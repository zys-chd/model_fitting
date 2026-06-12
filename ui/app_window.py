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
    from ..widgets import MARKER_ICONS as _M_ICONS
    from ..widgets import LINESTYLE_ICONS as _L_ICONS
    from ..presenter import FittingPresenter
    from .widgets.style_config_dialog import StyleConfigDialog
    from .widgets.data_workbook import DataWorkbook
except ImportError:
    from config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                        SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                        MODEL_DISPLAY, MODEL_KEY_MAP, FILTER_KEEP_SHIFT_ONLY_DEFAULT)
    from widgets import SeriesSelector
    from widgets import MARKER_ICONS as _M_ICONS
    from widgets import LINESTYLE_ICONS as _L_ICONS
    from presenter import FittingPresenter
    from .widgets.style_config_dialog import StyleConfigDialog
    from .widgets.data_workbook import DataWorkbook
except ImportError:
    from config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                        SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                        MODEL_DISPLAY, MODEL_KEY_MAP, FILTER_KEEP_SHIFT_ONLY_DEFAULT)
    from widgets import SeriesSelector
    from widgets import MARKER_ICONS as _M_ICONS
    from widgets import LINESTYLE_ICONS as _L_ICONS
    from presenter import FittingPresenter
    from ui.widgets.style_config_dialog import StyleConfigDialog

# matplotlib 值 → 图标映射
_MARKER_VAL_TO_ICON = dict(zip(['o','s','^','D','v','p','*','X','h','H','d','P','<','>'], _M_ICONS))
_LINESTYLE_VAL_TO_ICON = dict(zip(['-','--',':','-.'], _L_ICONS))

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
        self.title(f"分布拟合工具 v{_read_version()}")
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
        self._highlight_artists: list = []
        self._box_start = None
        self._box_patch = None
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
            "scatter_alpha": s.get_scatter_alpha(),
            "curve_alpha": s.get_curve_alpha(),
            "marker_size": s.get_marker_size(),
            "line_width": s.get_line_width(),
            "cycle_marker": s.cycle_marker_var.get(),
            "cycle_linestyle": s.cycle_linestyle_var.get(),
            "custom_color": s.custom_color_var.get(),
        } for s in self.selectors]

    def get_series_config(self) -> list:
        """返回完整系列配置（供会话保存）"""
        return [{
            "col": s.get_selection(),
            "marker": s.get_marker(),
            "linestyle": s.get_linestyle(),
            "limit": s.get_limit(),
            "scatter_alpha": s.get_scatter_alpha(),
            "curve_alpha": s.get_curve_alpha(),
            "marker_size": s.get_marker_size(),
            "line_width": s.get_line_width(),
            "cycle_marker": s.cycle_marker_var.get(),
            "cycle_linestyle": s.cycle_linestyle_var.get(),
            "custom_color": s.custom_color_var.get(),
        } for s in self.selectors]

    def restore_series_config(self, config: list) -> None:
        """根据配置恢复系列选择器（供会话加载）"""
        for s in self.selectors:
            s.destroy()
        self.selectors.clear()

        columns = self._presenter._state.value_columns
        for i, cfg in enumerate(config):
            s = SeriesSelector(
                self._selector_inner, columns, i,
                remove_callback=self._on_remove_selector,
                manual_remove_callback=self._on_manual_remove,
                auto_remove_callback=self._on_auto_remove,
                restore_callback=self._on_restore,
                selection_change_callback=lambda sel: self._presenter.update_all(),
                style_change_callback=lambda sel: self._presenter.update_all(),
                config_callback=self._on_open_style_config,
            )
            # 恢复列选择
            if cfg.get("col") and cfg["col"] in columns:
                s.var.set(cfg["col"])
            # 恢复样式
            style_dict = {
                "marker_icon": _MARKER_VAL_TO_ICON.get(cfg.get("marker"), "●"),
                "ls_icon": _LINESTYLE_VAL_TO_ICON.get(cfg.get("linestyle"), "────"),
                "limit": cfg.get("limit", 0.1),
                "scatter_alpha": cfg.get("scatter_alpha", 1.0),
                "curve_alpha": cfg.get("curve_alpha", 1.0),
                "marker_size": cfg.get("marker_size", 6),
                "line_width": cfg.get("line_width", 2),
                "cycle_marker": cfg.get("cycle_marker", True),
                "cycle_linestyle": cfg.get("cycle_linestyle", True),
                "custom_color": cfg.get("custom_color", ""),
            }
            s.apply_style_dict(style_dict)
            s.pack(fill=tk.X, pady=1)
            self.selectors.append(s)

    def sync_controls_from_state(self, state: dict) -> None:
        """同步 View 控件与 Presenter 状态（供会话加载）"""
        # 模型下拉
        model_key = state.get("model_key", "Weibull")
        from config import MODEL_KEY_MAP, MODEL_DISPLAY
        display_name = {v: k for k, v in MODEL_KEY_MAP.items()}.get(model_key, MODEL_DISPLAY[0])
        if "model" in self._tk_vars:
            self._tk_vars["model"].set(display_name)

        # 变换下拉
        transform_key = state.get("transform_key", "cdf")
        t_val = "CDF" if transform_key == "cdf" else "ln(-ln(1-CDF))"
        if "transform" in self._tk_vars:
            self._tk_vars["transform"].set(t_val)

        # X/Y 轴
        self._tk_vars.get("x_scale", tk.StringVar()).set(state.get("x_scale", "线性"))
        self._tk_vars.get("y_scale", tk.StringVar()).set(state.get("y_scale", "线性"))

        # 主题
        self._tk_vars.get("theme", tk.StringVar()).set(state.get("theme", "default"))

        # 范围
        xl = state.get("x_limits", [None, None])
        yl = state.get("y_limits", [None, None])
        self._tk_vars.get("xlim_min", tk.StringVar()).set(str(xl[0]) if xl[0] is not None else "")
        self._tk_vars.get("xlim_max", tk.StringVar()).set(str(xl[1]) if xl[1] is not None else "")
        self._tk_vars.get("ylim_min", tk.StringVar()).set(str(yl[0]) if yl[0] is not None else "")
        self._tk_vars.get("ylim_max", tk.StringVar()).set(str(yl[1]) if yl[1] is not None else "")

        # shift 过滤
        self._filter_shift_only.set(state.get("filter_shift_only", False))

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
        """更新统计树，含散点/曲线独立 checkbox（按列分组）"""
        t = self._stats_tree
        for item in t.get_children():
            t.delete(item)
        if not stats_tree_data:
            t.insert("", tk.END, text="无数据", values=("",))
            return

        # 按列分组
        by_col: dict = {}
        for item in stats_tree_data:
            by_col.setdefault(item["col"], []).append(item)

        for col, items in sorted(by_col.items()):
            # 计算列整体可见性
            col_all_scat = all(it.get("scatter_visible", True) for it in items)
            col_all_curv = all(it.get("curve_visible", True) for it in items)
            col_all_vis = col_all_scat and col_all_curv
            col_chk = "☑" if col_all_vis else "☐"
            col_node = t.insert("", tk.END, text=f"{col_chk} {col}", values=("",), open=True)

            for item in items:
                grp = item.get("group", "All")
                gt = grp if grp != "All" else "(全部)"
                scat_vis = item.get("scatter_visible", True)
                curv_vis = item.get("curve_visible", True)
                all_vis = scat_vis and curv_vis

                # 分组节点
                grp_chk = "☑" if all_vis else "☐"
                grp_node = t.insert(col_node, tk.END, text=f"{grp_chk} {gt}",
                                    values=("",), open=True, tags=("group",))

                # 散点子节点
                scat_chk = "☑" if scat_vis else "☐"
                t.insert(grp_node, tk.END, text=f"{scat_chk} 散点",
                         values=("",), tags=("scatter_toggle",))

                # 曲线子节点
                curv_chk = "☑" if curv_vis else "☐"
                t.insert(grp_node, tk.END, text=f"{curv_chk} 拟合曲线",
                         values=("",), tags=("curve_toggle",))

                # 模型信息
                t.insert(grp_node, tk.END, text="模型", values=(item.get("model_name", ""),))
                t.insert(grp_node, tk.END, text="R²", values=(f"{item.get('r_squared', 0):.6f}",))
                for pn, pv in item.get("params", []):
                    t.insert(grp_node, tk.END, text=pn, values=(f"{pv:.6g}",))
                for lbl, val in item.get("stats", {}).items():
                    if self._presenter._state.visible_stats is not None and lbl not in self._presenter._state.visible_stats:
                        continue
                    t.insert(grp_node, tk.END, text=lbl,
                             values=(f"{val:.6g}" if isinstance(val, float) else str(val),))
        # 刷新统计过滤 Combobox
        self._refresh_stat_filter_combo()

    def _on_stats_tree_click(self, event):
        """点击统计树切换显示/隐藏"""
        item = self._stats_tree.identify_row(event.y)
        if not item:
            return
        text = self._stats_tree.item(item, "text")
        tags = self._stats_tree.item(item, "tags")
        parent = self._stats_tree.parent(item)
        grandparent = self._stats_tree.parent(parent) if parent else None

        # 散点/曲线子节点
        if "scatter_toggle" in tags:
            col, grp = self._resolve_col_group(item, parent, grandparent)
            if col:
                self._presenter.toggle_scatter_visibility(col, grp)
            return
        if "curve_toggle" in tags:
            col, grp = self._resolve_col_group(item, parent, grandparent)
            if col:
                self._presenter.toggle_curve_visibility(col, grp)
            return

        # 分组节点（"group" tag）：切换整体系列
        if "group" in tags:
            col_text = self._stats_tree.item(parent, "text") if parent else ""
            col = col_text[2:].strip() if col_text.startswith(("\u2611", "\u2610")) else col_text.strip()
            grp = text[2:].strip() if text.startswith(("\u2611", "\u2610")) else text.strip()
            if grp == "(全部)":
                grp = "All"
            if col:
                self._presenter.toggle_visibility(col, grp)
            return

        # 列节点（无 parent）：切换整列
        if not parent:
            col = text[2:].strip() if text.startswith(("\u2611", "\u2610")) else text.strip()
            if col:
                self._presenter.toggle_column_visibility(col)

    def _resolve_col_group(self, item, parent, grandparent):
        """从 Treeview 节点解析 col / group 名称"""
        grp_text = self._stats_tree.item(parent, "text")
        grp = grp_text[2:].strip() if grp_text[:1] in ("☑", "☐") else grp_text.strip()
        if grp == "(全部)":
            grp = "All"
        if grandparent:
            col_text = self._stats_tree.item(grandparent, "text")
            col = col_text[2:].strip() if col_text[:1] in ("☑", "☐") else col_text.strip()
        else:
            col = ""
        return col, grp

    def update_mode_label(self, mode: str, text: str) -> None:
        if hasattr(self, '_mode_label'):
            self._mode_label.config(text=text, foreground="red" if mode == "remove" else "#555555")

    def refresh_ui(self) -> None:
        pass

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self)

    def show_fit_errors(self, errors: list) -> None:
        """汇总显示拟合异常（一次弹窗）"""
        if not errors:
            return
        deduped = list(dict.fromkeys(errors))  # 去重保序
        max_show = 10
        shown = deduped[:max_show]
        msg = "\n".join(f"• {e}" for e in shown)
        if len(deduped) > max_show:
            msg += f"\n\n... 还有 {len(deduped) - max_show} 条异常"
        messagebox.showwarning("拟合提醒", msg, parent=self)

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
        fm.add_command(label="读取数据（新窗口）", command=self._on_load_data_new_window)
        fm.add_command(label="附加数据", command=self._on_append_data)
        fm.add_command(label="自定义读取", command=self._on_custom_import)
        fm.add_command(label="生成测试数据", command=lambda: self._presenter.generate_test_data())
        fm.add_separator()
        fm.add_command(label="保存会话   Ctrl+S", command=self._on_save_session)
        fm.add_command(label="加载会话   Ctrl+O", command=self._on_load_session)
        fm.add_separator()
        fm.add_command(label="导出模板", command=self._on_export_template)
        fm.add_separator()
        fm.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=fm, font=menu_font)

        # 数据
        dm = tk.Menu(menubar, tearoff=0, font=menu_font)
        dm.add_command(label="数据工作簿", command=self._on_open_workbook)
        dm.add_separator()
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
        pm.add_separator()
        pm.add_command(label="取消选中", command=self._clear_selection)
        pm.add_command(label="绘制 limit 线", command=self._draw_limit_lines)
        menubar.add_cascade(label="绘图", menu=pm, font=menu_font)

        # 关于
        am = tk.Menu(menubar, tearoff=0, font=menu_font)
        am.add_command(label="分布拟合工具", command=None)
        am.add_separator()
        am.add_command(label="支持模型（点击查看详情）：")
        for md in MODEL_DISPLAY:
            am.add_command(
                label=f"  {md}", command=lambda m=md: self._show_model_info(m),
            )
        am.add_separator()
        am.add_command(label="统计信息计算方法", command=self._show_stats_info)
        am.add_separator()
        am.add_command(label=f"版本: {_read_version()}")
        menubar.add_cascade(label="关于", menu=am, font=menu_font)

        self.config(menu=menubar)
        self.bind_all("<Control-s>", lambda e: self._on_save_session())
        self.bind_all("<Control-o>", lambda e: self._on_load_session())

    def _build_top_bar(self):
        tf = ttk.Frame(self)
        tf.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        tf.columnconfigure([0,1,2], weight=1)

        # 数据选择（SeriesSelector 容器）
        self._selector_frame = ttk.LabelFrame(tf, text="数据选择")
        self._selector_frame.grid(column=0, row=0, sticky="nswe", padx=4, pady=4)
        self._selector_inner = ttk.Frame(self._selector_frame)
        self._selector_inner.pack()

        # 数据控制面板
        c = ttk.LabelFrame(tf, text="数据控制")
        c.grid(column=1, row=0, sticky="nswe", padx=4, pady=4)
        self._build_control_panel(c)

        # 绘图控制面板
        pc = ttk.LabelFrame(tf, text="绘图控制")
        pc.grid(column=2, row=0, sticky="nswe", padx=4, pady=4)
        self._build_plot_control(pc)

    def _build_control_panel(self, c):
        c.columnconfigure(0, weight=1)
        c.columnconfigure(1, weight=1)
        c.columnconfigure(2, weight=1)
        c.columnconfigure(3, weight=1)
        r = 0
        LW = 5
        ttk.Button(c, text="数据工作簿", command=self._on_open_workbook).grid(
            row=r, column=0, columnspan=2, sticky="ew", padx=1)
        ttk.Button(c, text="导出图", command=self._on_export_image).grid(row=r, column=2, sticky="w", padx=1)
        ttk.Button(c, text="导出参数", command=self._on_export_parameters).grid(row=r, column=3, sticky="w", padx=1)
        r += 1
        ttk.Button(c, text="添加列", command=self.add_selector).grid(row=r, column=0, sticky="w", padx=1)
        ttk.Button(c, text="移除列", command=self.remove_last).grid(row=r, column=1, sticky="w", padx=1)

        # 分位数 Entry（同行）
        self._tk_vars["quantile_low"] = tk.StringVar(value="5")
        self._tk_vars["quantile_high"] = tk.StringVar(value="95")
        ttk.Label(c, text=" 分位数:").grid(row=r, column=2, sticky="w", padx=(4, 0))
        self._q_low_entry = ttk.Entry(c, textvariable=self._tk_vars["quantile_low"], width=5)
        self._q_low_entry.grid(row=r, column=2, sticky="e", padx=(55, 0))
        self._q_low_entry.bind("<FocusOut>", self._on_quantile_change)
        self._q_low_entry.bind("<Return>", self._on_quantile_change)
        ttk.Label(c, text="~").grid(row=r, column=3, sticky="w")
        self._q_high_entry = ttk.Entry(c, textvariable=self._tk_vars["quantile_high"], width=5)
        self._q_high_entry.grid(row=r, column=3, sticky="w", padx=(12, 0))
        self._q_high_entry.bind("<FocusOut>", self._on_quantile_change)
        self._q_high_entry.bind("<Return>", self._on_quantile_change)
        ttk.Label(c, text="%").grid(row=r, column=3, sticky="w", padx=(48, 0))
        r += 1

        ttk.Checkbutton(c, text="仅保留 _shift 列", variable=self._filter_shift_only,
                        command=self._on_filter_shift_toggle).grid(
            row=r, column=0, sticky="w", padx=2)
        # 导出筛选 Checkbutton
        self._export_filtered = tk.BooleanVar(value=False)
        ttk.Checkbutton(c, text="仅导出显示项", variable=self._export_filtered).grid(
            row=r, column=1, sticky="w", padx=2)
        # 统计项显示选择 Combobox
        ttk.Label(c, text="统计：", width=LW, anchor="e").grid(row=r, column=2, sticky="e", padx=(4, 1))
        self._stat_filter_combo = ttk.Combobox(c, values=["全部显示"], state="readonly", width=12)
        self._stat_filter_combo.set("全部显示")
        self._stat_filter_combo.grid(row=r, column=3, sticky="w")
        self._stat_filter_combo.bind("<<ComboboxSelected>>", self._on_stat_filter_toggle)
        r += 1

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
        pc.columnconfigure([0,1,2,3,4,5], weight=1)
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
            row=r, column=0, columnspan=3, sticky="ew", pady=2)

        r += 1
        ttk.Button(pc, text="取消选中", command=self._clear_selection).grid(
            row=r, column=0, columnspan=3, sticky="ew", pady=2)
        ttk.Button(pc, text="绘制 limit 线", command=self._draw_limit_lines).grid(
            row=r, column=3, columnspan=3, sticky="ew", pady=2)

    def _build_middle_area(self):
        m = ttk.Frame(self)
        m.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        pf = ttk.LabelFrame(m, text="图表")
        pf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._canvas_frame = ttk.Frame(pf)
        self._canvas_frame.pack(fill=tk.BOTH, expand=True)

        sf = ttk.LabelFrame(m, text="统计信息")
        sf.pack(side=tk.LEFT, fill=tk.BOTH, padx=4, pady=4, ipadx=2)
        self._mode_label = ttk.Label(sf, text="● 普通模式 — 单击选点 / 右键框选 / 双击查看数据详情",
                                      font=(FONT_FAMILY, 8), foreground="#555555", anchor=tk.W)
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
        self._stats_tree.bind("<Button-1>", self._on_stats_tree_click, add="+")

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
            config_callback=self._on_open_style_config,
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
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = self._pick_excel_sheet(path)
                if df is None:
                    return
                self._presenter.load_dataframe(df)
            else:
                self._presenter.load_file(path)

    def _on_load_data_new_window(self):
        """在新窗口读取数据"""
        path = filedialog.askopenfilename(
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")], parent=self,
        )
        if path:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = self._pick_excel_sheet(path)
                if df is None:
                    return
                AppWindow(parent=self, dataframe=df)
            else:
                import pandas as pd
                df = pd.read_csv(path)
                AppWindow(parent=self, dataframe=df)

    def _on_append_data(self):
        """附加数据 — 通过自定义导入对话框配置后拼接"""
        if self._presenter.get_dataframe() is None:
            messagebox.showinfo("提示", "请先加载主数据文件", parent=self)
            return
        path = filedialog.askopenfilename(
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")], parent=self,
        )
        if path:
            self._presenter.append_custom_data(path)

    def _on_custom_import(self):
        """自定义数据读取"""
        path = filedialog.askopenfilename(
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"), ("所有文件", "*.*")], parent=self,
        )
        if path:
            self._presenter.import_custom_data(path)

    def _on_save_session(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".rda",
            filetypes=[("会话文件", "*.rda"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self._presenter.save_session(path)

    def _on_load_session(self):
        path = filedialog.askopenfilename(
            filetypes=[("会话文件", "*.rda"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self._presenter.load_session(path)

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
        col = sel.get_selection()
        self._active_selector_idx = sel.idx if self._active_selector_idx != sel.idx else None
        if self._active_selector_idx is not None:
            self.update_mode_label(
                "remove",
                f"⚠ 手动去除「{col}」— 单击选点 / 右键框选 / 双击确认去除 （再点「手动去除」退出）",
            )
        else:
            self.update_mode_label(
                "normal",
                "● 普通模式 — 单击选点 / 右键框选 / 双击查看数据详情",
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
            defaultextension=".xlsx",
            filetypes=[("Excel 文件", "*.xlsx"), ("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            filter_stats = None
            if self._export_filtered.get():
                vs = self._presenter._state.visible_stats
                if vs is not None:
                    filter_stats = vs
            self._presenter.export_parameters(path, visible_stats=filter_stats)

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
            messagebox.showinfo("导出模板", f"模板已保存至：\\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("导出错误", str(e), parent=self)

    # ==================== 样式配置对话框 ====================

    def _on_open_workbook(self):
        """打开数据工作簿"""
        df = self._presenter.get_dataframe()
        if df is None:
            messagebox.showinfo("提示", "请先加载数据", parent=self)
            return
        dlg = DataWorkbook(
            self, df,
            group_column=self._presenter._state.group_column,
            title=f"数据工作簿 — {self.title()}",
        )
        self._data_workbook = dlg

    def _on_open_style_config(self, selector=None):
        """打开样式配置对话框"""
        if not self.selectors:
            return
        initial_idx = selector.idx if selector is not None and selector in self.selectors else 0

        def _on_apply(full_redraw: bool, palette: str = None):
            """应用回调：full_redraw=True 用 update_all，否则用轻量更新"""
            if palette:
                self._presenter._state.color_palette = palette
            if full_redraw:
                self._presenter.update_all()
            else:
                self._presenter.apply_series_styles()

        dlg = StyleConfigDialog(
            self, self.selectors, initial_idx=initial_idx,
            palette=self._presenter._state.color_palette,
            on_apply=_on_apply,
        )
        self._style_config_dialog = dlg

    # ==================== matplotlib 交互 ====================

    def _setup_matplotlib_interaction(self):
        if not self._canvas or not self._current_figure or not self._current_figure.axes:
            return

        ax = self._current_figure.axes[0]

        def on_pick(event):
            if len(event.ind) == 0:
                return
            sel = self._collect_picked_points(event)
            if not sel:
                return
            if self._active_selector_idx is not None:
                # 手动去除模式：累积选中
                same = [s for s in self._selected_points if s["col"] == sel[0]["col"]]
                ex = {s["point_idx"] for s in same}
                new = [s for s in sel if s["point_idx"] not in ex]
                self._selected_points = same + new
                self._highlight_selected(ax, self._selected_points)
            else:
                self._highlight_selected(ax, sel)
                self._selected_points = sel
            self._canvas.draw_idle()

        # 右键框选
        def on_press(event):
            if event.button == 3 and event.inaxes and event.xdata is not None and event.ydata is not None:
                self._box_start = (event.xdata, event.ydata)

        def on_motion(event):
            if self._box_start and event.inaxes and event.xdata is not None and event.ydata is not None:
                if self._box_patch:
                    self._box_patch.remove()
                x0, y0 = self._box_start
                import matplotlib.patches as mpatches
                self._box_patch = mpatches.Rectangle(
                    (min(x0, event.xdata), min(y0, event.ydata)),
                    abs(event.xdata - x0), abs(event.ydata - y0),
                    fill=True, facecolor="blue", edgecolor="blue", alpha=0.2,
                )
                ax.add_patch(self._box_patch)
                self._canvas.draw_idle()

        def on_release(event):
            if self._box_start:
                if self._box_patch:
                    self._box_patch.remove()
                    self._box_patch = None
                x0, y0 = self._box_start
                x1, y1 = event.xdata, event.ydata
                self._box_start = None
                if x0 is None or y0 is None or x1 is None or y1 is None:
                    return
                xmin, xmax = sorted([x0, x1])
                ymin, ymax = sorted([y0, y1])
                sel = self._box_select_points(xmin, xmax, ymin, ymax)
                if not sel:
                    return
                if self._active_selector_idx is not None:
                    self._highlight_selected(ax, sel)
                    self._canvas.draw_idle()
                    self._confirm_remove(sel)
                else:
                    self._highlight_selected(ax, sel)
                    self._selected_points = sel
                    self._canvas.draw_idle()

        # 双击
        def on_dbl(event):
            if self._selected_points:
                if self._active_selector_idx is not None:
                    self._confirm_remove(list(self._selected_points))
                else:
                    self._show_popup(self._selected_points)

        self._canvas.mpl_connect("pick_event", on_pick)
        self._canvas.mpl_connect("button_press_event", on_press)
        self._canvas.mpl_connect("motion_notify_event", on_motion)
        self._canvas.mpl_connect("button_release_event", on_release)
        self._canvas.get_tk_widget().bind("<Double-Button-1>", on_dbl)

    def _collect_picked_points(self, event) -> list:
        """从 pick_event 收集选中点信息，映射 scatter artist → series_meta"""
        sel = []
        meta_list = self._presenter.get_series_meta()
        ax = self._current_figure.axes[0] if self._current_figure else None
        if not ax:
            return sel

        # 找到 event.artist 对应哪个 collection index
        try:
            coll_idx = list(ax.collections).index(event.artist)
        except ValueError:
            return sel
        if coll_idx >= len(meta_list):
            return sel

        m = meta_list[coll_idx]
        # 检查可见性和 selector
        if m["selector_idx"] != self._active_selector_idx and self._active_selector_idx is not None:
            return sel

        offsets = event.artist.get_offsets()
        df_indices = m.get("df_indices", [])
        for i in event.ind:
            if i >= len(offsets):
                continue
            df_idx = df_indices[i] if i < len(df_indices) else i
            sel.append({
                "col": m["col"],
                "group": m.get("group"),
                "point_idx": int(i),
                "x_raw": float(offsets[i, 0]),
                "y_cdf": float(offsets[i, 1]),
                "df_idx": df_idx,
                "selector_idx": m["selector_idx"],
                "marker": m.get("marker", "o"),
            })
        return sel

    def _box_select_points(self, xmin, xmax, ymin, ymax) -> list:
        """框选范围内的点"""
        sel = []
        meta_list = self._presenter.get_series_meta()
        ax = self._current_figure.axes[0] if self._current_figure else None
        if not ax:
            return sel
        for coll_idx, coll in enumerate(ax.collections):
            if coll_idx >= len(meta_list):
                continue
            m = meta_list[coll_idx]
            if self._active_selector_idx is not None and m["selector_idx"] != self._active_selector_idx:
                continue
            offsets = coll.get_offsets()
            inside = (
                (offsets[:, 0] >= xmin) & (offsets[:, 0] <= xmax) &
                (offsets[:, 1] >= ymin) & (offsets[:, 1] <= ymax)
            )
            df_indices = m.get("df_indices", [])
            for i in np.where(inside)[0]:
                df_idx = df_indices[i] if i < len(df_indices) else i
                sel.append({
                    "col": m["col"],
                    "group": m.get("group"),
                    "point_idx": int(i),
                    "x_raw": float(offsets[i, 0]),
                    "y_cdf": float(offsets[i, 1]),
                    "df_idx": df_idx,
                    "selector_idx": m["selector_idx"],
                    "marker": m.get("marker", "o"),
                })
        return sel

    def _highlight_selected(self, ax, sel: list):
        """高亮选中的点（保持原始 marker 形状）"""
        self._clear_selection()
        if not sel:
            return
        # 按 marker 分组，每组独立 scatter 以保持形状
        from collections import defaultdict
        by_marker = defaultdict(lambda: {"x": [], "y": []})
        for s in sel:
            mk = s.get("marker", "o")
            by_marker[mk]["x"].append(s["x_raw"])
            by_marker[mk]["y"].append(s["y_cdf"])
        for mk, coords in by_marker.items():
            hl = ax.scatter(
                coords["x"], coords["y"],
                s=80, facecolor="none", edgecolor="red",
                linewidth=2, zorder=10, marker=mk,
            )
            self._highlight_artists.append(hl)

    def _clear_selection(self):
        for a in self._highlight_artists:
            a.remove()
        self._highlight_artists.clear()
        self._selected_points.clear()
        if self._canvas:
            self._canvas.draw_idle()

    def _show_popup(self, sel: list):
        """弹窗显示选中数据点详情 — 按列→分组 Treeview，显示 PART_ID/group/值"""
        df = self._presenter.get_dataframe()
        if df is None:
            return

        top = tk.Toplevel(self)
        top.title("数据点详情")

        # 列宽自适应
        cols = ("PART_ID", "值")
        has_part_id = "PART_ID" in df.columns or "part_id" in df.columns
        has_group = self._presenter._state.group_column is not None
        if has_group:
            cols = ("PART_ID", "分组", "值")

        tv = ttk.Treeview(top, columns=cols, show="tree headings", height=min(30, len(sel)))
        tv.heading("#0", text="列")
        for c in cols:
            tv.heading(c, text=c)
        tv.column("#0", width=140, anchor="w")
        tv.column("值", width=120, anchor="e")
        if "PART_ID" in cols:
            tv.column("PART_ID", width=100, anchor="w")
        if "分组" in cols:
            tv.column("分组", width=80, anchor="w")

        # 按列→分组组织
        by_col: dict = {}
        for s in sel:
            by_col.setdefault(s["col"], []).append(s)

        for col_name, items in sorted(by_col.items()):
            cn = tv.insert("", tk.END, text=col_name, values=("", "", "") if len(cols)==3 else ("", ""), open=True)
            by_grp: dict = {}
            for s in items:
                r = df.loc[s["df_idx"]] if s["df_idx"] in df.index else None
                pid = str(r.get("PART_ID", r.get("part_id", f"#{s['df_idx']}"))) if r is not None else f"#{s['df_idx']}"
                g = str(r.get(self._presenter._state.group_column, "-")) if r is not None and has_group else "-"
                val_str = f"{s['x_raw']:.6g}"
                by_grp.setdefault(g, []).append((pid, val_str))
            for g, pts in sorted(by_grp.items()):
                gn = tv.insert(cn, tk.END, text=g, values=("", "", "") if len(cols)==3 else ("", ""), open=True)
                for pid, val in pts:
                    vals = (pid, g, val) if has_group else (pid, val)
                    tv.insert(gn, tk.END, text="", values=vals)

        sy = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tv.yview)
        tv.configure(yscrollcommand=sy.set)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        top.geometry(f"550x{max(240, 140 + min(30, len(sel)) * 22)}")

    def _confirm_remove(self, sel: list):
        """确认并执行去除选中的点 — 显示丰富上下文"""
        df = self._presenter.get_dataframe()
        if df is None:
            return

        has_group = self._presenter._state.group_column is not None
        lines = [f"以下 {len(sel)} 个点将被去除：\n", "-" * 50 + "\n"]
        for i, s in enumerate(sel[:30]):
            pid = ""
            grp_info = ""
            if s["df_idx"] in df.index:
                r = df.loc[s["df_idx"]]
                pid = str(r.get("PART_ID", r.get("part_id", "")))
                if has_group:
                    grp_info = f" [{r.get(self._presenter._state.group_column, '')}]"
            lines.append(f"  #{i+1}: {s['col']}{grp_info}  PID={pid}  值={s['x_raw']:.6g}\n")
        if len(sel) > 30:
            lines.append(f"  ... 还有 {len(sel) - 30} 个\n")
        if messagebox.askyesno("确认去除", "".join(lines), parent=self):
            self._presenter.manual_remove_points(sel)
            self._active_selector_idx = None
            self._clear_selection()
            self.update_mode_label("normal", "● 普通模式 — 单击选点 / 右键框选 / 双击查看数据详情")

    # ==================== 模型分析工具（补齐旧版功能） ====================

    def _pick_excel_sheet(self, path):
        """弹窗让用户选择 Excel 的 sheet，返回 DataFrame 或 None"""
        try:
            xl = pd.ExcelFile(path)
        except Exception as e:
            messagebox.showerror("读取失败", f"无法打开 Excel 文件：\n{e}", parent=self)
            return None
        sheets = xl.sheet_names
        if len(sheets) == 1:
            return pd.read_excel(path, sheet_name=sheets[0])
        dlg = tk.Toplevel(self)
        dlg.title("选择工作表")
        dlg.geometry("320x300")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        result = {"sheet": None}
        ttk.Label(dlg, text=f"文件包含 {len(sheets)} 个工作表，请选择：",
                  font=("Microsoft YaHei", 10)).pack(padx=15, pady=(15, 5))
        lb = tk.Listbox(dlg, font=("Microsoft YaHei", 10), selectmode=tk.SINGLE, height=6)
        for s in sheets:
            lb.insert(tk.END, s)
        lb.selection_set(0)
        lb.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)
        def on_ok():
            sel = lb.curselection()
            if sel:
                result["sheet"] = sheets[sel[0]]
            dlg.destroy()
        btn = ttk.Frame(dlg)
        btn.pack(pady=(5, 10))
        ttk.Button(btn, text="确认", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn, text="取消", command=dlg.destroy).pack(side=tk.LEFT, padx=5)
        self.wait_window(dlg)
        if result["sheet"]:
            return pd.read_excel(path, sheet_name=result["sheet"])
        return None

    def _show_model_info(self, display_name):
        """弹窗显示模型公式和介绍"""
        key = MODEL_KEY_MAP.get(display_name)
        if not key:
            return
        from ..models import MODEL_INSTANCES
        model = MODEL_INSTANCES.get(key)
        if not model:
            return
        formula = model.get_formula()
        desc = model.get_description()

        top = tk.Toplevel(self)
        top.title(display_name)
        top.geometry("520x420")
        top.resizable(False, False)

        # 公式图
        fig = Figure(figsize=(5, 0.7), dpi=100)
        fig.set_facecolor("#f5f5f5")
        fax = fig.add_subplot(111)
        fax.axis("off")
        fax.text(0.5, 0.5, f"${formula}$",
                 transform=fax.transAxes, fontsize=14, ha="center", va="center")
        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.get_tk_widget().pack(fill=tk.X, padx=10, pady=(10, 5))
        canvas.draw()

        ttk.Separator(top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        text = tk.Text(top, wrap=tk.WORD, font=("Microsoft YaHei", 10),
                       padx=10, pady=5, relief=tk.FLAT, bg="#f5f5f5")
        text.insert(tk.END, desc)
        text.config(state=tk.DISABLED)
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))

    def _draw_limit_lines(self):
        """重新绘图并绘制 limit 竖线"""
        self._log.info("绘制 limit 线")
        self._presenter.update_all()
        if not self._current_figure or not self._current_figure.axes:
            self._log.debug("绘制 limit 线: 无数据，跳过")
            return
        ax = self._current_figure.axes[0]
        seen = set()
        for meta in self._presenter.get_series_meta():
            col = meta.get("col", "")
            si = meta.get("selector_idx", -1)
            if si in seen:
                continue
            seen.add(si)
            if si >= len(self.selectors):
                continue
            try:
                limit = self.selectors[si].get_limit()
            except Exception:
                continue
            color = meta.get("color", "blue")
            ax.axvline(x=limit, color=color, linestyle=":", alpha=0.7, linewidth=1.5)
            ax.text(limit, 0.02, f"{col}={limit:.3g}", color=color,
                    fontsize=7, rotation=90, va="bottom", ha="right",
                    transform=ax.get_xaxis_transform())
        if self._canvas:
            self._canvas.draw_idle()

    # ==================== 分位数 + 统计说明 ====================

    def _on_stat_filter_toggle(self, event=None):
        """统计项 Combobox 选择：切换对应项的可见性"""
        sel = self._stat_filter_combo.get()
        if not sel or sel == "全部显示":
            return
        # 去掉前缀 ☑/☐
        label = sel[1:].strip()
        visible = self._presenter.toggle_stat_visibility(label)
        self._refresh_stat_filter_combo(visible)

    def _refresh_stat_filter_combo(self, visible_labels=None):
        """刷新统计过滤 Combobox 的内容（☑显示/☐隐藏）"""
        labels = self._presenter.get_stat_labels()
        if not labels:
            self._stat_filter_combo["values"] = ["全部显示"]
            self._stat_filter_combo.set("全部显示")
            return
        if visible_labels is None:
            vs = self._presenter._state.visible_stats
            visible_labels = list(vs) if vs is not None else labels
        items = []
        for lb in labels:
            prefix = "☑" if lb in visible_labels else "☐"
            items.append(f"{prefix} {lb}")
        self._stat_filter_combo["values"] = items
        self._stat_filter_combo.set("")

    def _on_quantile_change(self, event=None):
        try:
            ql = float(self._tk_vars["quantile_low"].get())
            qh = float(self._tk_vars["quantile_high"].get())
            if 0 <= ql <= 100 and 0 <= qh <= 100 and ql < qh:
                self._presenter.set_quantile_low(ql)
                self._presenter.set_quantile_high(qh)
        except ValueError:
            pass

    def _show_stats_info(self):
        top = tk.Toplevel(self)
        top.title("统计信息计算方法")
        top.geometry("540x500")
        top.resizable(True, True)

        text = tk.Text(top, wrap=tk.WORD, font=("Microsoft YaHei", 10),
                       padx=12, pady=10, relief=tk.FLAT, bg="#f5f5f5")
        info = (
            "样本数 (n)\n"
            "  参与计算的有效数据点个数。\n\n"
            "均值 (Mean)\n"
            "  所有数据的算术平均值。公式: μ = Σxᵢ / n\n\n"
            "标准差 (Std Dev)\n"
            "  数据离散程度的度量。\n"
            "  公式: σ = √(Σ(xᵢ-μ)² / (n-1))   (样本标准差, ddof=1)\n\n"
            "中位数 (Median)\n"
            "  排序后位于中间位置的值。不受极端值影响, 比均值更稳健。\n\n"
            "分位数 (Quantile)\n"
            "  低于该值的数据所占百分比。\n"
            "  例: 5%分位数表示有5%的数据小于该值。\n"
            "  默认 Q_low=5%, Q_high=95%，可在数据控制面板自定义。\n\n"
            "偏度 (Skewness)\n"
            "  数据分布不对称性的度量。\n"
            "  > 0 右偏(长尾在右), < 0 左偏, = 0 对称。\n"
            "  公式: γ₁ = (n/((n-1)(n-2))) × Σ((xᵢ-μ)/σ)³\n"
            "  使用 scipy.stats.skew (Fisher-Pearson 标准化矩系数)\n\n"
            "变异系数 (Coefficient of Variation, CV)\n"
            "  标准差与均值的比值, 消除量纲影响。\n"
            "  公式: CV(%) = (σ / μ) × 100%\n"
            "  用于比较不同量级数据的离散程度。\n"
            "  CV 越小表示数据越集中, 越大表示越分散。\n\n"
            "最小值 / 最大值\n"
            "  数据集中的最小值和最大值。\n\n"
            "limit处F值\n"
            "  在指定 limit 处的拟合 CDF 值 F(limit)。\n"
            "  表示在 limit 值处的累积失效概率。\n"
            "  依赖当前选择的分布模型和拟合参数。"
        )
        text.insert(tk.END, info)
        text.config(state=tk.DISABLED)
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(10, 10))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(10, 10))

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            text.yview_scroll(int(-1 * (event.delta / 120)), "units")
        text.bind("<MouseWheel>", _on_mousewheel)

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
