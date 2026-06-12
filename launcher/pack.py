#!/usr/bin/env python3
"""
通用 Python 项目 C 启动器 — 打包脚本

将项目文件压缩为 ZIP，嵌入 C 二进制并编译为独立可执行文件。

用法:
    python pack.py              # 完整打包 + 编译
    python pack.py --zip-only   # 仅生成 resource.h
    python pack.py --compile    # 仅编译（需要已有 resource.h）

前置条件:
    - macOS/Linux: cc / clang / gcc + zlib
    - Windows:     Visual Studio 或 MinGW-w64 + zlib

移植到新项目:
    1. 复制 launcher/ 目录到你的项目根目录
    2. 修改 launcher/config.h
    3. 创建 bootstrap.py（启动入口）
    4. 运行: python launcher/pack.py
"""

import os
import sys
import struct
import zlib
import subprocess
import shutil
from pathlib import Path

HERE = Path(__file__).parent.parent  # 项目根目录（pack.py 在 launcher/ 下）
LAUNCHER_DIR = HERE / "launcher"

# ── 排除列表 ─────────────────────────────────────────
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache",
    "build", "dist", "log", ".venv_pack",
    ".Spotlight-V100", ".fseventsd", ".Trashes",
    ".TemporaryItems", "$RECYCLE.BIN",
    "launcher",  # 打包工具自身
}

EXCLUDE_FILES = {
    "model_fitting.zip",
    "保存文件.rda",
    "build_chatgpt.py",
    "pack.py",
    "test_weibull.csv",
    "test.xlsx",
}

COMPRESS_LEVEL = 9

# ── 从 config.h 读取配置 ───────────────────────────────
def read_config():
    """读取 launcher/config.h，返回 ZIP_PREFIX 和输出文件名。"""
    import re
    config_h = LAUNCHER_DIR / "config.h"
    if not config_h.exists():
        print("[错误] 找不到 config.h")
        sys.exit(1)

    content = config_h.read_text(encoding="utf-8")
    zip_prefix = "model_fitting"
    out_name = "model_fitting"

    for line in content.splitlines():
        # 匹配: #define KEY "value"
        m = re.match(r'#define\s+(\w+)\s+"([^"]+)"', line)
        if m:
            key, val = m.group(1), m.group(2)
            if key == 'ZIP_PREFIX':
                zip_prefix = val
            elif key == 'PROJECT_NAME_EN':
                out_name = val.lower().replace(" ", "_")

    return zip_prefix, out_name


ZIP_PREFIX, OUTPUT_NAME = read_config()


def should_exclude(relpath: str) -> bool:
    parts = Path(relpath).parts
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    fname = os.path.basename(relpath)
    if fname in EXCLUDE_FILES:
        return True
    if fname.startswith("._"):
        return True
    if fname.endswith(".spec"):
        return True
    return False


def create_zip():
    """创建项目 ZIP，返回字节数据。"""
    files = []
    for root, dirs, names in os.walk(HERE):
        dirs[:] = [d for d in sorted(dirs) if d not in EXCLUDE_DIRS]
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, HERE)
            if should_exclude(rel):
                continue
            files.append((full, rel))

    print(f"打包 {len(files)} 个文件 ...")

    entries = []
    local_headers = []
    offset = 0

    for full_path, rel_path in files:
        with open(full_path, "rb") as f:
            data = f.read()

        zip_name = ZIP_PREFIX + "/" + rel_path.replace("\\", "/")
        crc = zlib.crc32(data) & 0xFFFFFFFF

        if COMPRESS_LEVEL > 0:
            compressed = zlib.compress(data, COMPRESS_LEVEL)
            if len(compressed) < len(data):
                method = 8
                comp_data = compressed[2:-4]
            else:
                method = 0
                comp_data = data
        else:
            method = 0
            comp_data = data

        comp_size = len(comp_data)
        uncomp_size = len(data)
        name_bytes = zip_name.encode("utf-8")

        local_header = bytearray()
        local_header += struct.pack("<I", 0x04034b50)
        local_header += struct.pack("<H", 20)
        local_header += struct.pack("<H", 0x0800)
        local_header += struct.pack("<H", method)
        local_header += struct.pack("<H", 0)
        local_header += struct.pack("<H", 0)
        local_header += struct.pack("<I", crc)
        local_header += struct.pack("<I", comp_size)
        local_header += struct.pack("<I", uncomp_size)
        local_header += struct.pack("<H", len(name_bytes))
        local_header += struct.pack("<H", 0)
        local_header += name_bytes

        cd_entry = bytearray()
        cd_entry += struct.pack("<I", 0x02014b50)
        cd_entry += struct.pack("<H", 20)
        cd_entry += struct.pack("<H", 20)
        cd_entry += struct.pack("<H", 0x0800)
        cd_entry += struct.pack("<H", method)
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<I", crc)
        cd_entry += struct.pack("<I", comp_size)
        cd_entry += struct.pack("<I", uncomp_size)
        cd_entry += struct.pack("<H", len(name_bytes))
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<H", 0)
        cd_entry += struct.pack("<I", 0)
        cd_entry += struct.pack("<I", offset)
        cd_entry += name_bytes

        entries.append((len(local_headers), cd_entry))
        local_headers.append(bytes(local_header) + comp_data)
        offset += len(local_headers[-1])

    result = bytearray()
    for lh in local_headers:
        result += lh
    cd_start = len(result)
    for _, cd in entries:
        result += cd
    cd_end = len(result)

    result += struct.pack("<I", 0x06054b50)
    result += struct.pack("<H", 0)
    result += struct.pack("<H", 0)
    result += struct.pack("<H", len(entries))
    result += struct.pack("<H", len(entries))
    result += struct.pack("<I", cd_end - cd_start)
    result += struct.pack("<I", cd_start)
    result += struct.pack("<H", 0)

    print(f"  ZIP 大小: {len(result) / 1024:.1f} KB")
    return bytes(result)


def generate_header(zip_data: bytes):
    """生成 resource.h。"""
    output_path = LAUNCHER_DIR / "resource.h"
    lines = [
        "/* 自动生成 — 由 pack.py 创建 */",
        "/* 包含嵌入式资源 ZIP */",
        "",
        f"/* 压缩后大小: {len(zip_data)} 字节 */",
    ]

    data_lines = []
    for i in range(0, len(zip_data), 16):
        chunk = zip_data[i:i + 16]
        hex_bytes = ", ".join(f"0x{b:02x}" for b in chunk)
        data_lines.append(f"    {hex_bytes},")

    lines.append("static const unsigned char resource_zip[] = {")
    lines.extend(data_lines)
    lines.append("};")
    lines.append("")
    lines.append("static const size_t resource_zip_size = sizeof(resource_zip);")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  生成: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")


def find_compiler():
    """查找可用的 C 编译器。"""
    if sys.platform == "win32":
        # Windows: 优先 MSVC，然后 MinGW
        for cc in ["cl", "gcc", "clang"]:
            if shutil.which(cc):
                return cc
    else:
        candidates = ["cc", "gcc", "clang"]
        if sys.platform == "darwin":
            candidates = ["clang", "cc", "gcc"]
        for cc in candidates:
            if shutil.which(cc):
                return cc
    return None


def compile_launcher():
    cc = find_compiler()
    if not cc:
        print("[错误] 找不到 C 编译器")
        print("")
        print("  macOS:")
        print("    xcode-select --install")
        print("")
        print("  Linux (Debian/Ubuntu):")
        print("    sudo apt install build-essential zlib1g-dev")
        print("")
        print("  Linux (Fedora/RHEL):")
        print("    sudo dnf install gcc zlib-devel")
        print("")
        print("  Windows:")
        print("    方案 A — MinGW-w64:")
        print("      1. 下载: https://winlibs.com/")
        print("      2. 解压并加入 PATH")
        print("      3. 重开终端运行: python launcher/pack.py")
        print("")
        print("    方案 B — Visual Studio:")
        print("      1. 安装 Visual Studio Build Tools")
        print("      2. 打开 'Developer Command Prompt'")
        print("      3. 先运行: python launcher/pack.py --zip-only")
        print("      4. 再运行: cl /O2 /DRESOURCE_H /I launcher launcher\\launcher.c "
              "/link /SUBSYSTEM:WINDOWS zlib.lib")
        return False

    src = LAUNCHER_DIR / "launcher.c"
    if not src.exists():
        print(f"[错误] 找不到: {src}")
        return False

    ext = ".exe" if sys.platform == "win32" else ""
    out = LAUNCHER_DIR / f"{OUTPUT_NAME}{ext}"

    # 构建编译参数
    if cc == "cl":
        # MSVC
        flags = [cc, "/O2", "/DRESOURCE_H",
                 f"/I{LAUNCHER_DIR}", str(src),
                 "/link", "/SUBSYSTEM:WINDOWS", "zlib.lib",
                 f"/OUT:{out}"]
    elif sys.platform == "win32":
        # MinGW / Clang on Windows (无命令行窗口)
        flags = [cc, "-O2", "-s", "-o", str(out), str(src),
                 "-lz", "-DRESOURCE_H", f"-I{LAUNCHER_DIR}",
                 "-mwindows", "-std=c11"]
    else:
        # macOS / Linux
        flags = [cc, "-O2", "-s", "-o", str(out), str(src),
                 "-lz", "-DRESOURCE_H", f"-I{LAUNCHER_DIR}"]

    print(f"编译: {' '.join(str(f) for f in flags)}")

    if cc == "cl":
        # MSVC 输出到 stdout/stderr 混合
        result = subprocess.run(
            [str(f) for f in flags],
            cwd=LAUNCHER_DIR,
            capture_output=True, text=True,
            shell=True  # MSVC 需要 shell 环境
        )
    else:
        result = subprocess.run(
            [str(f) for f in flags],
            cwd=LAUNCHER_DIR,
            capture_output=True, text=True
        )

    if result.returncode != 0:
        print(f"[错误] 编译失败:\n{result.stderr}")
        if "zlib" in (result.stderr + result.stdout).lower():
            print(""
            "  → 缺少 zlib 开发库。请安装：\n"
            "    macOS: (系统自带，不需要额外安装)\n"
            "    Linux: sudo apt install zlib1g-dev\n"
            "    Windows (MinGW): pacman -S mingw-w64-x86_64-zlib\n"
            "    Windows (MSVC): 从 https://zlib.net/ 下载或使用 vcpkg")
        return False

    if result.stderr.strip():
        print(f"[警告] {result.stderr.strip()}")

    size = os.path.getsize(out)
    print(f"[✓] 编译成功: {out} ({size / 1024:.0f} KB)")

    if sys.platform != "win32":
        os.chmod(out, 0o755)

    return True


def pack():
    print("╔══════════════════════════════╗")
    print("║     Python C Launcher        ║")
    print("║       打包工具               ║")
    print("╚══════════════════════════════╝")
    print()

    os.chdir(HERE)

    print("── 1. 创建资源包 ──")
    zip_data = create_zip()

    print("\n── 2. 生成 resource.h ──")
    generate_header(zip_data)

    print("\n── 3. 编译启动器 ──")
    if not compile_launcher():
        return 1

    print(f"\n[✓] 打包完成! 输出: launcher/{OUTPUT_NAME}{'.exe' if sys.platform=='win32' else ''}")
    return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Python C Launcher 打包脚本")
    parser.add_argument("--zip-only", action="store_true")
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()

    if args.compile:
        sys.exit(0 if compile_launcher() else 1)
    elif args.zip_only:
        zip_data = create_zip()
        generate_header(zip_data)
        sys.exit(0)
    else:
        sys.exit(pack())
