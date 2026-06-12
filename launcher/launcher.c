/*
 * 模型拟合工具 — C 启动器
 *
 * 将整个项目打包为 ZIP 嵌入二进制文件。
 * 运行时解压到临时目录，调用系统 Python 执行 bootstrap.py，
 * 退出时自动清理临时目录。
 *
 * 编译:
 *   macOS/Linux: cc -O2 -o launcher launcher.c -lz
 *   Windows:      cl /O2 launcher.c zlib.lib
 *
 * 嵌入资源:
 *   python pack.py    → 生成 resource.h + 编译
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#ifdef _WIN32
  #include <windows.h>
  #include <io.h>
  #define popen  _popen
  #define pclose _pclose
  #define unlink _unlink
  #define rmdir  _rmdir
  #define PATH_SEP '\\'
  #define PATH_SEP_STR "\\"
  #define TEMP_ENV "TEMP"
#else
  #include <unistd.h>
  #include <signal.h>
  #include <sys/stat.h>
  #include <sys/wait.h>
  #include <dirent.h>
  #include <errno.h>
  #define PATH_SEP '/'
  #define PATH_SEP_STR "/"
  #define TEMP_ENV "TMPDIR"
#endif

#include <zlib.h>

/* ── 嵌入的资源 ZIP（由 pack.py 生成 resource.h）──── */
#ifdef RESOURCE_H
  #include "resource.h"
#else
  /* 占位 — 实际编译时由 resource.h 提供 */
  static const unsigned char resource_zip[] = {0};
  static const size_t resource_zip_size = 0;
#endif

/* ── 全局变量（信号处理用）──── */
static char g_temp_dir[1024] = {0};
static volatile int g_keep_alive = 1;

/* ── 宏 ──────────────────────────────────────────────── */
#define ZIP_LOCAL_SIG   0x04034b50
#define ZIP_CENTRAL_SIG 0x02014b50
#define ZIP_EOCD_SIG    0x06054b50

#define MAX_PATH_LEN 1024
#define ERR(...) do { fprintf(stderr, "[错误] " __VA_ARGS__); } while(0)
#define INFO(...) do { printf(__VA_ARGS__); } while(0)

/* ── 小端序读取 ────────────────────────────────────── */
static inline uint16_t read16(const unsigned char *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static inline uint32_t read32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ── 路径拼接 ────────────────────────────────────────── */
static void join_path(char *dst, size_t dst_sz, const char *dir, const char *name) {
    size_t dlen = strlen(dir);
    if (dlen >= dst_sz) return;
    memcpy(dst, dir, dlen);
    dst[dlen] = PATH_SEP;
    dst[dlen + 1] = '\0';

    /* 跳过 name 开头的路径分隔符（ZIP 里可能是 '/'） */
    while (*name == '/' || *name == '\\') name++;

    /* 在 name 中将 '/' 替换为平台分隔符 */
    const char *src = name;
    char *d = dst + dlen + 1;
    size_t remain = dst_sz - dlen - 1;
    while (*src && remain > 1) {
        *d++ = (*src == '/' || *src == '\\') ? PATH_SEP : *src;
        src++;
        remain--;
    }
    *d = '\0';
}

/* ── 创建目录递归 ─────────────────────────────────── */
static int mkdir_p(const char *path) {
    char tmp[MAX_PATH_LEN];
    strncpy(tmp, path, MAX_PATH_LEN);
    tmp[MAX_PATH_LEN - 1] = '\0';

    size_t len = strlen(tmp);
    /* 跳过末尾的路径分隔符 */
    while (len > 0 && (tmp[len - 1] == '/' || tmp[len - 1] == '\\')) {
        tmp[--len] = '\0';
    }

    for (size_t i = 1; i < len; i++) {
        if (tmp[i] == '/' || tmp[i] == '\\') {
            tmp[i] = '\0';
#ifdef _WIN32
            /* Windows: 跳过盘符 "C:" */
            if (i > 2) CreateDirectoryA(tmp, NULL);
#else
            mkdir(tmp, 0755);
#endif
            tmp[i] = PATH_SEP;
        }
    }
#ifdef _WIN32
    CreateDirectoryA(tmp, NULL);
#else
    mkdir(tmp, 0755);
#endif
    return 0;
}

/* ── 获取父目录 ─────────────────────────────────────── */
static void parent_dir(char *dst, size_t dst_sz, const char *path) {
    strncpy(dst, path, dst_sz);
    dst[dst_sz - 1] = '\0';
    char *last = strrchr(dst, PATH_SEP);
    if (!last) last = strrchr(dst, '/');
    if (last) *last = '\0';
}

/* ── ZIP 提取 ──────────────────────────────────────── */
static int extract_zip(const unsigned char *zip_data, size_t zip_size,
                       const char *dest_dir) {
    if (zip_size < 22) {
        ERR("ZIP 数据太小\n");
        return -1;
    }

    /* 查找 EOCD 签名 (从末尾向前搜索，兼容 ZIP 注释) */
    int64_t eocd_offset = -1;
    int64_t search_start = (int64_t)zip_size - 22;
    if (search_start < 0) search_start = 0;
    for (int64_t i = search_start; i >= 0; i--) {
        if (read32(zip_data + i) == ZIP_EOCD_SIG) {
            eocd_offset = i;
            break;
        }
    }
    if (eocd_offset < 0) {
        ERR("找不到 ZIP EOCD 记录\n");
        return -1;
    }

    uint16_t total_entries = read16(zip_data + eocd_offset + 10);
    uint32_t central_offset = read32(zip_data + eocd_offset + 16);

    INFO("提取 %u 个文件到 %s ...\n", total_entries, dest_dir);
    int extracted = 0;

    /* 遍历 central directory */
    unsigned char *central = (unsigned char *)zip_data + central_offset;
    for (uint16_t n = 0; n < total_entries; n++) {
        if (read32(central) != ZIP_CENTRAL_SIG) break;

        uint16_t comp_method   = read16(central + 10);
        uint32_t comp_size     = read32(central + 20);
        uint32_t uncomp_size   = read32(central + 24);
        uint16_t name_len      = read16(central + 28);
        uint16_t extra_len     = read16(central + 30);
        uint16_t comment_len   = read16(central + 32);
        uint32_t local_offset  = read32(central + 42);

        /* 读取文件名 */
        char name[512] = {0};
        uint16_t nl = name_len < 511 ? name_len : 511;
        memcpy(name, central + 46, nl);

        /* 跳过目录条目 */
        if (name[nl - 1] == '/' || name[nl - 1] == '\\') {
            /* 创建目录 */
            char full_path[MAX_PATH_LEN];
            join_path(full_path, MAX_PATH_LEN, dest_dir, name);
            mkdir_p(full_path);
            central += 46 + name_len + extra_len + comment_len;
            continue;
        }

        /* 读取 local file header */
        unsigned char *local = (unsigned char *)zip_data + local_offset;
        if (read32(local) != ZIP_LOCAL_SIG) {
            ERR("文件 '%s' local header 损坏\n", name);
            central += 46 + name_len + extra_len + comment_len;
            continue;
        }
        uint16_t local_name_len  = read16(local + 26);
        uint16_t local_extra_len = read16(local + 28);
        unsigned char *file_data = local + 30 + local_name_len + local_extra_len;

        /* 构建输出路径 */
        char full_path[MAX_PATH_LEN];
        join_path(full_path, MAX_PATH_LEN, dest_dir, name);

        /* 创建父目录 */
        char pdir[MAX_PATH_LEN];
        parent_dir(pdir, MAX_PATH_LEN, full_path);
        mkdir_p(pdir);

        /* 提取文件 */
        FILE *out = fopen(full_path, "wb");
        if (!out) {
            ERR("无法创建文件: %s\n", full_path);
            central += 46 + name_len + extra_len + comment_len;
            continue;
        }

        if (comp_method == 0) {
            /* stored — 直接写入 */
            fwrite(file_data, 1, uncomp_size, out);
        } else if (comp_method == 8) {
            /* deflated — 用 zlib 解压 */
            z_stream strm = {0};
            if (inflateInit2(&strm, -MAX_WBITS) != Z_OK) {
                ERR("zlib init 失败: %s\n", full_path);
                fclose(out);
                central += 46 + name_len + extra_len + comment_len;
                continue;
            }
            strm.next_in = file_data;
            strm.avail_in = comp_size;

            unsigned char buf[65536];
            int ret;
            do {
                strm.next_out = buf;
                strm.avail_out = sizeof(buf);
                ret = inflate(&strm, Z_NO_FLUSH);
                if (ret == Z_STREAM_ERROR || ret == Z_DATA_ERROR || ret == Z_MEM_ERROR) {
                    ERR("解压失败 (%d): %s\n", ret, full_path);
                    break;
                }
                fwrite(buf, 1, sizeof(buf) - strm.avail_out, out);
            } while (ret != Z_STREAM_END);
            inflateEnd(&strm);
        } else {
            ERR("不支持的压缩方法 %u: %s\n", comp_method, name);
        }

        fclose(out);
        extracted++;

        /* 跳到下一个 central directory entry */
        central += 46 + name_len + extra_len + comment_len;
    }

    INFO("提取完成: %d 个文件\n", extracted);
    return extracted > 0 ? 0 : -1;
}

/* ── 查找 Python ────────────────────────────────────── */
static int find_python(char *buf, size_t buf_sz) {
    const char *candidates[] = {"python3", "python", NULL};
    for (int i = 0; candidates[i]; i++) {
        char cmd[512];
#ifdef _WIN32
        snprintf(cmd, sizeof(cmd), "where %s 2>nul", candidates[i]);
#else
        snprintf(cmd, sizeof(cmd), "command -v %s 2>/dev/null", candidates[i]);
#endif
        FILE *fp = popen(cmd, "r");
        if (!fp) continue;
        if (fgets(buf, (int)buf_sz, fp)) {
            /* 去掉换行 */
            size_t len = strlen(buf);
            while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r')) {
                buf[--len] = '\0';
            }
            pclose(fp);
            if (len > 0) return 0;
        }
        pclose(fp);
    }
    return -1;
}

/* ── 创建临时目录 ──────────────────────────────────── */
static int create_temp_dir(char *buf, size_t buf_sz) {
    const char *tmp = getenv("TMPDIR");
    if (!tmp) tmp = getenv("TEMP");
    if (!tmp) tmp = getenv("TMP");
#ifdef _WIN32
    if (!tmp) tmp = "C:\\Windows\\Temp";
#else
    if (!tmp) tmp = "/tmp";
#endif

#ifdef _WIN32
    char tpl[MAX_PATH_LEN];
    snprintf(tpl, sizeof(tpl), "%s\\mf_XXXXXX", tmp);
    if (!_mktemp_s(tpl, strlen(tpl) + 1)) {
        CreateDirectoryA(tpl, NULL);
        strncpy(buf, tpl, buf_sz);
        return 0;
    }
#else
    snprintf(buf, buf_sz, "%s/mf_XXXXXX", tmp);
    if (mkdtemp(buf)) return 0;
#endif
    return -1;
}

/* ── 删除目录递归 ─────────────────────────────────── */
static void remove_dir(const char *path) {
#ifdef _WIN32
    /* Windows 递归删除 */
    char search[MAX_PATH_LEN];
    snprintf(search, sizeof(search), "%s\\*", path);
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA(search, &fd);
    if (h == INVALID_HANDLE_VALUE) {
        RemoveDirectoryA(path);
        return;
    }
    do {
        if (strcmp(fd.cFileName, ".") == 0 || strcmp(fd.cFileName, "..") == 0)
            continue;
        char full[MAX_PATH_LEN];
        snprintf(full, sizeof(full), "%s\\%s", path, fd.cFileName);
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            remove_dir(full);
        } else {
            DeleteFileA(full);
        }
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    RemoveDirectoryA(path);
#else
    DIR *d = opendir(path);
    if (!d) {
        rmdir(path);
        return;
    }
    struct dirent *ent;
    while ((ent = readdir(d))) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0)
            continue;
        char full[MAX_PATH_LEN];
        snprintf(full, sizeof(full), "%s/%s", path, ent->d_name);
        struct stat st;
        if (stat(full, &st) == 0 && S_ISDIR(st.st_mode)) {
            remove_dir(full);
        } else {
            unlink(full);
        }
    }
    closedir(d);
    rmdir(path);
#endif
}

/* ── 信号处理 ──────────────────────────────────────── */
static void cleanup_and_exit(void) {
    if (g_temp_dir[0]) {
        INFO("\n清理临时目录: %s\n", g_temp_dir);
        remove_dir(g_temp_dir);
        g_temp_dir[0] = '\0';
    }
}

#ifdef _WIN32
static BOOL WINAPI ctrl_handler(DWORD fdwCtrlType) {
    (void)fdwCtrlType;
    cleanup_and_exit();
    ExitProcess(1);
    return TRUE;
}
#else
static void signal_handler(int sig) {
    (void)sig;
    cleanup_and_exit();
    _exit(1);
}
#endif

/* ── 运行 Python bootstrap ────────────────────────── */
static int run_bootstrap(const char *python, const char *temp_dir,
                         int argc, char **argv) {
    /* 构建命令行 */
    char cmd[8192];
    int pos = snprintf(cmd, sizeof(cmd),
                       "\"%s\" \"%s%cmodel_fitting%cbootstrap.py\" --auto",
                       python, temp_dir, PATH_SEP, PATH_SEP);

    /* 附加用户参数（跳过程序名） */
    for (int i = 1; i < argc && (size_t)pos < sizeof(cmd) - 1; i++) {
        pos += snprintf(cmd + pos, sizeof(cmd) - (size_t)pos, " \"%s\"", argv[i]);
    }

    INFO("运行: %s\n", cmd);

#ifdef _WIN32
    STARTUPINFOA si = {0};
    PROCESS_INFORMATION pi = {0};
    si.cb = sizeof(si);

    if (!CreateProcessA(NULL, cmd, NULL, NULL, FALSE,
                        0, NULL, temp_dir, &si, &pi)) {
        ERR("启动 Python 失败 (错误码 %lu)\n", GetLastError());
        return -1;
    }
    /* 等待进程结束，同时保持信号响应 */
    while (WaitForSingleObject(pi.hProcess, 100) == WAIT_TIMEOUT) {
        /* 继续等待 */
    }
    DWORD exit_code = 1;
    GetExitCodeProcess(pi.hProcess, &exit_code);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return (int)exit_code;
#else
    pid_t pid = fork();
    if (pid < 0) {
        ERR("fork 失败\n");
        return -1;
    }
    if (pid == 0) {
        /* 子进程: 用 sh -c 执行完整命令行 */
        execl("/bin/sh", "sh", "-c", cmd, (char *)NULL);
        ERR("execl 失败\n");
        _exit(127);
    }

    /* 父进程：等待 */
    int status;
    while (waitpid(pid, &status, WNOHANG) == 0) {
        usleep(100000); /* 100ms */
    }

    if (WIFEXITED(status)) return WEXITSTATUS(status);
    return -1;
#endif
}

/* ── 主入口 ────────────────────────────────────────── */
int main(int argc, char **argv) {
    /* 信号处理 */
#ifdef _WIN32
    SetConsoleCtrlHandler(ctrl_handler, TRUE);
#else
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
#endif
    atexit(cleanup_and_exit);

    INFO("模型拟合工具 — C Launcher v0.9\n\n");

    /* 1. 查找 Python */
    char python_path[MAX_PATH_LEN] = {0};
    if (find_python(python_path, sizeof(python_path)) != 0) {
        ERR("找不到 Python 3。请安装 Python >= 3.10：\n"
            "  https://www.python.org/downloads/\n");
        return 1;
    }
    INFO("[✓] Python: %s\n", python_path);

    /* 2. 创建临时目录 */
    if (create_temp_dir(g_temp_dir, sizeof(g_temp_dir)) != 0) {
        ERR("无法创建临时目录\n");
        return 1;
    }
    INFO("[✓] 临时目录: %s\n", g_temp_dir);

    /* 3. 提取资源 */
    if (resource_zip_size == 0) {
        ERR("未嵌入资源文件。请运行 pack.py 重新构建。\n");
        remove_dir(g_temp_dir);
        g_temp_dir[0] = '\0';
        return 1;
    }

    if (extract_zip(resource_zip, resource_zip_size, g_temp_dir) != 0) {
        ERR("提取资源失败\n");
        return 1;
    }

    /* 4. 运行 bootstrap.py */
    int ret = run_bootstrap(python_path, g_temp_dir, argc, argv);

    /* 5. 清理 */
    cleanup_and_exit();

    return ret;
}
