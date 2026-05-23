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
- 依赖：`numpy scipy pandas matplotlib`

```bash
pip install numpy scipy pandas matplotlib
```

## 快速开始

```bash
# 直接运行
python app.py

# 带 CSV 参数
python run.py data.csv

# 作为模块调用
python -c "from app import launch; launch(csv_path='data.csv')"
```

**代码调用：**

```python
from app import launch, App
import pandas as pd

# 方式1：launch() + DataFrame
launch(dataframe=pd.read_csv("data.csv"))

# 方式2：launch() + CSV 路径
launch(csv_path="data.csv")

# 方式3：App 作为子窗口嵌入
app = App(parent=root, dataframe=df)
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
from app import App

root = tk.Tk()
app = App(parent=root, dataframe=df)  # 直接传入 DataFrame
root.mainloop()
```

也支持 `from app import launch` 独立启动（自带事件循环）。

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
