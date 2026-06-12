# Python C Launcher — 移植指南

将任意 Python GUI/CLI 项目打包为 **500-800 KB 独立二进制文件**。

依赖系统 Python 运行环境，缺失的包自动通过 pip 安装。

---

## 工作原理

```
用户双击 launcher.exe (无命令行窗口)
  │
  ├─ 0. 检查标记文件 %TEMP%\_mf_env_ok → 存在则直接跳到步骤 6
  ├─ 1. 查找系统 Python (py -3 → where python → 常见路径)
  ├─ 2. 验证版本 (python --version → 解析 "Python 3.x.y")
  ├─ 3. 解压内嵌 ZIP 到临时目录
  ├─ 4. 检查 pip 依赖 (逐包, 显示进度窗口)
  ├─ 5. 缺失 → 静默 pip install (无对话框)
  ├─ 6. 全部就绪 → 用 pythonw.exe 启动 Python App
  └─ 7. Launcher 立即退出 (临时目录保留给 Python 使用)
```

所有子进程使用 `CreateProcess + CREATE_NO_WINDOW`，无 cmd.exe 黑框。
首次检查通过后写标记文件，后续启动跳过步骤 4-5，零弹窗直接进应用。
环境检查失败时才弹 Unicode 对话框（MessageBoxW，UTF-8 中文无乱码）。

---

## 快速开始（3 步移植到你的项目）

### 第 1 步：复制 launcher 目录

```
your-project/
├── launcher/              ← 复制整个目录
│   ├── config.h           ← 你要改的文件
│   ├── launcher.c         ← 通用 C 代码（不改）
│   ├── pack.py            ← 打包脚本（可能需要改排除列表）
│   └── .gitignore
├── your_package/
│   ├── __init__.py
│   └── ...
└── bootstrap.py           ← 你要创建的文件
```

### 第 2 步：修改 config.h

打开 `launcher/config.h`，修改以下内容：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `PROJECT_NAME` | 项目中文名（对话框标题） | `"我的工具"` |
| `PROJECT_NAME_EN` | 项目英文名（输出文件名） | `"My Tool"` |
| `PROJECT_VERSION` | 版本号 | `"1.0"` |
| `PROJECT_URL` | Python 下载链接 | `"https://..."` |
| `ZIP_PREFIX` | ZIP 内的包目录名 | `"my_package"` |
| `MIN_PYTHON_MAJOR` | Python 最低主版本 | `3` |
| `MIN_PYTHON_MINOR` | Python 最低次版本 | `10` |
| `REQUIREMENTS_COUNT` | 依赖包数量 | `5` |
| `REQUIREMENTS[]` | 依赖包列表 | 见下方 |
| `TKINTER_*_MSG` | tkinter 安装提示 | 按平台填写 |

**依赖包列表格式：**

```c
#define REQUIREMENTS_COUNT  5

static const struct {
    const char *import_name;   /* Python import 检测用     */
    const char *pip_name;      /* pip install 用的包名      */
    const char *min_version;   /* 版本约束                  */
} REQUIREMENTS[] = {
    {"numpy",      "numpy",      ">=2.0"},
    {"pandas",     "pandas",     ">=2.0"},
    {"matplotlib", "matplotlib", ">=3.8"},
    {"requests",   "requests",   ">=2.28"},
    {"PIL",        "pillow",     ">=10.0"},
};
```

> **注意：** `import_name` 和 `pip_name` 通常相同，但有些不同。例如 Pillow 的 import 名是 `PIL` 而 pip 名是 `pillow`。

**如果你的项目不使用 tkinter：**

如果你的 GUI 框架是 PyQt、wxPython 等（它们是纯 pip 包），把它们的 import 名加入 `REQUIREMENTS[]` 即可。C 层的 tkinter 检查只会提示用户安装，不会阻塞启动。不需要修改 `TKINTER_*_MSG`。

如果你的项目是 CLI 工具（无 GUI），直接忽略 tkinter 相关配置，依赖列表里不包含 GUI 框架就好。

### 第 3 步：创建 bootstrap.py

在项目根目录创建 `bootstrap.py`，这是你的应用启动入口：

```python
"""
我的工具 — 启动入口
用法：python bootstrap.py [data.csv]
"""
import os
import sys

# 确保包可导入
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def main():
    csv_path = None
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            csv_path = a

    try:
        # === 这里改成你的启动代码 ===
        from my_package.main import run
        run(csv_path=csv_path)
        # ==========================
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

核心就 40 行，关键只改一行：把 `from my_package.main import run` 换成你的入口。

### 打包

```bash
cd your-project
python launcher/pack.py
```

输出文件：`launcher/my_tool` (macOS/Linux) 或 `launcher/my_tool.exe` (Windows)

---

## 文件说明

| 文件 | 作用 | 移植时需要改？ |
|------|------|:---:|
| `config.h` | 项目名称、依赖列表、版本要求 | **是** |
| `launcher.c` | C 启动器（ZIP 解压、依赖检测、原生对话框） | 否 |
| `pack.py` | 打包脚本（ZIP 创建、resource.h 生成、编译） | 可能需要改排除列表 |
| `bootstrap.py` | Python 启动入口（在项目根目录） | **是**（创建） |

---

## pack.py 排除列表

`pack.py` 中的 `EXCLUDE_DIRS` 和 `EXCLUDE_FILES` 控制哪些文件不打包进 ZIP。

**默认排除的有：**

- `.git`、`__pycache__`、build 产物
- `launcher/`（打包工具自身）
- `test_*.csv`、`test_*.xlsx`（测试数据通常很大）

**根据你的项目调整：**

```python
# 你的项目有哪些不需要打包的大文件/目录？
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache",
    "build", "dist", "log", ".venv",
    "launcher",               # 打包工具自身
    "assets",                 # 如果资源文件太大
}

EXCLUDE_FILES = {
    "large_dataset.csv",
    "training_data.h5",
    ".env",
}
```

---

## 各操作系统打包步骤

### macOS

```bash
# 1. 安装编译器（如果没有）
xcode-select --install

# 2. 打包
cd your-project
python launcher/pack.py

# 输出: launcher/your_tool (~700 KB)
```

双击即可运行，无终端窗口。依赖 macOS 内建 clang + zlib。

---

### Linux

```bash
# 1. 安装依赖
# Debian/Ubuntu
sudo apt install build-essential zlib1g-dev

# Fedora/RHEL
sudo dnf install gcc zlib-devel

# 2. 打包
cd your-project
python launcher/pack.py

# 输出: launcher/your_tool (~700 KB)
```

---

### Windows

#### 方案 A: MinGW-w64（推荐）

```powershell
# 1. 安装 MinGW-w64（Dev-Cpp 自带, 或从 https://winlibs.com/ 下载）
#    确保 gcc.exe 在 PATH 中

# 2. 安装 zlib 开发文件到 MinGW 目录
#    从 zlib.net 下载源码, 交叉编译或直接使用预编译包:
#    将 zlib.h / zconf.h 复制到 MinGW/include/
#    将 libz.a 复制到 MinGW/lib/

# 3. 打包（pack.py 已支持 Windows MinGW）
cd your-project
python launcher\pack.py

# 输出: launcher\your_tool.exe (~700 KB)
```

#### 方案 B: Visual Studio

```powershell
# 1. 安装 Visual Studio Build Tools (C++ Build Tools + Windows SDK)

# 2. 安装 zlib: vcpkg install zlib:x64-windows

# 3. 打开 "Developer Command Prompt for VS"
cd your-project
python launcher\pack.py

# pack.py 自动检测 cl.exe 并使用 MSVC 编译
```

> **注意：** pack.py 已内置对 MSVC (`cl`) 和 MinGW (`gcc`) 的自动检测。
> 所有子进程调用均使用 `CreateProcess(CREATE_NO_WINDOW)`，不依赖 shell 重定向语法（`2>&1` / `2>nul`），因此在两种编译器下行为一致。

---

## 体积对比

实测数据（本项目）：

| 打包方式 | 体积 | 需预装 |
|----------|------|--------|
| PyInstaller | ~74 MB | 无 |
| C Launcher | ~730 KB | Python 3.10+ |

---

## 常见问题

**Q: 用户没有安装 Python 怎么办？**

弹出 Unicode 对话框，显示找到的路径和版本号，以及 Python 下载页面链接。

**Q: pip install 失败了？**

弹出对话框显示失败原因（通常是网络问题），提示手动安装命令。
首次安装是静默的，不弹确认框。只有失败时才弹错误提示。

**Q: 依赖安装后每次启动还是会检查吗？**

不会。首次检查全部通过后，写入标记文件 `%TEMP%\_mf_env_ok`（Windows）或 `/tmp/_mf_env_ok`（macOS/Linux）。
后续启动直接跳过环境检查，零弹窗。如需重新检查，删除该文件即可。

**Q: 为什么启动 Python 后没有控制台黑框？**

Windows 上 launcher 使用 `pythonw.exe`（GUI 子系统）启动应用，配合 `CREATE_NO_WINDOW` 标志。
所有子进程（`py -3`、`pip install` 等）均通过 `CreateProcess(CREATE_NO_WINDOW)` 执行，不闪 cmd 窗口。

**Q: 依赖列表里的包版本约束怎么写？**

```c
{"numpy", "numpy", ">=2.0"},
```

C 层只检查包是否可 import，不检查版本号。版本约束传给 `pip install` 使用。

**Q: 我的包名和 import 名不一样怎么办？**

```c
{"cv2",  "opencv-python",  ">=4.0"},    // import cv2, pip install opencv-python
{"PIL",  "pillow",         ">=10.0"},   // import PIL, pip install pillow
{"yaml", "pyyaml",         ">=6.0"},    // import yaml, pip install pyyaml
```

`import_name` 是 C 代码要用 `python -c "import X"` 检查的名字。`pip_name` 是 pip 安装用的包名。

**Q: 需要支持多个 Python 入口点？**

bootstrap.py 里用 `sys.argv` 分发，支持 `--legacy` 之类的标志切换启动方式。

---

## 架构总览

```
launcher.c (C, ~700 行)
  │
  ├─ win_msgbox()        → Unicode 对话框 (MessageBoxW, UTF-8 无乱码)
  ├─ show_status()       → 进度窗口 (CreateWindowExW, 🚀 + 大字体)
  ├─ extract_zip()       → 零依赖 ZIP 解压 (zlib DEFLATE)
  ├─ find_python()       → py -3 → where → 常见路径, 内嵌 --version 验证
  ├─ check_package()     → python -c "import X", 检查输出中是否有 Error
  ├─ pip_install()       → python -m pip install (静默, 无确认框)
  │
  ├─ spopen() / ssys()   → CreateProcess + CREATE_NO_WINDOW (替代 popen/system)
  ├─ pump_messages()     → PeekMessage 保持状态窗口响应
  │
  └─ main()
       │
       ├─ 标记文件检查 → 存在则跳过环境检查
       ├─ Python 查找 + 版本验证
       ├─ 临时目录解压
       ├─ pip 逐包检查 (显示 "正在检查 X (N/M)...")
       ├─ 缺失 → 静默安装 → 显示 "正在安装依赖..."
       ├─ 通过 → 写标记文件 %TEMP%\_mf_env_ok
       └─ 用 pythonw.exe 启动 bootstrap.py → _exit(0) 退出

config.h (项目配置)
  ├─ 项目名 / 版本 / ZIP 前缀
  ├─ Python 版本要求 (MIN_PYTHON_MAJOR/MINOR)
  ├─ 依赖包列表 (REQUIREMENTS[] — import_name / pip_name / min_version)
  └─ tkinter 各平台安装提示 (仅 macOS/Linux 检查)

bootstrap.py (项目根目录, Python)
  └─ sys.path 设置 → import 项目包 → 启动入口

pack.py (打包脚本, Python)
  ├─ 读取 config.h 获取 ZIP_PREFIX
  ├─ ZIP 项目文件 (排除 .git/__pycache__/launcher/)
  ├─ 生成 resource.h (C 数组)
  ├─ 自动检测编译器 (cl.exe 或 gcc)
  └─ 编译 launcher.c + 链接 zlib → 输出 exe
```
