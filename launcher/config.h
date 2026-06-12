/*
 * config.h — 项目特定配置
 * ─────────────────────────────────────────────────
 * 移植到新项目时只需要修改这个文件。
 * 然后运行: python pack.py
 */

#ifndef CONFIG_H
#define CONFIG_H

/* ── 项目信息 ───────────────────────────────────── */
#define PROJECT_NAME        "模型拟合工具"
#define PROJECT_NAME_EN     "Model Fitting"
#define PROJECT_VERSION     "0.9"
#define PROJECT_URL         "https://www.python.org/downloads/"  /* Python 下载链接 */

/* ── ZIP 前缀 ────────────────────────────────────── */
/* ZIP 包内所有文件的前缀目录名，必须和 Python 包名一致 */
#define ZIP_PREFIX          "model_fitting"

/* ── Python 最低版本 ─────────────────────────────── */
#define MIN_PYTHON_MAJOR    3
#define MIN_PYTHON_MINOR    10

/* ── 启动入口 ────────────────────────────────────── */
/* bootstrap.py 负责实际的 import + 启动 */
/* 入口脚本路径: <ZIP_PREFIX>/bootstrap.py */

/* ── 依赖包列表 ──────────────────────────────────── */
/* {import_name, pip_name, min_version_string}           */
/* import_name: Python import 检测用                     */
/* pip_name:    pip install 用的包名                      */
/* min_version: pip install 的版本约束 (如 ">=2.0")       */
#define REQUIREMENTS_COUNT  7

static const struct {
    const char *import_name;
    const char *pip_name;
    const char *min_version;
} REQUIREMENTS[] = {
    {"numpy",      "numpy",      ">=2.0"},
    {"scipy",      "scipy",      ">=1.10"},
    {"pandas",     "pandas",     ">=2.0"},
    {"matplotlib", "matplotlib", ">=3.8"},
    {"PIL",        "pillow",     ">=10.0"},
    {"openpyxl",   "openpyxl",   ">=3.0"},
    {"xlrd",       "xlrd",       ">=2.0"},
};

/* ── tkinter 安装提示（各平台） ───────────────────── */
#define TKINTER_WIN_MSG \
    "请重新运行 Python 安装程序，勾选 'tcl/tk and IDLE' 选项。"

#define TKINTER_MAC_MSG \
    "请运行: brew install python-tk\n" \
    "或使用系统自带 Python: /usr/bin/python3"

#define TKINTER_LINUX_MSG \
    "请运行:\n" \
    "  sudo apt install python3-tk    (Debian/Ubuntu)\n" \
    "  sudo dnf install python3-tkinter (Fedora/RHEL)"

#endif /* CONFIG_H */
