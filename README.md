# 分布拟合工具 (Distribution Fitting Tool)

基于 Python 的可靠性工程分布拟合 GUI 工具，支持 9 种分布模型、交互式数据选择、离群点去除、limit 分析。


## 功能特性

- **9 种分布模型**：Weibull (2P/3P)、Exponential、Lognormal、Normal、Gamma、LogLogistic、Gumbel、Birnbaum-Saunders
- **交互式绘图**：散点图 + 拟合曲线，支持 CDF / ln(-ln(1-CDF)) 变换
- **多列多分组**：同时对比多列数据、多个分组
- **离群点处理**：右键框选手动去除 / 自动统计去除 / 数据恢复
- **Limit 分析**：绘制 limit 竖线，计算 F(limit) 值
- **可见性控制**：统计树 checkbox 独立控制每组数据显示/隐藏
- **样式自定义**：每列独立设置 marker / linestyle / 颜色 / 透明度 / 大小，支持 ✎ 配置按钮弹窗
- **描述性统计**：样本数、均值、标准差、中位数、自定义分位数、分位数间距、相对分位数间距、最小值、最大值、偏度、变异系数
- **统计项筛选**：ComboBox 勾选显示/隐藏各项统计，导出可选仅导出显示项
- **导出**：图表导出 (PNG/PDF/SVG) / 参数导出 (Excel/CSV/JSON)
- **C Launcher 打包**：~700KB 独立 exe，自动检测环境、静默安装依赖、无黑框
- **多实例**：可在同一进程中打开多个窗口，各自独立日志

## 运行环境

- Python 3.10+
- 依赖见 `requirements.txt`

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（新版 UI）
python run.py

# 启动（经典 tkinter 模式）
python run.py --classic

# 带 CSV 数据启动
python run.py data.csv
```

### 打包为独立 exe

使用内置 C Launcher，打包为 ~700KB 独立二进制文件（不需预装 Python）：

```bash
python launcher/pack.py
# 输出: launcher/模型拟合工具.exe
```

详见 [launcher/PORTING.md](launcher/PORTING.md)

---

## 添加自定义分布模型

详见 [docs/add-model.md](docs/add-model.md)，3 步即可新增：创建模型文件 → 注册到 `models/__init__.py` → 注册到 `config.py`。

---

## 文档

| 文档 | 说明 |
|---|---|
| [docs/add-model.md](docs/add-model.md) | 添加自定义分布模型 — 代码模板 + 注册步骤 |
| [docs/architecture.md](docs/architecture.md) | 架构总览 — 模块职责、数据流、事件回调链、UI 布局 |
| [docs/add-statistic.md](docs/add-statistic.md) | 添加自定义统计指标 — 3 步新增，含 context 参数速查 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 常见问题 — 拟合失败、打包异常、中文乱码等排查 |

---

## 项目结构

```
model_fitting/
├── run.py                 # 主入口
├── bootstrap.py           # C Launcher 入口
├── config.py              # 全局配置（字体、颜色、模型注册表）
├── presenter.py           # MVP Presenter 层
├── utils.py               # 工具函数
├── widgets.py             # 可复用 UI 组件（SeriesSelector）
├── VERSION                # 版本号文件
├── requirements.txt       # 依赖
├── build.bat              # PyInstaller 打包脚本
├── README.md
├── launcher/              # C Launcher 打包工具
│   ├── config.h           # 项目配置
│   ├── launcher.c         # C 启动器源码
│   ├── pack.py            # 打包脚本
│   └── PORTING.md         # 移植文档
├── core/                  # 核心层
├── ui/                    # UI 层
│   ├── app_window.py      # 主窗口
│   └── widgets/           # UI 组件
│       ├── style_config_dialog.py
│       ├── data_workbook.py
│       ├── import_dialog.py
│       └── series_selector.py
├── models/                # 9 种分布模型
├── services/              # 业务服务层
├── plotting/              # 绘图层
├── docs/                  # 文档
├── tests/                 # 测试
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

## 一键打包

```bash
build.bat
```

生成 `dist/model_fitting.exe`（约 74 MB）。

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
