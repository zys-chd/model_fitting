"""
模型拟合工具 — 启动引导脚本
由 C launcher 调用，负责检查运行环境、安装缺失依赖、启动主程序。

用法:
    python bootstrap.py              # 交互模式：缺依赖时询问是否安装
    python bootstrap.py --auto       # 自动安装缺失依赖
    python bootstrap.py data.csv     # 传参给主程序
"""

import os
import sys
import subprocess
import platform
import shutil

MIN_PYTHON = (3, 10)

# ── 依赖定义 ──────────────────────────────────────────────
# (import名, pip包名, 版本约束, 最小版本号)
REQUIREMENTS = [
    ("numpy",      "numpy",      "numpy>=2.0",       (2, 0)),
    ("scipy",      "scipy",      "scipy>=1.10",      (1, 10)),
    ("pandas",     "pandas",     "pandas>=2.0",      (2, 0)),
    ("matplotlib", "matplotlib", "matplotlib>=3.8",   (3, 8)),
    ("PIL",        "pillow",     "pillow>=10.0",      (10, 0)),
    ("openpyxl",   "openpyxl",   "openpyxl>=3.0",     (3, 0)),
    ("xlrd",       "xlrd",       "xlrd>=2.0",         (2, 0)),
]

# tkinter 不是 pip 包，需特殊处理
TKINTER_INSTALL_GUIDE = {
    "Windows": "请重新运行 Python 安装程序，勾选 'tcl/tk and IDLE' 选项。",
    "Darwin":  "请运行: brew install python-tk   （Homebrew Python）\n"
               "         或使用系统自带 Python: /usr/bin/python3",
    "Linux":   "请运行: sudo apt install python3-tk   (Debian/Ubuntu)\n"
               "        sudo dnf install python3-tkinter  (Fedora/RHEL)",
}


def get_pip_cmd():
    """返回可用的 pip 安装命令（优先使用 python -m pip）。"""
    python = sys.executable or shutil.which("python3") or shutil.which("python") or "python3"
    return [python, "-m", "pip", "install", "--quiet"]


def check_python_version():
    """检查 Python 版本 >= 3.10。"""
    if sys.version_info < MIN_PYTHON:
        print(f"[错误] 需要 Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}，"
              f"当前版本: {sys.version}")
        print("请升级 Python 后重试: https://www.python.org/downloads/")
        sys.exit(1)
    print(f"[✓] Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


def check_tkinter():
    """检查 tkinter 是否可用。"""
    try:
        import tkinter
        print("[✓] tkinter")
        return True
    except ImportError:
        system = platform.system()
        guide = TKINTER_INSTALL_GUIDE.get(system, "请安装 tkinter 后重试。")
        print(f"[✗] tkinter 不可用")
        print(f"\n{guide}\n")
        return False


def parse_version(version_str):
    """从模块 __version__ 或 version 字符串中提取版本号元组。"""
    import re
    nums = re.findall(r"(\d+)", version_str)

    return tuple(int(n) for n in nums[:3])


def check_requirement(import_name, pip_name, constraint, min_version):
    """检查单个依赖是否满足要求。返回 (ok, installed_version)。"""
    try:
        mod = __import__(import_name)
        # 尝试获取版本号
        for attr in ("__version__", "version", "VERSION"):
            ver = getattr(mod, attr, None)
            if isinstance(ver, str):
                break
            if hasattr(ver, "__iter__") and not isinstance(ver, str):
                ver = ".".join(str(x) for x in ver)
                break
        else:
            ver = "未知"
        # 检查版本
        try:
            actual = parse_version(ver)
            if actual >= min_version:
                print(f"[✓] {pip_name} {ver}")
                return True, ver
            else:
                print(f"[✗] {pip_name} {ver} < {constraint}")
                return False, ver
        except Exception:
            print(f"[!] {pip_name} {ver}（无法解析版本，假设可用）")
            return True, ver
    except ImportError:
        print(f"[✗] {pip_name} 未安装")
        return False, None


def install_packages(packages):
    """安装指定的包列表。"""
    if not packages:
        return True
    print(f"\n正在安装: {', '.join(packages)} ...")
    pip = get_pip_cmd()
    try:
        result = subprocess.run(
            pip + packages,
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("[✓] 安装完成")
            return True
        else:
            print(f"[✗] 安装失败:\n{result.stderr.strip()[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        print("[✗] 安装超时，请检查网络连接")
        return False
    except FileNotFoundError:
        print("[✗] 找不到 pip，请先安装 Python 并确保 pip 在 PATH 中")
        return False


def ensure_dependencies(auto_install=False):
    """确保所有依赖就绪。返回 True 表示可以继续启动。"""
    print("\n── 检查运行环境 ──")
    check_python_version()

    if not check_tkinter():
        return False

    print("\n── 检查依赖包 ──")
    missing = []
    outdated = []

    for import_name, pip_name, constraint, min_ver in REQUIREMENTS:
        ok, ver = check_requirement(import_name, pip_name, constraint, min_ver)
        if not ok:
            if ver is None:
                missing.append(pip_name)
            else:
                outdated.append(constraint)

    if not missing and not outdated:
        print("\n[✓] 所有依赖就绪")
        return True

    to_install = missing
    if outdated:
        print(f"\n以下包版本过旧，需要升级: {', '.join(outdated)}")
        to_install = missing + [o.split(">=")[0] for o in outdated]

    if auto_install:
        if install_packages(to_install):
            print("\n[✓] 依赖安装完毕，请重新运行程序")
            sys.exit(0)
        else:
            return False

    # 交互模式
    print(f"\n缺少以下包: {', '.join(to_install)}")
    answer = input("是否自动安装? [Y/n] ").strip().lower()
    if answer in ("", "y", "yes"):
        if install_packages(to_install):
            print("\n[✓] 请重新运行程序以使用已安装的依赖")
            print("    （某些包安装后需要重新导入才能生效）")
            sys.exit(0)
    else:
        print("请手动安装依赖后重试:")
        pip = " ".join(get_pip_cmd())
        print(f"  {pip} {' '.join(to_install)}")
    return False


def launch_app(extra_args=None):
    """启动主程序。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # script_dir 现在是 <temp>/model_fitting/
    # 需要把 <temp>/ 加到 sys.path 才能 import model_fitting
    parent_dir = os.path.dirname(script_dir)

    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    # 同时加上 script_dir 以兼容直接 import
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # 解析参数
    csv_path = None
    use_legacy = False
    args = extra_args or sys.argv[1:]
    filtered = []
    for a in args:
        if a == "--legacy":
            use_legacy = True
        elif a == "--auto":
            continue
        elif a.startswith("--"):
            filtered.append(a)
        else:
            csv_path = a
            filtered.append(a)

    # 启动
    print("\n── 启动分布拟合工具 ──\n")
    try:
        if use_legacy:
            from model_fitting.model_fitting_app import launch
            launch(dataframe=None, csv_path=csv_path)
        else:
            from model_fitting.run import launch
            launch(dataframe=None, csv_path=csv_path)
    except Exception as e:
        print(f"\n[错误] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    auto = "--auto" in sys.argv

    if not ensure_dependencies(auto_install=auto):
        sys.exit(1)

    launch_app()


if __name__ == "__main__":
    main()
