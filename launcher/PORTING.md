# Python C Launcher — 移植指南

将任意 Python GUI/CLI 项目打包为 **500-800 KB 独立二进制文件**。

依赖系统 Python 运行环境，缺失的包自动通过 pip 安装。

---

## 工作原理

```
用户双击 launcher.exe (无命令行窗口)
  │
  ├─ 1. 检测系统 Python 版本
  ├─ 2. 检测 tkinter（或你的 GUI 框架）
  ├─ 3. 逐项检测 pip 依赖包
  ├─ 4. 缺失 → 弹出对话框询问 → pip install
  ├─ 5. 全部就绪 → 解压项目到临时目录 → 启动 Python App
  └─ 6. App 退出 → 自动清理临时目录
```

所有步骤在 C 层完成，不依赖 Python 脚本做环境检测。启动后无命令行窗口（Windows）/无终端窗口（macOS），只有原生对话框。

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

Windows 有两种方案：

#### 方案 A: MinGW-w64（推荐，简单）

```powershell
# 1. 下载 MinGW-w64: https://winlibs.com/
#    选择 "GCC + LLVM/Clang" 版本
#    解压到 C:\mingw64

# 2. 加入 PATH
set PATH=C:\mingw64\bin;%PATH%

# 3. 安装 zlib（MinGW 的包管理器）
pacman -S mingw-w64-x86_64-zlib

# 4. 打包
cd your-project
python launcher\pack.py

# 输出: launcher\your_tool.exe (~700 KB)
```

#### 方案 B: Visual Studio

```powershell
# 1. 安装 Visual Studio Build Tools
#    勾选 "C++ Build Tools" + "Windows SDK"

# 2. 安装 zlib
#    方式 a: vcpkg install zlib:x64-windows
#    方式 b: 从 https://zlib.net/ 下载并编译 zlib.lib

# 3. 打开 "Developer Command Prompt for VS"

# 4. 生成 resource.h（不需要编译器）
cd your-project
python launcher\pack.py --zip-only

# 5. 手动编译（/SUBSYSTEM:WINDOWS = 无命令行窗口）
cl /O2 /DRESOURCE_H /I launcher launcher\launcher.c ^
   /link /SUBSYSTEM:WINDOWS zlib.lib /OUT:launcher\your_tool.exe
```

#### 无 zlib 的备选：使用 miniz

如果不想折腾 zlib，可以用单头文件 `miniz`（公共域，zlib API 兼容）：

```bash
# 下载 miniz.h 到 launcher/
curl -o launcher/miniz.h https://raw.githubusercontent.com/richgel999/miniz/master/miniz.h

# 然后修改 launcher.c 顶部:
#   #include <zlib.h>  →  #include "miniz.h"

# 编译时去掉 -lz:
#   gcc ... launcher.c -DRESOURCE_H -Ilauncher -mwindows   (MinGW)
#   cl ... launcher.c /link /SUBSYSTEM:WINDOWS             (MSVC)
```

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

弹出原生对话框，显示 `PROJECT_URL` 指向的 Python 下载页面。

**Q: pip install 失败了？**

弹出对话框显示失败原因（通常是网络问题），提示手动安装命令。

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

**Q: 怎么在 Windows 上编译？**

```cmd
:: Visual Studio
cl /O2 launcher.c zlib.lib /link /SUBSYSTEM:WINDOWS

:: MinGW-w64
gcc -O2 -o my_tool.exe launcher.c -lz -mwindows
```

pack.py 暂时只支持 macOS/Linux 的 clang/gcc。Windows 编译需要手动操作或改写 pack.py。

---

## 架构总览

```
launcher.c (C, ~550 行)
  │
  ├─ msgbox()           → 原生对话框 (Win: MessageBox, Mac: osascript, Linux: zenity)
  ├─ extract_zip()      → 零依赖 ZIP 解压 (zlib DEFLATE)
  ├─ check_tkinter()    → python3 -c "import tkinter"
  ├─ check_package()    → python3 -c "import numpy" (逐项)
  ├─ pip_install()      → python3 -m pip install ...
  └─ main()
       │
       ├─ Python 检查 → 版本检查 → temp 解压
       ├─ tkinter 检查 → pip 逐项检查 → 安装 → 验证
       └─ 启动 python3 bootstrap.py [args]

config.h (项目配置)
  ├─ 项目名 / 版本 / ZIP 前缀
  ├─ Python 版本要求
  ├─ 依赖包列表 (REQUIREMENTS[])
  └─ tkinter 各平台安装提示

bootstrap.py (项目根目录, Python)
  └─ sys.path 设置 → import 项目包 → 启动入口

pack.py (打包脚本, Python)
  ├─ 读取 config.h 获取 ZIP_PREFIX
  ├─ ZIP 项目文件 (排除 .git/__pycache__/launcher/)
  ├─ 生成 resource.h (C 数组)
  └─ 编译 launcher.c
```
