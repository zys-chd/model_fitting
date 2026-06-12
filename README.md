# 分布拟合工具 (Distribution Fitting Tool)

基于 Python 的可靠性工程分布拟合 GUI 工具，支持 9 种分布模型、交互式数据选择、离群点去除、limit 分析。


## 功能特性

- **9 种分布模型**：Weibull (2P/3P)、Exponential、Lognormal、Normal、Gamma、LogLogistic、Gumbel、Birnbaum-Saunders
- **交互式绘图**：散点图 + 拟合曲线，支持 CDF / ln(-ln(1-CDF)) 变换
- **多列多分组**：同时对比多列数据、多个分组
- **离群点处理**：右键框选手动去除 / 自动统计去除 / 数据恢复
- **Limit 分析**：绘制 limit 竖线，计算 F(limit) 值
- **可见性控制**：统计树 checkbox 独立控制每组数据显示/隐藏
- **样式自定义**：每列独立设置 marker 和 linestyle
- **导出**：图表导出 (PNG/PDF/SVG) / 参数导出 (CSV)
- **多实例**：可在同一进程中打开多个窗口，各自独立日志

## 运行环境

- Python 3.10+
- 依赖见 `requirements.txt`

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
# 直接运行
python model_fitting_app.py

# 带 CSV 参数
python run.py data.csv

# 作为模块调用
python -c "from model_fitting_app import launch; launch(csv_path='data.csv')"
```

**代码调用：**

```python
from model_fitting_app import launch, Model_Fitting_App
import pandas as pd

# 方式1：launch() + DataFrame
launch(dataframe=pd.read_csv("data.csv"))

# 方式2：launch() + CSV 路径
launch(csv_path="data.csv")

# 方式3：嵌入到其他 tkinter 窗口
app = Model_Fitting_App(parent=my_tk_window, dataframe=df)
```

---

## 添加自定义分布模型

详见 [docs/add-model.md](docs/add-model.md)，3 步即可新增：创建模型文件 → 注册到 `models/__init__.py` → 注册到 `config.py`。

---

## 文档

| 文档 | 说明 |
|---|---|
| [docs/add-model.md](docs/add-model.md) | 添加自定义分布模型 — 代码模板 + 注册步骤 |
| [docs/architecture.md](docs/architecture.md) | 架构总览 — 模块职责、数据流、事件回调链、UI 布局 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 常见问题 — 拟合失败、打包异常、中文乱码等排查 |

---

## 项目结构

```
model_fitting/
├── model_fitting_app.py   # 主窗口 + launch() 入口
├── run.py                 # CLI 入口
├── config.py              # 全局配置（字体、颜色、模型注册表）
├── utils.py               # 工具函数（列检测、测试数据生成）
├── widgets.py             # 可复用 UI 组件（SeriesSelector）
├── VERSION                # 版本号文件
├── requirements.txt       # 依赖
├── README.md
├── docs/
│   ├── add-model.md       # 添加自定义模型指南
│   ├── architecture.md    # 架构总览
│   └── troubleshooting.md # 常见问题
├── models/
│   ├── __init__.py        # 模型注册中心
│   ├── base.py            # 抽象基类 DistributionModel
│   ├── weibull.py         # Weibull-2P
│   ├── weibull3p.py       # Weibull-3P
│   ├── exponential.py     # Exponential
│   ├── lognormal.py       # Lognormal
│   ├── normal.py          # Normal
│   ├── gamma.py           # Gamma
│   ├── loglogistic.py     # Log-Logistic
│   ├── gumbel.py          # Gumbel
│   └── birnbaum_saunders.py  # Birnbaum-Saunders
└── log/                   # 运行日志
```

## 数据格式

CSV 文件需包含至少一列数值数据，可选 `PART_ID` 列和分组列：

| PART_ID | group | IDSS1 | IDSS2 | ... |
|---------|-------|-------|-------|-----|
| P001 | GroupA | 1.2 | 3.4 | ... |

- **PART_ID**：可选，用于数据点详情弹窗显示
- **分组列**：自动检测非数值列（或含 `group` 关键词的列）作为分组
- **数值列**：其余数值列作为可选测试项

从菜单 `文件 > 导出模板` 可生成示例 CSV。

## 作为模块嵌入

```python
import tkinter as tk
from model_fitting_app import Model_Fitting_App

root = tk.Tk()
app = Model_Fitting_App(parent=root, dataframe=df)
root.mainloop()
```

也支持 `from model_fitting_app import launch` 独立启动。

详见 `test_app.py`。

## 打包发布

### 方式一：C Launcher（推荐，~730 KB）

将项目资源 ZIP 嵌入 C 程序，运行时解压到临时目录，调用系统 Python 执行。
依赖缺失时自动 `pip install`，退出后清理临时目录。

**前置条件：** 目标机器需安装 Python 3.10+（不需要预装任何包）

```bash
# 打包（需要 C 编译器 + zlib）
python pack.py

# 输出: launcher/model_fitting (macOS/Linux) 或 model_fitting.exe (Windows)
```

**工作原理：**
1. `pack.py` 将项目文件压缩为 ZIP，转为 C 数组，编译为独立二进制
2. 运行时解压到系统临时目录
3. 调用系统 `python3 bootstrap.py --auto`
4. `bootstrap.py` 检查 tkinter 和依赖（numpy, scipy, pandas, matplotlib, pillow, openpyxl, xlrd），缺则自动安装
5. 启动主程序
6. 退出时自动清理临时目录

**体积对比：**

| 方案 | 体积 | 需预装 |
|------|------|--------|
| PyInstaller | ~74 MB | 无 |
| C Launcher | ~730 KB | Python 3.10+ |

### 方式二：PyInstaller（传统）

```bash
build.bat
```

生成 `dist/model_fitting.exe`（约 74 MB）。包含完整 Python 运行时，无需目标机器安装任何环境。

## 项目结构

```
model_fitting/
├── app.py              # 主应用（~1300 行）
├── widgets.py          # 可复用 UI 组件
├── config.py           # 全局配置
├── utils.py            # 工具函数
├── models/             # 分布模型包
│   ├── base.py         # 基类
│   ├── weibull.py      # Weibull 2P
│   ├── weibull3p.py    # Weibull 3P
│   ├── exponential.py
│   ├── lognormal.py
│   ├── normal.py
│   ├── gamma.py
│   ├── loglogistic.py
│   ├── gumbel.py
│   └── birnbaum_saunders.py
├── run.py              # 启动器
├── test_app.py         # 嵌入测试
├── build.bat           # 打包脚本
├── VERSION             # 版本号
└── log/                # 运行日志（自动创建）
```
