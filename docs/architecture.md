# 架构总览

## 模块职责

```
model_fitting/
├── model_fitting_app.py   # 🎯 主窗口 + 编排层
├── config.py              # ⚙️ 全局常量（字体、颜色、模型注册表）
├── utils.py               # 🔧 工具函数（列检测、测试数据生成）
├── widgets.py             # 🧩 UI 组件（SeriesSelector）
├── models/
│   ├── base.py            # 📐 抽象基类 DistributionModel
│   ├── __init__.py        # 📋 模型注册中心 MODEL_INSTANCES
│   └── *.py               # 📊 各分布模型实现
├── run.py                 # 🚀 CLI 入口
├── VERSION                # 🏷 版本号
└── log/                   # 📝 运行日志
```

## 类层次

```
tk.Toplevel
  └── Model_Fitting_App          # 主窗口（继承 Toplevel，可独立或嵌入）

ttk.Frame
  └── SeriesSelector             # 数值列选择组件（每列一个实例）

DistributionModel (ABC)          # 模型抽象基类
  ├── WeibullModel
  ├── Weibull3PModel
  ├── ExponentialModel
  ├── LognormalModel
  ├── NormalModel
  ├── GammaModel
  ├── LogLogisticModel
  ├── GumbelModel
  └── BirnbaumSaundersModel
```

## UI 布局

```
┌──────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 数据 | 绘图 | 关于                      │
├───────────────┬──────────────────┬───────────────────┤
│  数值列        │  数据控制          │  绘图控制           │
│  ┌──────────┐ │  模型: [▼]       │  X轴: [▼] Y轴: [▼] │
│  │Selector 0│ │  变换: [▼]       │  主题: [▼]          │
│  │Selector 1│ │  [添加列][移除列] │  X范围: [_]~[_]    │
│  │  ...     │ │  [导出图][导出参数]│  Y范围: [_]~[_]    │
│  └──────────┘ │  ┌─公式显示──┐   │  [取消选中][应用范围]│
│               │  │ F(x)=...  │   │  [绘制limit线]     │
│               │  └──────────┘   │                    │
├───────────────┴──────────────────┴───────────────────┤
│  图表 (matplotlib FigureCanvasTkAgg)                  │
│  ┌────────────────────────────────────────────────┐  │
│  │           散点 + 拟合曲线                         │  │
│  │           CDF / ln(-ln(1-CDF))                  │  │
│  └────────────────────────────────────────────────┘  │
│  [matplotlib 工具栏: 缩放/平移/保存]                   │
├──────────────────────────────────────────────────────┤
│  统计信息 (ttk.Treeview)         │ 模式提示 (mode_label)│
│  ☑ IDSS1                        │                     │
│    ☑ GroupA  模型: Weibull      │                     │
│              R²: 0.9876          │                     │
│              β: 1.52             │                     │
│              η: 48.3             │                     │
│              样本数: 40           │                     │
│              ...                 │                     │
└──────────────────────────────────┴─────────────────────┘
```

## 核心数据流

```
load_csv / load_dataframe
        │
        ▼
  _load_data(path)          ← 文件对话框 or launch(csv_path=)
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
