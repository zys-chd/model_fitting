# 架构总览（v2 — MVP 重构）

## 设计模式

**MVP（Model-View-Presenter）+ 策略模式（ABC + Registry）**

```
┌──────────────┐     调用      ┌──────────────────┐     渲染     ┌──────────────┐
│   View (UI)  │ ───────────→ │   Presenter       │ ──────────→ │   View (UI)  │
│  AppWindow   │              │  (纯 Python)      │             │  display_*() │
│  (tk.Toplevel)│ ←─────────── │  FittingPresenter │              │              │
└──────────────┘   推送数据    └────────┬─────────┘              └──────────────┘
                                       │
                          ┌────────────┼────────────┐
                          ▼            ▼            ▼
                   ┌──────────┐ ┌──────────┐ ┌──────────┐
                   │ Services │ │ Plotting │ │ Models   │
                   │ (纯逻辑) │ │ (纯绘图) │ │ (拟合)   │
                   └──────────┘ └──────────┘ └──────────┘
```

## 模块职责

```
model_fitting/
├── presenter.py              # 🎯 MVP Presenter — 核心协调器（纯 Python）
├── model_fitting_app.py      # 🔄 旧版窗口（向后兼容，保留）
├── config.py                 # ⚙️ 全局常量
├── utils.py                  # 🔧 工具函数
│
├── services/                 # 🔬 业务逻辑层（零 GUI 依赖）
│   ├── data_service.py       # 数据加载/列检测/过滤
│   ├── fitting_service.py    # 拟合调度/离群检测
│   ├── stats_service.py      # 统计量计算
│   ├── export_service.py     # 导出逻辑
│   │
│   ├── transform_registry.py       # 🧩 变换模式策略（CDF / lnln）
│   ├── stat_registry.py            # 🧩 统计指标计算器
│   ├── file_handler_registry.py    # 🧩 文件格式处理器
│   ├── outlier_registry.py         # 🧩 离群检测策略
│   ├── cdf_estimator_registry.py   # 🧩 经验 CDF 估计器
│   └── export_handler_registry.py  # 🧩 导出格式处理器
│
├── plotting/                 # 🎨 绘图层（依赖 matplotlib，不依赖 tkinter）
│   ├── plot_data.py          # FitResult / PlotSpec / SeriesPlotData dataclass
│   └── plot_manager.py       # PlotManager: build_figure()
│
├── ui/                       # 🖥️ 视图层（依赖 tkinter）
│   ├── app_window.py         # AppWindow 主窗口（实现 AppViewProtocol）
│   └── widgets/
│       └── series_selector.py # SeriesSelector 组件
│
├── models/                   # 📊 分布模型（ABC + 策略模式）
│   ├── base.py               # DistributionModel ABC（含 @abstractmethod）
│   ├── __init__.py            # MODEL_INSTANCES 注册中心
│   └── *.py                  # 9 个分布模型
│
├── tests/                    # 🧪 单元测试套件
│   ├── conftest.py
│   ├── test_services/        # 扩展点 + Service 测试
│   ├── test_plotting/        # 绘图测试
│   ├── test_presenter/       # Presenter 测试
│   └── test_integration/     # 集成测试
│
├── run.py                    # 🚀 入口
└── docs/                     # 📖 文档
```

## 六大扩展点（ABC + Registry）

| 扩展点 | ABC 类 | Registry | 新增方式 |
|--------|--------|----------|---------|
| 变换模式 | `TransformStrategy` | `TRANSFORM_REGISTRY` | 继承 + 注册一行 |
| 统计指标 | `StatCalculator` | `STAT_REGISTRY` | 继承 + 注册 + 加入 Composite |
| 文件格式 | `FileFormatHandler` | `FILE_HANDLERS` | 继承 + 加入列表 |
| 离群检测 | `OutlierDetector` | `OUTLIER_REGISTRY` | 继承 + 注册一行 |
| CDF 估计 | `CDFEstimator` | `CDF_ESTIMATOR_REGISTRY` | 继承 + 注册一行 |
| 导出格式 | `ExportHandler` | `EXPORT_REGISTRY` | 继承 + 注册一行 |

## 核心数据流 (MVP)

```
用户操作 → View 回调 → Presenter 方法 → Service 层 → 结果 → View 渲染

具体步骤（update_all）：
1. View.get_selected_columns() → [(idx, col_name), ...]
2. View.get_series_styles() → [{marker, linestyle, limit}, ...]
3. FittingService.fit_single(samples, model_key) → FitResult
4. StatsService.compute_all(samples, ...) → stats dict
5. PlotManager.build_figure(PlotSpec) → matplotlib Figure
6. View.display_plot(figure) → 嵌入 TkAgg 画布
7. View.display_stats(data) → 更新统计树
```

## 类层次

```
tk.Toplevel
  ├── Model_Fitting_App          # 旧版窗口（向后兼容）
  └── AppWindow                  # 新版 MVP 窗口

FittingPresenter                 # 协调器（纯 Python）

ttk.Frame
  └── SeriesSelector             # 数值列选择组件

DistributionModel (ABC)          # 模型抽象基类（含 @abstractmethod）
  ├── WeibullModel
  ├── Weibull3PModel
  ├── ExponentialModel
  ├── LognormalModel
  ├── NormalModel
  ├── GammaModel
  ├── LogLogisticModel
  ├── GumbelModel
  └── BirnbaumSaundersModel

TransformStrategy (ABC)          # 变换策略
  ├── CDFTransform
  └── LnLnTransform

StatCalculator (ABC)             # 统计计算器
  ├── BasicStatsCalculator
  └── FitAtLimitCalculator

FileFormatHandler (ABC)          # 文件格式处理器
  ├── CSVHandler
  ├── ExcelHandler
  ├── ParquetHandler
  └── JSONHandler

OutlierDetector (ABC)            # 离群检测器
  ├── MADOutlierDetector
  ├── ZScoreOutlierDetector
  └── IQROutlierDetector

CDFEstimator (ABC)               # CDF 估计器
  ├── MedianRankEstimator
  ├── MeanRankEstimator
  └── KaplanMeierEstimator

ExportHandler (ABC)              # 导出处理器
  ├── CSVExportHandler
  ├── JSONExportHandler
  └── ExcelExportHandler
```
        │
        ▼
  pd.read_csv / pd.read_excel
        │
        ▼
  detect_columns(df)        ← utils.py: 自动识别 PART_ID、group、数值列
        │
        ▼
  _apply_dataframe(df)      ← 设置 self.data / value_columns / group_column
        │                   ← 更新所有 SeriesSelector 的 combobox 选项
        │
        ▼
  update_plot()             ← 核心渲染入口
        │
        ├──► 按 group_column 分组
        │
        ├──► 遍历 self.selectors，对每个选中的列：
        │       │
        │       ▼
        │     _fit_plot(ax, model, samples, ...)
        │       │
        │       ├──► model.fit(samples)
        │       │       ├── prepare_cdf_data()    ← 排序 + 中位秩 CDF
        │       │       ├── curve_fit(_cdf_func)  ← scipy 拟合
        │       │       └── compute_r_squared()   ← 计算 R²
        │       │
        │       ├──► ax.scatter(xs, cdf)          ← 散点
        │       ├──► ax.plot(xf, model.cdf(...))  ← 拟合曲线
        │       │
        │       ├──► self.fit_results[key] = (...) ← 缓存拟合结果
        │       └──► self.stats_cache[key] = _stats(samples)  ← 统计量
        │
        ├──► _embed_canvas()         ← 嵌入 FigureCanvasTkAgg
        ├──► _apply_visibility()     ← 图例和显示/隐藏
        ├──► _setup_interaction()    ← 单击选点 / 右键框选 / 双击查看
        └──► _update_stats_tree()    ← 填充统计信息 Treeview
```

## 事件回调链

```
用户操作                        触发方法                        效果
──────────────────────────────────────────────────────────────────────
打开 CSV              →  _load_data           →  _apply_dataframe → update_plot
传入 DataFrame        →  load_dataframe       →  _apply_dataframe → update_plot
切换模型下拉框         →  _on_model_change     →  update_plot
切换变换/坐标轴        →  update_plot          →  重绘全部
添加/移除列           →  add_selector / remove →  update_plot
Selector 列切换       →  _on_selection_change  →  update_plot
Selector 样式变更     →  _on_style_change      →  update_plot
手动去除离群点(右键)   →  _on_box_select       →  _confirm_remove → update_plot
自动去除离群点         →  _on_auto_remove      →  update_plot
恢复数据               →  _on_restore          →  update_plot
统计树点击 checkbox    →  _on_tree_click       →  _apply_visibility → 重绘图例
绘图区单击选点         →  on_pick              →  _highlight_selected（高亮）
绘图区双击             →  on_dbl               →  _show_popup（弹窗）
```

## 多实例机制

`Model_Fitting_App` 继承 `tk.Toplevel`，天然支持多窗口：

- 通过全局计数器 `_max_instance_id` + 释放池 `_freed_instance_ids` 管理实例 ID
- 每个实例独立日志文件：`log/model_fitting_XXX.log`
- 关闭时调用 `plt.close("all")` 防止 matplotlib 引用泄漏
- 从 `test_app.py` 宿主窗口打开的多个子窗口，由 `_child_windows` 列表跟踪

## 两种运行模式

| 特性 | 嵌入模式 | 独立模式 |
|---|---|---|
| 创建方式 | `Model_Fitting_App(parent=host)` | `launch(csv_path=...)` |
| 父窗口 | 外部 tk 窗口 | 隐藏的 `tk.Tk()` 根窗口 |
| 事件循环 | 共享宿主 mainloop | `app._tk_root.mainloop()`（阻塞） |
| 关闭行为 | `self.destroy()` | `self._tk_root.quit()` + `destroy()` |
| 图标设置 | `self.winfo_toplevel()` | `self._tk_root` |

## 配置文件关键常量

| 常量 | 位置 | 说明 |
|---|---|---|
| `FONT_FAMILY` / `FONT_SIZE` | `config.py` | 全局字体，菜单在此基础上 +2 |
| `MAX_SERIES` | `config.py` | 最多同时显示的列数（默认 4） |
| `COLORS` | `config.py` | 分组颜色（tab10 色板） |
| `SCALE_MAP` | `config.py` | 坐标轴缩放：线性/对数 |
| `TRANSFORM_OPTIONS` | `config.py` | 变换模式：CDF / ln(-ln(1-CDF)) |
| `MODEL_KEYS` | `config.py` | 模型内部标识列表 |
| `MODEL_DISPLAY` | `config.py` | 模型 UI 显示名（与 KEYS 一一对应） |
| `GROUP_CANDIDATES` | `config.py` | 分组列自动检测关键词 |
| `ID_CANDIDATES` | `config.py` | ID 列自动检测关键词 |
