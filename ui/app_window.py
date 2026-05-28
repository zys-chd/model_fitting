"""
AppWindow — MVP 视图层主窗口

实现 AppViewProtocol，组合所有 UI 组件，委托 Presenter 处理业务逻辑。
"""
import sys
import os
import logging
import logging.handlers
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# ---- 导入配置与组件 ----
try:
    from ..config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                          SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                          MODEL_DISPLAY, MODEL_KEY_MAP, FILTER_KEEP_SHIFT_ONLY_DEFAULT)
    from ..widgets import SeriesSelector
    from ..presenter import FittingPresenter
except ImportError:
    from config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                        SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                        MODEL_DISPLAY, MODEL_KEY_MAP, FILTER_KEEP_SHIFT_ONLY_DEFAULT)
    from widgets import SeriesSelector
    from presenter import FittingPresenter

logger = logging.getLogger("model_fitting.ui")


# ---- 实例 ID 管理（与旧代码兼容） ----
_max_instance_id = 0
_freed_instance_ids: set = set()


def _acquire_instance_id():
    global _max_instance_id
    if _freed_instance_ids:
        return min(_freed_instance_ids)
    _max_instance_id += 1
    return _max_instance_id


def _release_instance_id(iid: int):
    _freed_instance_ids.add(iid)


def _app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return _app_dir()


def _read_version():
    vpath = os.path.join(_data_dir(), "VERSION")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


def _setup_logger(iid):
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(instance)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(ch)

    log_dir = os.path.join(_app_dir(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"model_fitting_{iid:03d}.log")
    fh = logging.handlers.RotatingFileHandler(
        log_path, encoding="utf-8", maxBytes=5 * 1024 * 1024, backupCount=3,
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] instance-%(instance)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    adapter = logging.LoggerAdapter(logger, {"instance": f"#{iid:03d}"})
    return adapter, fh


class AppWindow(tk.Toplevel):
    """
    MVP 视图层主窗口。

    职责：
    - 构建 UI 布局（菜单栏、控制面板、图表区域、统计树）
    - 收集用户输入并转发给 Presenter
    - 接收 Presenter 推送的结果并渲染到界面
    - 不含任何拟合/数据处理逻辑
    """

    def __init__(self, parent=None, dataframe=None, presenter=None):
        self._instance_id = _acquire_instance_id()
        self._log, self._log_fh = _setup_logger(self._instance_id)
        _freed_instance_ids.discard(self._instance_id)
        self._standalone = parent is None
        if self._standalone:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            super().__init__(self._tk_root)
        else:
            super().__init__(parent)
        self.title("分布拟合工具")
        self.geometry("1650x900")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style(self)
        style.configure(".", font=(FONT_FAMILY, FONT_SIZE))

        # Presenter 注入
        self._presenter = presenter or FittingPresenter(view=self)

        # UI 状态
        self.selectors: list[SeriesSelector] = []
        self._tk_vars = {}  # StringVar 字典
        self._canvas: FigureCanvasTkAgg | None = None
        self._toolbar = None
        self._current_figure: Figure | None = None

        # 交互状态
        self._active_selector_idx: int | None = None
        self._selected_points: list = []
        self._filter_shift_only = tk.BooleanVar(value=FILTER_KEEP_SHIFT_ONLY_DEFAULT)

        self._build_ui()
        self.add_selector()
        if dataframe is not None:
            self.after(100, lambda: self._presenter.load_dataframe(dataframe))
        self.after(100, self._apply_app_icon)

    # ==================== View 协议实现 ====================

    def get_selected_columns(self) -> list:
        return [(s.idx, s.get_selection()) for s in self.selectors if s.get_selection()]

    def get_series_styles(self) -> list:
        return [{
            "marker": s.get_marker(),
            "linestyle": s.get_linestyle(),
            "limit": s.get_limit(),
        } for s in self.selectors]

    def get_model_selection(self) -> str:
        return self._tk_vars.get("model", tk.StringVar(value=MODEL_DISPLAY[0])).get()

    def get_transform_selection(self) -> str:
        return self._tk_vars.get("transform", tk.StringVar(value="cdf")).get()

    def get_x_scale(self) -> str:
        return self._tk_vars.get("x_scale", tk.StringVar(value="线性")).get()

    def get_y_scale(self) -> str:
        return self._tk_vars.get("y_scale", tk.StringVar(value="线性")).get()

    def get_theme(self) -> str:
        return self._tk_vars.get("theme", tk.StringVar(value="default")).get()

    def get_x_limits(self) -> tuple:
        try:
            xl = self._tk_vars.get("xlim_min", tk.StringVar(value="")).get()
            xr = self._tk_vars.get("xlim_max", tk.StringVar(value="")).get()
            return (float(xl) if xl else None, float(xr) if xr else None)
        except ValueError:
            return (None, None)

    def get_y_limits(self) -> tuple:
        try:
            yb = self._tk_vars.get("ylim_min", tk.StringVar(value="")).get()
            yt = self._tk_vars.get("ylim_max", tk.StringVar(value="")).get()
            return (float(yb) if yb else None, float(yt) if yt else None)
        except ValueError:
            return (None, None)

    def display_plot(self, figure: Figure) -> None:
        """嵌入 matplotlib Figure 到 TkAgg 画布"""
        if self._canvas:
            self._canvas.get_tk_widget().destroy()
        if self._toolbar:
            self._toolbar.destroy()
            self._toolbar = None

        self._current_figure = figure
        self._canvas = FigureCanvasTkAgg(figure, master=self._canvas_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        try:
            if not hasattr(self, '_toolbar_frame'):
                self._toolbar_frame = ttk.Frame(self._canvas_frame)
                self._toolbar_frame.pack(fill=tk.X, padx=4, pady=2, side=tk.BOTTOM)
            self._toolbar = NavigationToolbar2Tk(self._canvas, self._toolbar_frame)
            self._toolbar.update()
        except Exception:
            pass

        self._setup_matplotlib_interaction()

    def display_formula(self, formula_latex: str) -> None:
        """更新公式显示"""
        if hasattr(self, '_formula_ax'):
            self._formula_ax.clear()
            self._formula_ax.axis("off")
            self._formula_ax.text(
                0.5, 0.5, f"${formula_latex}$",
                transform=self._formula_ax.transAxes,
                fontsize=14, ha="center", va="center",
            )
            if hasattr(self, '_formula_fig'):
                self._formula_fig.canvas.draw_idle()

    def display_stats(self, stats_tree_data: list) -> None:
        """更新统计树"""
        t = self._stats_tree
        for item in t.get_children():
            t.delete(item)
        if not stats_tree_data:
            t.insert("", tk.END, text="无数据", values=("",))
            return

        for item in stats_tree_data:
            chk = "☑" if item.get("visible", True) else "☐"
            col = item["col"]
            grp = item.get("group", "All")
            gt = grp if grp != "All" else "(全部)"
            col_node = t.insert("", tk.END, text=f"{chk} {col}", values=("",), open=True)
            grp_node = t.insert(col_node, tk.END, text=f"{chk} {gt}", values=("",), open=True, tags=("group",))
            t.insert(grp_node, tk.END, text="模型", values=(item.get("model_name", ""),))
            t.insert(grp_node, tk.END, text="R²", values=(f"{item.get('r_squared', 0):.6f}",))
            for pn, pv in item.get("params", []):
                t.insert(grp_node, tk.END, text=pn, values=(f"{pv:.6g}",))
            for lbl, val in item.get("stats", {}).items():
                t.insert(grp_node, tk.END, text=lbl,
                         values=(f"{val:.6g}" if isinstance(val, float) else str(val),))

    def update_mode_label(self, mode: str, text: str) -> None:
        if hasattr(self, '_mode_label'):
            self._mode_label.config(text=text, foreground="red" if mode == "remove" else "#555555")

    def refresh_ui(self) -> None:
        pass

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message, parent=self)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message, parent=self)

    def ask_save_path(self, **options) -> str | None:
        return filedialog.asksaveasfilename(parent=self, **options)

    def ask_open_path(self, **options) -> str | None:
        return filedialog.askopenfilename(parent=self, **options)

    def get_max_series(self) -> int:
        return MAX_SERIES

    def get_series_count(self) -> int:
        return len(self.selectors)

    def update_series_columns(self, columns: list) -> None:
        for s in self.selectors:
            s.update_columns(columns)

    # ==================== UI 构建 ====================

    def _build_ui(self):
        if getattr(sys, 'frozen', False):
            try:
                import pyi_splash
                pyi_splash.close()
            except Exception:
                pass

        self._build_menu()
        self._build_top_bar()
        self._build_middle_area()
        self._log.debug("UI 构建完成")

    def _build_menu(self):
        menu_font = (FONT_FAMILY, FONT_SIZE + 2)
        menubar = tk.Menu(self, font=menu_font)

        # 文件
        fm = tk.Menu(menubar, tearoff=0, font=menu_font)
        fm.add_command(label="读取数据", command=self._on_load_data)
        fm.add_command(label="生成测试数据", command=lambda: self._presenter.generate_test_data())
        fm.add_separator()
        fm.add_command(label="导出模板", command=self._on_export_template)
        fm.add_separator()
        fm.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=fm, font=menu_font)

        # 数据
        dm = tk.Menu(menubar, tearoff=0, font=menu_font)
        dm.add_command(label="添加列", command=self.add_selector)
        dm.add_command(label="移除列", command=self.remove_last)
        dm.add_separator()
        dm.add_command(label="导出图", command=self._on_export_image)
        dm.add_command(label="导出参数", command=self._on_export_parameters)
        model_sub = tk.Menu(dm, tearoff=0, font=menu_font)
        self._tk_vars["model"] = tk.StringVar(value=MODEL_DISPLAY[0])
        for md in MODEL_DISPLAY:
            model_sub.add_radiobutton(
                label=md, variable=self._tk_vars["model"], value=md,
                command=lambda m=md: self._on_model_change(m),
            )
        dm.add_cascade(label="模型选择", menu=model_sub)
        menubar.add_cascade(label="数据", menu=dm, font=menu_font)

        # 绘图
        pm = tk.Menu(menubar, tearoff=0, font=menu_font)
        x_sub = tk.Menu(pm, tearoff=0, font=menu_font)
        self._tk_vars["x_scale"] = tk.StringVar(value="线性")
        for s in SCALE_DISPLAY:
            x_sub.add_radiobutton(label=s, variable=self._tk_vars["x_scale"], value=s,
                                  command=lambda v=s: self._presenter.set_x_scale(v))
        pm.add_cascade(label="X 轴缩放", menu=x_sub)
        y_sub = tk.Menu(pm, tearoff=0, font=menu_font)
        self._tk_vars["y_scale"] = tk.StringVar(value="线性")
        for s in SCALE_DISPLAY:
            y_sub.add_radiobutton(label=s, variable=self._tk_vars["y_scale"], value=s,
                                  command=lambda v=s: self._presenter.set_y_scale(v))
        pm.add_cascade(label="Y 轴缩放", menu=y_sub)
        th_sub = tk.Menu(pm, tearoff=0, font=menu_font)
        self._tk_vars["theme"] = tk.StringVar(value="default")
        themes = ["default", "ggplot", "seaborn-v0_8", "bmh", "fivethirtyeight", "dark_background", "classic"]
        for t in themes:
            th_sub.add_radiobutton(label=t, variable=self._tk_vars["theme"], value=t,
                                   command=lambda v=t: self._presenter.set_theme(v))
        pm.add_cascade(label="主题切换", menu=th_sub)
        menubar.add_cascade(label="绘图", menu=pm, font=menu_font)

        # 关于
        am = tk.Menu(menubar, tearoff=0, font=menu_font)
        am.add_command(label=f"版本: {_read_version()}")
        menubar.add_cascade(label="关于", menu=am, font=menu_font)

        self.config(menu=menubar)

    def _build_top_bar(self):
        tf = ttk.Frame(self)
        tf.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        # 数据选择（SeriesSelector 容器）
        self._selector_frame = ttk.LabelFrame(tf, text="数据选择")
        self._selector_frame.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        self._selector_inner = ttk.Frame(self._selector_frame)
        self._selector_inner.pack()

        # 数据控制面板
        c = ttk.LabelFrame(tf, text="数据控制")
        c.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        self._build_control_panel(c)

        # 绘图控制面板
        pc = ttk.LabelFrame(tf, text="绘图控制")
        pc.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        self._build_plot_control(pc)

    def _build_control_panel(self, c):
        r = 0
        ttk.Button(c, text="添加列", command=self.add_selector).grid(row=r, column=0, sticky="w", padx=1)
        ttk.Button(c, text="移除列", command=self.remove_last).grid(row=r, column=1, sticky="w", padx=1)
        ttk.Button(c, text="导出图", command=self._on_export_image).grid(row=r, column=2, sticky="w", padx=1)
        ttk.Button(c, text="导出参数", command=self._on_export_parameters).grid(row=r, column=3, sticky="w", padx=1)
        r += 1

        ttk.Checkbutton(c, text="仅保留 _shift 列", variable=self._filter_shift_only,
                        command=self._on_filter_shift_toggle).grid(
            row=r, column=0, columnspan=4, sticky="w", padx=2)
        r += 1

        LW = 5
        ttk.Label(c, text="模型：", width=LW, anchor="e").grid(row=r, column=0, sticky="e")
        mc = ttk.Combobox(c, textvariable=self._tk_vars.get("model", tk.StringVar(value=MODEL_DISPLAY[0])),
                          values=MODEL_DISPLAY, state="readonly", width=24)
        mc.grid(row=r, column=1, sticky="w")
        mc.bind("<<ComboboxSelected>>", lambda e: self._on_model_change(self._tk_vars["model"].get()))
        self._tk_vars["model_combo"] = mc

        ttk.Label(c, text="变换：", width=LW, anchor="e").grid(row=r, column=2, sticky="e", padx=(4, 1))
        self._tk_vars["transform"] = tk.StringVar(value="cdf")
        tc = ttk.Combobox(c, textvariable=self._tk_vars["transform"],
                          values=["CDF", "ln(-ln(1-CDF))"], state="readonly", width=12)
        tc.grid(row=r, column=3, sticky="w")
        tc.bind("<<ComboboxSelected>>", lambda e: self._on_transform_change())
        r += 1

        # 公式显示
        self._formula_fig = Figure(figsize=(4.5, 0.55), dpi=100)
        self._formula_fig.set_facecolor("#f0f0f0")
        self._formula_ax = self._formula_fig.add_subplot(111)
        self._formula_ax.axis("off")
        self._formula_canvas = FigureCanvasTkAgg(self._formula_fig, master=c)
        self._formula_canvas.get_tk_widget().grid(row=r, column=0, columnspan=4, sticky="ew", pady=(1, 0))

    def _build_plot_control(self, pc):
        r = 0
        LW = 5
        ttk.Label(pc, text="X 轴：", width=LW, anchor="e").grid(row=r, column=0, sticky="e")
        xc = ttk.Combobox(pc, textvariable=self._tk_vars["x_scale"],
                          values=SCALE_DISPLAY, state="readonly", width=6)
        xc.grid(row=r, column=1, sticky="w")
        xc.bind("<<ComboboxSelected>>", lambda e: self._presenter.set_x_scale(self._tk_vars["x_scale"].get()))

        ttk.Label(pc, text="Y 轴：", width=LW, anchor="e").grid(row=r, column=2, sticky="e")
        yc = ttk.Combobox(pc, textvariable=self._tk_vars["y_scale"],
                          values=SCALE_DISPLAY, state="readonly", width=6)
        yc.grid(row=r, column=3, sticky="w")
        yc.bind("<<ComboboxSelected>>", lambda e: self._presenter.set_y_scale(self._tk_vars["y_scale"].get()))

        ttk.Label(pc, text="主题：", width=LW, anchor="e").grid(row=r, column=4, sticky="e")
        th = ttk.Combobox(pc, textvariable=self._tk_vars["theme"],
                          values=["default", "ggplot", "seaborn-v0_8", "bmh", "fivethirtyeight", "dark_background", "classic"],
                          state="readonly", width=12)
        th.grid(row=r, column=5, sticky="w")
        th.bind("<<ComboboxSelected>>", lambda e: self._presenter.set_theme(self._tk_vars["theme"].get()))
        r += 1

        ttk.Label(pc, text="X 范围：", width=LW, anchor="e").grid(row=r, column=0, sticky="e")
        self._tk_vars["xlim_min"] = tk.StringVar(value="")
        ttk.Entry(pc, textvariable=self._tk_vars["xlim_min"], width=LW*2).grid(row=r, column=1, sticky="w")
        ttk.Label(pc, text="~").grid(row=r, column=2)
        self._tk_vars["xlim_max"] = tk.StringVar(value="")
        ttk.Entry(pc, textvariable=self._tk_vars["xlim_max"], width=LW*2).grid(row=r, column=3, sticky="w")
        r += 1

        ttk.Label(pc, text="Y 范围：", width=LW, anchor="e").grid(row=r, column=0, sticky="e")
        self._tk_vars["ylim_min"] = tk.StringVar(value="")
        ttk.Entry(pc, textvariable=self._tk_vars["ylim_min"], width=LW*2).grid(row=r, column=1, sticky="w")
        ttk.Label(pc, text="~").grid(row=r, column=2)
        self._tk_vars["ylim_max"] = tk.StringVar(value="")
        ttk.Entry(pc, textvariable=self._tk_vars["ylim_max"], width=LW*2).grid(row=r, column=3, sticky="w")
        r += 1

        ttk.Button(pc, text="应用范围", command=self._on_apply_limits).grid(
            row=r, column=0, columnspan=6, sticky="ew", pady=2)

    def _build_middle_area(self):
        m = ttk.Frame(self)
        m.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        pf = ttk.LabelFrame(m, text="图表")
        pf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._canvas_frame = ttk.Frame(pf)
        self._canvas_frame.pack(fill=tk.BOTH, expand=True)

        sf = ttk.LabelFrame(m, text="统计信息")
        sf.pack(side=tk.LEFT, fill=tk.BOTH, padx=4, pady=4, ipadx=2)
        self._mode_label = ttk.Label(sf, text="", font=(FONT_FAMILY, 8), foreground="#555555", anchor=tk.W)
        self._mode_label.pack(fill=tk.X, padx=2, pady=(0, 2))
        tc = ttk.Frame(sf)
        tc.pack(fill=tk.BOTH, expand=True)
        self._stats_tree = ttk.Treeview(tc, columns=("值",), show="tree headings", height=22)
        self._stats_tree.heading("值", text="值")
        self._stats_tree.column("#0", width=160, anchor="w", stretch=False)
        self._stats_tree.column("值", width=180, anchor="w", stretch=False)
        sy = ttk.Scrollbar(tc, orient=tk.VERTICAL, command=self._stats_tree.yview)
        sx = ttk.Scrollbar(tc, orient=tk.HORIZONTAL, command=self._stats_tree.xview)
        self._stats_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self._stats_tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        tc.grid_rowconfigure(0, weight=1)
        tc.grid_columnconfigure(0, weight=1)
        self._stats_tree.bind("<MouseWheel>", lambda e: self._stats_tree.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    # ==================== 选择器管理 ====================

    def add_selector(self):
        if len(self.selectors) >= MAX_SERIES:
            messagebox.showinfo("已达上限", f"最多支持 {MAX_SERIES} 列", parent=self)
            return
        columns = self._presenter._state.value_columns if self._presenter._state.data is not None else []
        s = SeriesSelector(
            self._selector_inner, columns, len(self.selectors),
            remove_callback=self._on_remove_selector,
            manual_remove_callback=self._on_manual_remove,
            auto_remove_callback=self._on_auto_remove,
            restore_callback=self._on_restore,
            selection_change_callback=lambda sel: self._presenter.update_all(),
            style_change_callback=lambda sel: self._presenter.update_all(),
        )
        s.pack(fill=tk.X, pady=1)
        self.selectors.append(s)
        self._presenter.update_all()

    def remove_last(self):
        if self.selectors:
            self.selectors.pop().destroy()
            self._presenter.update_all()

    def _on_remove_selector(self, s):
        if s in self.selectors:
            self.selectors.remove(s)
            s.destroy()
            self._presenter.update_all()

    # ==================== 回调方法 ====================

    def _on_load_data(self):
        path = filedialog.askopenfilename(
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")], parent=self,
        )
        if path:
            self._presenter.load_file(path)

    def _on_model_change(self, display_name):
        key = MODEL_KEY_MAP.get(display_name, "Weibull")
        self._presenter.set_model(key)

    def _on_transform_change(self):
        val = self._tk_vars["transform"].get()
        key = "cdf" if val == "CDF" else "lnln"
        self._presenter.set_transform(key)

    def _on_apply_limits(self):
        self._presenter.set_axis_limits(self.get_x_limits(), self.get_y_limits())

    def _on_filter_shift_toggle(self):
        self._presenter.set_filter_shift_only(self._filter_shift_only.get())

    def _on_manual_remove(self, sel: SeriesSelector):
        self._active_selector_idx = sel.idx if self._active_selector_idx != sel.idx else None
        self.update_mode_label(
            "remove" if self._active_selector_idx is not None else "normal",
            f"⚠ 手动去除模式" if self._active_selector_idx is not None else "● 普通模式",
        )

    def _on_auto_remove(self, sel: SeriesSelector):
        col = sel.get_selection()
        if not col:
            return
        cnt = self._presenter.auto_remove_outliers(sel.idx, col)
        messagebox.showinfo("自动去除", f"列 {col} 已自动去除 {cnt} 个离群点。", parent=self)

    def _on_restore(self, sel: SeriesSelector = None):
        self._presenter.restore_data()
        messagebox.showinfo("恢复", "数据已恢复到最初加载状态。", parent=self)

    def _on_export_image(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg"), ("JPG", "*.jpg"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self._presenter.export_image(path)

    def _on_export_parameters(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self._presenter.export_parameters(path)

    def _on_export_template(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile="fitting_template.csv",
            parent=self,
        )
        if not path:
            return
        try:
            template = pd.DataFrame({
                "PART_ID": [f"P{i:03d}" for i in range(1, 11)],
                "group": ["GroupA"] * 5 + ["GroupB"] * 5,
                "IDSS1": [1.2, 1.5, 1.3, 1.8, 1.6, 2.1, 2.4, 1.9, 2.2, 2.6],
            })
            template.to_csv(path, index=False)
            messagebox.showinfo("导出模板", f"模板已保存至：\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("导出错误", str(e), parent=self)

    # ==================== matplotlib 交互 ====================

    def _setup_matplotlib_interaction(self):
        if not self._canvas:
            return

        def on_pick(event):
            if len(event.ind) == 0:
                return
            # 收集选中点信息
            sel_points = []
            for i in event.ind:
                sel_points.append({
                    "df_idx": i,
                    "x_raw": float(event.artist.get_offsets()[i, 0]),
                    "y_cdf": float(event.artist.get_offsets()[i, 1]),
                })

        self._canvas.mpl_connect("pick_event", on_pick)

    # ==================== 清理 ====================

    def _on_close(self):
        self._log.info("窗口关闭")
        if self._canvas:
            try:
                self._canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self._canvas = None
        if self._toolbar:
            try:
                self._toolbar.destroy()
            except Exception:
                pass
            self._toolbar = None
        plt.close("all")
        if hasattr(self, "_log_fh") and self._log_fh:
            try:
                self._log_fh.close()
            except Exception:
                pass
            logger.removeHandler(self._log_fh)
            self._log_fh = None
        _release_instance_id(self._instance_id)
        if self._standalone:
            self._tk_root.quit()
            self._tk_root.destroy()
        else:
            self.destroy()

    def _apply_app_icon(self):
        ico = os.path.join(_data_dir(), "model_fitting.ico")
        if not os.path.exists(ico):
            return
        try:
            self.iconbitmap(default=ico)
        except Exception:
            pass
