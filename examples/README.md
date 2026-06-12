# 示例目录说明

本文件夹包含将本项目作为 Python package 在外部调用时的示例代码和打包脚本，方便快速上手与集成。

## 文件清单

| 文件 | 说明 |
|------|------|
| `test_app.py` | 测试启动器，演示 `Model_Fitting_App` 的多种启动方式 |
| `build_test.bat` | 一键打包脚本，使用 PyInstaller 将测试工具打包为独立 exe |
| `mf.ico` | 打包用的图标文件 |
| `model_fitting.ico` | 应用图标文件 |
| `model_fitting.png` | 启动闪屏图片 |

## test_app.py — 测试启动器

`TestHost` 是一个 tkinter 宿主窗口，演示了两种集成模式：

### 嵌入模式（App 作为子窗口）

将 `Model_Fitting_App` 嵌入到已有的 tkinter 应用中：

```py
from model_fitting.model_fitting_app import Model_Fitting_App

# 空窗口
app = Model_Fitting_App(parent=self)

# 加载 CSV 文件
app = Model_Fitting_App(parent=self)
app.load_csv("path/to/data.csv")

# 直接传入 DataFrame
import pandas as pd
df = pd.read_csv("path/to/data.csv")
app = Model_Fitting_App(parent=self, dataframe=df)
```

### 独立模式（launch 函数）

使用 `launch()` 函数独立启动，自带事件循环（阻塞直到窗口关闭）：

```py
from model_fitting.model_fitting_app import launch

# 传入 CSV 路径
launch(csv_path="path/to/data.csv")

# 传入 DataFrame
launch(dataframe=df)
```

## build_test.bat — 打包脚本

将 `test_app.py` 打包为独立的 Windows 可执行文件（`.exe`）。

使用方式：在项目根目录下运行 `examples\build_test.bat`，脚本会自动：
1. 创建/检查虚拟环境
2. 安装依赖
3. 清理旧构建
4. 使用 PyInstaller 打包，输出至 `dist\` 目录

## 快速开始

1. 安装依赖：
   ```sh
   pip install -r requirements.txt
   ```
2. 运行测试启动器：
   ```sh
   python examples/test_app.py
   ```
3. 或打包为 exe：
   ```sh
   examples\build_test.bat
   ```
