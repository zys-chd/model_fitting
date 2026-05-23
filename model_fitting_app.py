"""
主窗口 App 类 — 分布拟合工具的 UI 编排
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

# ---- 日志配置（延迟初始化，App 创建时才激活） ----
logger = logging.getLogger("model_fitting.app")
logger.setLevel(logging.DEBUG)

_max_instance_id = 0
_freed_instance_ids: set = set()


def _acquire_instance_id():
    """获取可用的实例 ID（优先复用已关闭窗口释放的）"""
    global _max_instance_id
    if _freed_instance_ids:
        return min(_freed_instance_ids)
    _max_instance_id += 1
    return _max_instance_id


def _release_instance_id(iid: int):
    """释放实例 ID，供后续新窗口复用"""
    _freed_instance_ids.add(iid)


def _app_dir():
    """获取应用根目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _data_dir():
    """获取打包数据文件目录（PyInstaller --add-data 解压位置）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return _app_dir()

def _read_version():
    """从根目录 VERSION 文件读取版本号"""
    vpath = os.path.join(_data_dir(), "VERSION")
    try:
        with open(vpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.warning("读取 VERSION 文件失败: %s", e)
        return "0.0.0"


def _setup_logger(iid):
    """为指定实例 ID 设置日志，返回 LoggerAdapter（独立日志文件，无竞争）"""

    # 控制台 handler：仅首次添加（所有实例共享）
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(instance)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(ch)

    # 文件 handler：每个实例独立文件，放在 log/ 子目录
    log_dir = os.path.join(_app_dir(), "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"model_fitting_{iid:03d}.log")
    fh = logging.handlers.RotatingFileHandler(
        log_path, encoding="utf-8", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] instance-%(instance)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)

    adapter = logging.LoggerAdapter(logger, {"instance": f"#{iid:03d}"})
    adapter.info("日志文件: %s", log_path)
    return adapter, fh


# ---- 导入（优先相对导入避免联合打包时与其他项目的模块冲突） ----
def _import_modules():
    global detect_columns, generate_test_data, default_test_path
    global FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS
    global SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS, MODEL_DISPLAY, MODEL_KEY_MAP
    global MODEL_INSTANCES, SeriesSelector
    try:
        # 优先相对导入（精确、不与其他项目冲突）
        from .config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                             SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                             MODEL_DISPLAY, MODEL_KEY_MAP)
        from .models import MODEL_INSTANCES
        from .widgets import SeriesSelector
        from .utils import detect_columns, generate_test_data, default_test_path
    except ImportError:
        # 直接运行时回退绝对导入
        from config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                            SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                            MODEL_DISPLAY, MODEL_KEY_MAP)
        from models import MODEL_INSTANCES
        from widgets import SeriesSelector
        from utils import detect_columns, generate_test_data, default_test_path

_import_modules()


def _safe_lnln(cdf_vals):
    """安全的 ln(-ln(1-CDF)) 变换，返回 (transformed, bad_mask)"""
    import warnings

    inner = 1 - np.asarray(cdf_vals)
    with np.errstate(divide="ignore", invalid="ignore"):
        warnings.filterwarnings("ignore", "divide by zero")
        warnings.filterwarnings("ignore", "invalid value")
        inner = np.where(inner <= 0, 1e-300, inner)
        result = np.log(-np.log(inner))
        warnings.resetwarnings()
    return np.nan_to_num(result, nan=-100, posinf=100, neginf=-100)


class Model_Fitting_App(tk.Toplevel):
    """分布拟合工具主窗口"""

    def __init__(self, parent=None, dataframe=None):
        self._instance_id = _acquire_instance_id()
        self._log, self._log_fh = _setup_logger(self._instance_id)
        # 移除已释放 ID 的 handler（复用 ID 时旧 handler 已无效）
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

        self.data = None
        self.original_data = None
        self.columns = []
        self.value_columns = []
        self.group_column = None
        self.selectors = []
        self.models = MODEL_INSTANCES
        self.current_model = "Weibull"
        self.fit_results = {}
        self.stats_cache = {}

        self.figure = None
        self.ax = None
        self.canvas = None
        self.canvas_frame = None
        self.toolbar = None
        self.toolbar_frame = None

        self._plot_meta = []
        self._selected_meta = []
        self._highlight_artists = []
        self._box_start = None
        self._box_patch = None
        self._active_selector_idx = None
        self._visibility = {}  # {(col, group): True/False}
        self._col_legends = {}  # col → column header legend handle

        self._build_ui()
        self.max_series = MAX_SERIES
        self.add_selector()
        if dataframe is not None:
            self.after(100, lambda: self.load_dataframe(dataframe))
        # 窗口需先映射到屏幕才能设置图标（after 等 tk 完成内部映射）
        self.after(100, self._apply_app_icon)

    def _on_close(self):
        self._log.info("窗口关闭")
        # 清理 matplotlib 资源，释放 TkAgg 后端占用的事件循环和引用
        self._cleanup_matplotlib()
        # 释放实例 ID 和日志文件 handler，供后续窗口复用
        self._cleanup_logger()
        _release_instance_id(self._instance_id)
        if self._standalone:
            self._tk_root.quit()
            self._tk_root.destroy()
        else:
            self.destroy()

    def _cleanup_logger(self):
        """移除该实例的日志文件 handler，释放文件句柄"""
        if hasattr(self, "_log_fh") and self._log_fh:
            try:
                self._log_fh.close()
            except Exception:
                pass
            logger.removeHandler(self._log_fh)
            self._log_fh = None

    def _cleanup_matplotlib(self):
        """清理 matplotlib figure / canvas / toolbar，防止进程不退出"""
        if self.toolbar:
            try:
                self.toolbar.destroy()
            except Exception:
                pass
            self.toolbar = None
        if self.canvas:
            try:
                self.canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.canvas = None
        if self.figure:
            plt.close(self.figure)
            self.figure = None
        # 清理公式图
        if hasattr(self, "formula_fig") and self.formula_fig:
            plt.close(self.formula_fig)
            self.formula_fig = None
        # 关闭所有 pyplot 残留 figure，释放 TkAgg 事件循环引用
        plt.close("all")

    @staticmethod
    def _load_app_icon():
        """加载应用图标（.ico），兼容源码和 PyInstaller 打包"""
        ico = os.path.join(_data_dir(), "model_fitting.ico")
        return ico if os.path.exists(ico) else None

    def _apply_app_icon(self):
        """同步设置标题栏 + 任务栏图标"""
        ico = self._load_app_icon()
        if not ico:
            return
        # 标题栏：.ico 直接生效
        try:
            self.iconbitmap(default=ico)
        except Exception as e:
            self._log.debug("iconbitmap 失败: %s", e)
        # 任务栏：iconphoto 必须设置在 master（Tk 根窗口）上
        try:
            from PIL import Image, ImageTk
            img = Image.open(ico)
            if img.size[0] > 64:
                img = img.resize((32, 32), Image.LANCZOS)
            bg = Image.new("RGBA", img.size, (0, 0, 0, 0))
            img = Image.alpha_composite(bg, img).convert("RGB")
            photo = ImageTk.PhotoImage(img)
            root = self._tk_root if self._standalone else self.winfo_toplevel()
            root.wm_iconphoto(True, photo)
            self._taskbar_photo = photo
        except Exception as e:
            self._log.debug("iconphoto 失败: %s", e)

    # ==================== UI ====================

    def _build_ui(self):
        # Close splash only if running as compiled EXE
        if getattr(sys, 'frozen', False):
            import pyi_splash
            pyi_splash.close()
        self._log.debug("开始构建 UI")
        self._build_menu()
        self._build_top_bar()
        self._build_middle_area()
        self._log.debug("UI 构建完成")

    def _build_menu(self):
        menubar = tk.Menu(self)
        self._menubar = menubar  # 保存引用供状态更新

        # ===== 文件 =====
        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="读取数据", command=self._load_data)
        fm.add_command(label="读取数据（新窗口）", command=self._load_data_new_window)
        fm.add_command(label="生成测试数据", command=self.generate_and_load)
        fm.add_separator()
        fm.add_command(label="导出模板", command=self._export_template)
        fm.add_separator()
        fm.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=fm)

        # ===== 数据 =====
        dm = tk.Menu(menubar, tearoff=0)
        dm.add_command(label="添加列", command=self.add_selector)
        dm.add_command(label="移除列", command=self.remove_last)
        dm.add_separator()
        dm.add_command(label="导出图", command=self.export_image)
        dm.add_command(label="导出参数", command=self.export_parameters)
        dm.add_separator()
        # 模型子菜单
        model_sub = tk.Menu(dm, tearoff=0)
        self._model_radio = tk.StringVar(value=MODEL_DISPLAY[0])
        for md in MODEL_DISPLAY:
            model_sub.add_radiobutton(
                label=md,
                variable=self._model_radio,
                value=md,
                command=lambda m=md: self._menu_set_model(m),
            )
        dm.add_cascade(label="模型选择", menu=model_sub)
        # 变换子菜单
        trans_sub = tk.Menu(dm, tearoff=0)
        self._trans_radio = tk.StringVar(value="CDF")
        for t in TRANSFORM_OPTIONS:
            trans_sub.add_radiobutton(
                label=t,
                variable=self._trans_radio,
                value=t,
                command=lambda v=t: self._menu_set_transform(v),
            )
        dm.add_cascade(label="变换选择", menu=trans_sub)
        menubar.add_cascade(label="数据", menu=dm)

        # ===== 绘图 =====
        pm = tk.Menu(menubar, tearoff=0)
        # X轴缩放
        x_sub = tk.Menu(pm, tearoff=0)
        self._xscale_radio = tk.StringVar(value="线性")
        for s in SCALE_DISPLAY:
            x_sub.add_radiobutton(
                label=s,
                variable=self._xscale_radio,
                value=s,
                command=lambda v=s: self._menu_set_xscale(v),
            )
        pm.add_cascade(label="X 轴缩放", menu=x_sub)
        # Y轴缩放
        y_sub = tk.Menu(pm, tearoff=0)
        self._yscale_radio = tk.StringVar(value="线性")
        for s in SCALE_DISPLAY:
            y_sub.add_radiobutton(
                label=s,
                variable=self._yscale_radio,
                value=s,
                command=lambda v=s: self._menu_set_yscale(v),
            )
        pm.add_cascade(label="Y 轴缩放", menu=y_sub)
        # 主题
        th_sub = tk.Menu(pm, tearoff=0)
        self._theme_radio = tk.StringVar(value="default")
        themes = [
            "default",
            "ggplot",
            "seaborn-v0_8",
            "bmh",
            "fivethirtyeight",
            "dark_background",
            "classic",
        ]
        for t in themes:
            th_sub.add_radiobutton(
                label=t,
                variable=self._theme_radio,
                value=t,
                command=lambda v=t: self._menu_set_theme(v),
            )
        pm.add_cascade(label="主题切换", menu=th_sub)
        pm.add_separator()
        pm.add_command(label="X/Y 范围设置", command=self._menu_range_dialog)
        pm.add_command(label="取消选中", command=self._clear_selection)
        pm.add_command(label="绘制 limit 线", command=self._draw_limit_lines)
        menubar.add_cascade(label="绘图", menu=pm)

        # ===== 关于 =====
        am = tk.Menu(menubar, tearoff=0)
        am.add_command(label="分布拟合工具", command=None)
        am.add_separator()
        am.add_command(label="支持模型（点击查看详情）：")
        for md in MODEL_DISPLAY:
            am.add_command(
                label=f"  {md}", command=lambda m=md: self._show_model_info(m)
            )
        am.add_separator()
        am.add_command(label=f"版本: {_read_version()}", command=None)
        menubar.add_cascade(label="关于", menu=am)

        self.config(menu=menubar)

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
                  font=(FONT_FAMILY, 10)).pack(padx=15, pady=(15, 5))
        lb = tk.Listbox(dlg, font=(FONT_FAMILY, 10), selectmode=tk.SINGLE, height=6)
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

    def _load_data(self, path=None):
        """读取 CSV / Excel 数据"""
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("数据文件", "*.csv *.xlsx *.xls"),
                           ("CSV 文件", "*.csv"),
                           ("Excel 文件", "*.xlsx *.xls"),
                           ("所有文件", "*.*")],
                parent=self,
            )
            if not path:
                self._log.debug("_load_data: 用户取消选择")
                return
        self._log.info("_load_data: %s", path)
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = self._pick_excel_sheet(path)
                if df is None:
                    return
            else:
                df = pd.read_csv(path)
            self._apply_dataframe(df)
        except Exception as e:
            self._log.error("加载数据失败: %s", e)
            messagebox.showerror("加载错误", str(e), parent=self)

    def _load_data_new_window(self):
        """在新窗口读取数据"""
        self._log.info("打开新窗口读取数据")
        path = filedialog.askopenfilename(
            filetypes=[("数据文件", "*.csv *.xlsx *.xls"),
                       ("CSV 文件", "*.csv"),
                       ("Excel 文件", "*.xlsx *.xls"),
                       ("所有文件", "*.*")],
            parent=self,
        )
        if not path:
            return
        self._log.info("新窗口加载: %s", path)
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xls"):
                df = self._pick_excel_sheet(path)
                if df is None:
                    return
            else:
                df = pd.read_csv(path)
            Model_Fitting_App(parent=self, dataframe=df)
        except Exception as e:
            self._log.error("新窗口加载失败: %s", e)
            messagebox.showerror("加载错误", str(e), parent=self)

    def _show_model_info(self, display_name):
        """弹窗显示模型公式和介绍（从模型实例读取）"""
        self._log.info("显示模型信息: %s", display_name)
        key = MODEL_KEY_MAP.get(display_name)
        if not key:
            return
        model = self.models.get(key)
        if not model:
            return
        formula = f"${model.get_formula()}$"
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
        fax.text(
            0.5,
            0.5,
            formula,
            transform=fax.transAxes,
            fontsize=14,
            ha="center",
            va="center",
        )
        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.get_tk_widget().pack(fill=tk.X, padx=10, pady=(10, 5))
        canvas.draw()

        # 分隔线
        ttk.Separator(top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # 描述文本
        text = tk.Text(
            top,
            wrap=tk.WORD,
            font=(FONT_FAMILY, 10),
            padx=10,
            pady=5,
            relief=tk.FLAT,
            bg="#f5f5f5",
        )
        text.insert(tk.END, desc)
        text.config(state=tk.DISABLED)
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))

    def _menu_set_model(self, label):
        self._log.info("菜单切换模型: %s", label)
        self.model_var.set(label)
        self._on_model_change()

    def _menu_set_transform(self, val):
        self._log.info("菜单切换变换: %s", val)
        self.transform_mode.set(val)
        self.update_plot()

    def _menu_set_xscale(self, val):
        self._log.info("菜单切换 X 轴: %s", val)
        self.scale_x.set(val)
        self.update_plot()

    def _menu_set_yscale(self, val):
        self._log.info("菜单切换 Y 轴: %s", val)
        self.scale_y.set(val)
        self.update_plot()

    def _menu_set_theme(self, val):
        self._log.info("菜单切换主题: %s", val)
        self.theme_var.set(val)
        self._apply_theme()

    def _menu_range_dialog(self):
        """弹窗设置 X/Y 范围"""
        self._log.info("打开范围设置对话框")
        dlg = tk.Toplevel(self)
        dlg.title("设置 X/Y 范围")
        dlg.geometry("300x180")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        f = ttk.Frame(dlg, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="X 最小：").grid(row=0, column=0, sticky="e", pady=3)
        xmin_e = ttk.Entry(f, width=10)
        xmin_e.insert(0, self.xlim_min.get())
        xmin_e.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(f, text="X 最大：").grid(row=1, column=0, sticky="e", pady=3)
        xmax_e = ttk.Entry(f, width=10)
        xmax_e.insert(0, self.xlim_max.get())
        xmax_e.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(f, text="Y 最小：").grid(row=2, column=0, sticky="e", pady=3)
        ymin_e = ttk.Entry(f, width=10)
        ymin_e.insert(0, self.ylim_min.get())
        ymin_e.grid(row=2, column=1, sticky="w", padx=5)

        ttk.Label(f, text="Y 最大：").grid(row=3, column=0, sticky="e", pady=3)
        ymax_e = ttk.Entry(f, width=10)
        ymax_e.insert(0, self.ylim_max.get())
        ymax_e.grid(row=3, column=1, sticky="w", padx=5)

        def on_confirm():
            self._log.info(
                "应用范围: x=[%s, %s], y=[%s, %s]",
                xmin_e.get(),
                xmax_e.get(),
                ymin_e.get(),
                ymax_e.get(),
            )
            self.xlim_min.set(xmin_e.get())
            self.xlim_max.set(xmax_e.get())
            self.ylim_min.set(ymin_e.get())
            self.ylim_max.set(ymax_e.get())
            self.update_plot()
            dlg.destroy()

        btn_f = ttk.Frame(f)
        btn_f.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btn_f, text="确认", command=on_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_f, text="取消", command=dlg.destroy).pack(side=tk.LEFT, padx=5)

    def _build_top_bar(self):
        tf = ttk.Frame(self)
        tf.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        self._build_column_selector(tf)
        self._build_control_panel(tf)
        self._build_plot_control_panel(tf)

    def _build_column_selector(self, p):
        f = ttk.LabelFrame(p, text="数值列")
        f.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        self.left_inner = ttk.Frame(f)
        self.left_inner.pack()

    def _build_control_panel(self, p):
        c = ttk.LabelFrame(p, text="数据控制")
        c.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)

        r = 0
        ttk.Button(c, text="添加列", command=self.add_selector).grid(
            row=r, column=0, sticky="w", padx=(0, 1), pady=(0, 1)
        )
        ttk.Button(c, text="移除列", command=self.remove_last).grid(
            row=r, column=1, sticky="w", padx=(0, 1), pady=(0, 1)
        )
        ttk.Button(c, text="导出图", command=self.export_image).grid(
            row=r, column=2, sticky="w", padx=(0, 1), pady=(0, 1)
        )
        ttk.Button(c, text="导出参数", command=self.export_parameters).grid(
            row=r, column=3, sticky="w", padx=(0, 1), pady=(0, 1)
        )
        r += 1

        LW = 5
        ttk.Label(
            c, text="模型：", width=LW, anchor="e", font=(FONT_FAMILY, FONT_SIZE)
        ).grid(row=r, column=0, sticky="e", padx=(0, 1))
        self.model_var = tk.StringVar(value=MODEL_DISPLAY[0])
        mc = ttk.Combobox(
            c,
            textvariable=self.model_var,
            values=MODEL_DISPLAY,
            state="readonly",
            width=24,
        )
        mc.grid(row=r, column=1, sticky="w")
        mc.bind("<<ComboboxSelected>>", lambda e: self._on_model_change())

        ttk.Label(
            c, text="变换：", width=LW, anchor="e", font=(FONT_FAMILY, FONT_SIZE)
        ).grid(row=r, column=2, sticky="e", padx=(4, 1))
        self.transform_mode = tk.StringVar(value="CDF")
        tc = ttk.Combobox(
            c,
            textvariable=self.transform_mode,
            values=TRANSFORM_OPTIONS,
            state="readonly",
            width=12,
        )
        tc.grid(row=r, column=3, sticky="w")
        tc.bind("<<ComboboxSelected>>", lambda e: self.update_plot())
        r += 1

        self.formula_fig = Figure(figsize=(4.5, 0.55), dpi=100)
        self.formula_fig.set_facecolor("#f0f0f0")
        self.formula_ax = self.formula_fig.add_subplot(111)
        self.formula_ax.axis("off")
        self.formula_canvas = FigureCanvasTkAgg(self.formula_fig, master=c)
        self.formula_canvas.get_tk_widget().grid(
            row=r, column=0, columnspan=4, sticky="ew", pady=(1, 0)
        )
        self._on_model_change()

    def _build_plot_control_panel(self, p):
        c = ttk.LabelFrame(p, text="绘图控制")
        c.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        LW = 5

        r = 0
        # X/Y 轴 + 主题 同行排列
        ttk.Label(
            c, text="X 轴：", width=LW, anchor="e", font=(FONT_FAMILY, FONT_SIZE)
        ).grid(row=r, column=0, sticky="e", padx=(0, 1))
        self.scale_x = tk.StringVar(value="线性")
        xc = ttk.Combobox(
            c,
            textvariable=self.scale_x,
            values=SCALE_DISPLAY,
            state="readonly",
            width=6,
        )
        xc.grid(row=r, column=1, sticky="w", padx=(0, 2))
        xc.bind("<<ComboboxSelected>>", lambda e: self.update_plot())

        ttk.Label(
            c, text="Y 轴：", width=LW, anchor="e", font=(FONT_FAMILY, FONT_SIZE)
        ).grid(row=r, column=2, sticky="e", padx=(2, 1))
        self.scale_y = tk.StringVar(value="线性")
        yc = ttk.Combobox(
            c,
            textvariable=self.scale_y,
            values=SCALE_DISPLAY,
            state="readonly",
            width=6,
        )
        yc.grid(row=r, column=3, sticky="w", padx=(0, 2))
        yc.bind("<<ComboboxSelected>>", lambda e: self.update_plot())

        ttk.Label(
            c, text="主题：", width=LW, anchor="e", font=(FONT_FAMILY, FONT_SIZE)
        ).grid(row=r, column=4, sticky="e", padx=(2, 1))
        self.theme_var = tk.StringVar(value="default")
        themes = [
            "default",
            "ggplot",
            "seaborn-v0_8",
            "bmh",
            "fivethirtyeight",
            "dark_background",
            "classic",
        ]
        th = ttk.Combobox(
            c, textvariable=self.theme_var, values=themes, state="readonly", width=12
        )
        th.grid(row=r, column=5, sticky="w")
        th.bind("<<ComboboxSelected>>", lambda e: self._apply_theme())
        r += 1
        ttk.Separator(c, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=6, sticky="ew", pady=2
        )

        r += 1
        # X/Y 范围 + 按钮
        ttk.Label(
            c,
            text="X 范围：",
            width=LW,
            anchor="e",
            font=(FONT_FAMILY, FONT_SIZE - 1),
        ).grid(row=r, column=0, sticky="e", padx=(10, 10))
        self.xlim_min = tk.StringVar(value="")
        ttk.Entry(c, textvariable=self.xlim_min, width=LW*2).grid(
            row=r, column=1, sticky="w"
        )
        ttk.Label(c, text="~", font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=2)
        self.xlim_max = tk.StringVar(value="")
        ttk.Entry(c, textvariable=self.xlim_max, width=LW*2).grid(
            row=r, column=3, sticky="w"
        )
        r += 1

        ttk.Label(
            c,
            text="Y 范围：",
            width=LW,
            anchor="e",
            font=(FONT_FAMILY, FONT_SIZE - 1),
        ).grid(row=r, column=0, sticky="e", padx=(10, 10))
        self.ylim_min = tk.StringVar(value="")
        ttk.Entry(c, textvariable=self.ylim_min, width=LW*2).grid(
            row=r, column=1, sticky="w"
        )
        ttk.Label(c, text="~", font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=2)
        self.ylim_max = tk.StringVar(value="")
        ttk.Entry(c, textvariable=self.ylim_max, width=LW*2).grid(
            row=r, column=3, sticky="w"
        )
        r += 1

        ttk.Button(c, text="取消选中", command=self._clear_selection).grid(
            row=r, column=0, columnspan=3, pady=2, sticky="ew", padx=(0, 1)
        )
        ttk.Button(c, text="应用范围", command=self.update_plot).grid(
            row=r, column=3, columnspan=3, pady=2, sticky="ew", padx=(1, 0)
        )
        r += 1

        ttk.Button(c, text="绘制 limit 线", command=self._draw_limit_lines).grid(
            row=r, column=0, columnspan=6, pady=2, sticky="ew"
        )

    def _draw_limit_lines(self):
        """重新绘图并绘制 limit 竖线"""
        self._log.info("绘制 limit 线")
        self.update_plot()
        if not self.ax or not self._plot_meta:
            self._log.debug("绘制 limit 线: 无数据，跳过")
            return
        seen = set()
        for meta in self._plot_meta:
            col = meta["col"]
            si = meta["selector_idx"]
            if si in seen:
                continue
            seen.add(si)
            try:
                limit = self.selectors[si].get_limit()
            except Exception:
                continue
            color = meta["color"]
            self.ax.axvline(
                x=limit, color=color, linestyle=":", alpha=0.7, linewidth=1.5
            )
            self.ax.text(
                limit,
                0.02,
                f"{col}={limit:.3g}",
                color=color,
                fontsize=7,
                rotation=90,
                va="bottom",
                ha="right",
                transform=self.ax.get_xaxis_transform(),
            )
        self.canvas.draw_idle()

    def _apply_theme(self):
        theme = self.theme_var.get()
        self._log.info("应用主题: %s", theme)
        try:
            if theme == "default":
                plt.style.use("default")
            else:
                plt.style.use(theme)
        except Exception as e:
            self._log.warning("应用主题失败: %s", e)
        self.update_plot()

    def _build_middle_area(self):
        m = ttk.Frame(self)
        m.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
        pf = ttk.LabelFrame(m, text="图表")
        pf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.canvas_frame = ttk.Frame(pf)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        sf = ttk.LabelFrame(m, text="统计信息")
        sf.pack(side=tk.LEFT, fill=tk.BOTH, padx=4, pady=4, ipadx=2)
        self.mode_label = ttk.Label(
            sf, text="", font=(FONT_FAMILY, 8), foreground="#555555", anchor=tk.W
        )
        self.mode_label.pack(fill=tk.X, padx=2, pady=(0, 2))
        tc = ttk.Frame(sf)
        tc.pack(fill=tk.BOTH, expand=True)
        self.stats_tree = ttk.Treeview(
            tc, columns=("值",), show="tree headings", height=22
        )
        self.stats_tree.heading("值", text="值")
        self.stats_tree.column("#0", width=160, anchor="w", stretch=False)
        self.stats_tree.column("值", width=180, anchor="w", stretch=False)
        sy = ttk.Scrollbar(tc, orient=tk.VERTICAL, command=self.stats_tree.yview)
        sx = ttk.Scrollbar(tc, orient=tk.HORIZONTAL, command=self.stats_tree.xview)
        self.stats_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.stats_tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        tc.grid_rowconfigure(0, weight=1)
        tc.grid_columnconfigure(0, weight=1)
        self.stats_tree.bind("<MouseWheel>", self._on_tree_mousewheel)
        self.stats_tree.bind("<Button-1>", self._on_tree_click, add="+")

    # ==================== 选择器 ====================

    def _make_selector(self):
        return SeriesSelector(
            self.left_inner,
            self.value_columns,
            len(self.selectors),
            remove_callback=self._remove_selector,
            manual_remove_callback=self._on_manual_remove,
            auto_remove_callback=self._on_auto_remove,
            restore_callback=self._on_restore,
            selection_change_callback=lambda s: self.update_plot(),
            style_change_callback=self._on_style_change,
        )

    def _on_style_change(self, sel):
        self._log.info(
            "样式变更: 列%d marker=%s linestyle=%s",
            sel.idx + 1,
            sel.get_marker(),
            sel.get_linestyle(),
        )
        self.update_plot()

    def add_selector(self):
        if len(self.selectors) >= self.max_series:
            self._log.warning("添加列达到上限: %d", self.max_series)
            messagebox.showinfo(
                "已达上限", f"最多支持 {self.max_series} 列", parent=self
            )
            return
        self._log.info("添加列: 当前 %d 列", len(self.selectors) + 1)
        s = self._make_selector()
        s.pack(fill=tk.X, pady=1)
        self.selectors.append(s)
        self.update_plot()

    def remove_last(self):
        if self.selectors:
            self._log.info("移除最后一列: 剩余 %d 列", len(self.selectors) - 1)
            self.selectors.pop().destroy()
            self.update_plot()

    def _remove_selector(self, s):
        if s in self.selectors:
            self._log.info("移除指定列: idx=%d", s.idx)
            self.selectors.remove(s)
            s.destroy()
            self.update_plot()

    def _on_model_change(self):
        k = MODEL_KEY_MAP.get(self.model_var.get(), "Weibull")
        self._log.info("模型切换: %s -> %s", self.current_model, k)
        self.current_model = k
        formula = self.models[k].get_formula()
        self.formula_ax.clear()
        self.formula_ax.axis("off")
        self.formula_ax.text(
            0.5,
            0.5,
            f"${formula}$",
            transform=self.formula_ax.transAxes,
            fontsize=14,
            ha="center",
            va="center",
        )
        self.formula_fig.canvas.draw_idle()
        self.update_plot()

    # ==================== 离群点 ====================

    def _on_manual_remove(self, sel):
        if self.data is None:
            return
        c = sel.get_selection()
        if not c or c not in self.data.columns:
            messagebox.showinfo("提示", "请先选择有效的数值列", parent=self)
            return
        self._active_selector_idx = (
            sel.idx if self._active_selector_idx != sel.idx else None
        )
        self._log.info(
            "手动去除模式: %s, selector_idx=%s",
            "进入" if self._active_selector_idx is not None else "退出",
            sel.idx,
        )
        self._clear_selection()
        self._update_mode_label()
        self.canvas.draw_idle()

    def _on_auto_remove(self, sel):
        if self.data is None:
            return
        c = sel.get_selection()
        if not c or c not in self.data.columns:
            return
        self._log.info("自动去除离群点: 列=%s, model=%s", c, self.current_model)
        if self.original_data is None:
            self.original_data = self.data.copy()
        model = self.models[self.current_model]
        cnt = 0
        for meta in self._plot_meta:
            if meta["selector_idx"] != sel.idx or meta["col"] != c:
                continue
            try:
                popt, _, _, _, _ = model.fit(meta["samples"])
                yp = model.cdf(meta["samples"], popt)
                yt = (np.arange(1, len(yp) + 1) - 0.3) / (len(yp) + 0.4)
                res = np.abs(yt - yp)
                th = 3 * np.std(res)
                mask = res > th
                if mask.any():
                    drop = meta["df_indices"][mask]
                    self.data.loc[drop, c] = np.nan
                    cnt += mask.sum()
            except Exception as e:
                self._log.debug('自动去除拟合失败: %s', e)
                continue
        if cnt:
            self._log.info("自动去除 %d 个离群点 (列=%s)", cnt, c)
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()
        messagebox.showinfo(
            "自动去除", f"列 {c} 已自动去除 {cnt} 个离群点。", parent=self
        )

    def _on_restore(self, sel=None):
        if self.original_data is not None:
            self._log.info("恢复原始数据")
            self.data = self.original_data.copy()
            self.original_data = None
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()
            messagebox.showinfo("恢复", "数据已恢复到最初加载状态。", parent=self)
        else:
            self._log.debug("恢复原始数据: 无需恢复（无原始数据备份）")

    def _update_mode_label(self):
        if self._active_selector_idx is not None:
            sel = self.selectors[self._active_selector_idx]
            self.mode_label.config(
                text=f"⚠ 手动去除：右键框选去除「{sel.get_selection()}」数据点（再点退出）",
                foreground="red",
            )
        else:
            self.mode_label.config(
                text="● 普通：单击选点 / 右键框选 / 双击显示数据", foreground="#555555"
            )

    def _on_box_select_virtual(self, x0, y0, x1, y1):
        """手动框选回调，x0,y0,x1,y1 为数据坐标"""
        self._log.debug("框选: (%.3g,%.3g)-(%.3g,%.3g)", x0, y0, x1, y1)
        xmin, xmax = sorted([x0, x1])
        ymin, ymax = sorted([y0, y1])
        sel = []
        for m in self._plot_meta:
            if (
                self._active_selector_idx is not None
                and m["selector_idx"] != self._active_selector_idx
            ):
                continue
            inside = (
                (m["xs"] >= xmin)
                & (m["xs"] <= xmax)
                & (m["ys"] >= ymin)
                & (m["ys"] <= ymax)
            )
            for i in np.where(inside)[0]:
                sel.append(
                    {
                        "col": m["col"],
                        "group": m.get("group"),
                        "df_indices": m["df_indices"],
                        "samples": m["samples"],
                        "point_idx": int(i),
                        "x_raw": float(m["xs"][i]),
                        "y_cdf": float(m["ys"][i]),
                        "df_idx": m["df_indices"][i],
                    }
                )
        if not sel:
            self._log.debug("框选: 无匹配点")
            return
        self._log.info("框选 %d 个点", len(sel))
        if self._active_selector_idx is not None:
            self._highlight_selected(sel)  # 先高亮
            self.canvas.draw_idle()  # 刷新后再弹窗
            self._confirm_remove(sel)
        else:
            self._highlight_selected(sel)

    def _highlight_selected(self, sel):
        self._log.debug("高亮选中 %d 个点", len(sel))
        self._clear_selection()
        self._selected_meta = sel
        if sel:
            hl = self.ax.scatter(
                [s["x_raw"] for s in sel],
                [s["y_cdf"] for s in sel],
                s=80,
                facecolor="none",
                edgecolor="red",
                linewidth=2,
                zorder=10,
            )
            self._highlight_artists.append(hl)
            self.canvas.draw_idle()

    def _confirm_remove(self, sel):
        lines = [
            f"以下 {len(sel)} 个点将被去除：\n",
            f"列: {sel[0]['col']}\n",
            "-" * 50 + "\n",
        ]
        for i, s in enumerate(sel[:20]):
            g = f" [{s.get('group', '-')}]" if s.get("group") else ""
            lines.append(f"  #{i+1}: 值={s['x_raw']:.6g}  CDF={s['y_cdf']:.4f}{g}\n")
        if len(sel) > 20:
            lines.append(f"  ... 还有 {len(sel) - 20} 个\n")
        if messagebox.askyesno("确认去除", "".join(lines), parent=self):
            if self.original_data is None:
                self.original_data = self.data.copy()
            for s in sel:
                self.data.loc[s["df_idx"], s["col"]] = np.nan
            self._log.info("手动去除 %d 个点 (列=%s)", len(sel), sel[0]["col"])
            self._active_selector_idx = None
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()

    # ==================== 数据加载 ====================

    def _apply_dataframe(self, df):
        info = detect_columns(df)
        self.data = df
        self.original_data = df.copy()
        self.columns = info["columns"]
        self.group_column = info["group_column"]
        self.value_columns = info["value_columns"]
        self.fit_results.clear()
        self.stats_cache.clear()
        self._visibility.clear()
        self._log.info(
            "数据加载: %d 行, %d 列, 数值列=%s, 分组列=%s",
            len(df),
            len(df.columns),
            self.value_columns,
            self.group_column,
        )
        for s in self.selectors:
            s.combo["values"] = self.value_columns
            s.columns = self.value_columns
            if self.value_columns:
                s.combo.current(0)
        self.update_plot()

    def load_dataframe(self, df):
        self._log.info("load_dataframe: %d 行 x %d 列", len(df), len(df.columns))
        if not isinstance(df, pd.DataFrame):
            self._log.error("load_dataframe: 类型错误，期望 DataFrame")
            raise TypeError("参数必须是 pandas DataFrame")
        self._apply_dataframe(df)

    def load_csv(self, path=None):
        """向后兼容别名"""
        self._load_data(path=path)

    def generate_and_load(self):
        self._log.info("生成测试数据并加载")
        p = default_test_path()
        generate_test_data(p)
        self.load_csv(p)

    def _export_template(self):
        """导出 CSV 模板文件，含 PART_ID + group + IDSS1 列示例"""
        self._log.info("导出模板")
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            initialfile="fitting_template.csv",
            parent=self,
        )
        if not p:
            return
        try:
            import pandas as pd
            template = pd.DataFrame({
                "PART_ID": [f"P{i:03d}" for i in range(1, 11)],
                "group": ["GroupA"] * 5 + ["GroupB"] * 5,
                "IDSS1": [1.2, 1.5, 1.3, 1.8, 1.6, 2.1, 2.4, 1.9, 2.2, 2.6],
            })
            template.to_csv(p, index=False)
            messagebox.showinfo("导出模板", f"模板已保存至：\n{p}", parent=self)
        except Exception as e:
            self._log.error("导出模板失败: %s", e)
            messagebox.showerror("导出错误", str(e), parent=self)

    # ==================== 绘图 ====================

    def update_plot(self):
        if self.data is None or not self.selectors:
            return
        if self.group_column:
            raw = self.data[self.group_column].dropna().unique()
            groups = sorted(raw)
        else:
            groups = ["All"]
        self._log.info(
            "更新绘图: model=%s, transform=%s, xscale=%s, yscale=%s, groups=%s",
            self.model_var.get(),
            self.transform_mode.get(),
            self.scale_x.get(),
            self.scale_y.get(),
            groups,
        )
        self.current_model = MODEL_KEY_MAP.get(self.model_var.get(), "Weibull")
        model = self.models[self.current_model]
        self._active_selector_idx = None
        self.fit_results.clear()
        self.stats_cache.clear()
        if self.figure:
            plt.close(self.figure)
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.ax = ax = self.figure.add_subplot(111)
        gcolors = {g: COLORS[i % len(COLORS)] for i, g in enumerate(groups)}
        self._plot_meta = []
        for si, sel in enumerate(self.selectors):
            c = sel.get_selection()
            if not c or c not in self.data.columns:
                continue
            if self.group_column:
                for g in groups:
                    sub = self.data.loc[self.data[self.group_column] == g, c].dropna()
                    if len(sub) < 3:
                        continue
                    self._fit_plot(
                        ax, model, sub.values, sub.index.values, c, g, si, gcolors[g]
                    )
            else:
                sub = self.data[c].dropna()
                if len(sub) >= 3:
                    self._fit_plot(
                        ax,
                        model,
                        sub.values,
                        sub.index.values,
                        c,
                        None,
                        si,
                        gcolors["All"],
                    )
        tr = self.transform_mode.get()
        yt = "CDF" if tr == "CDF" else "ln(-ln(1-CDF))"
        ax.set_xlabel("")
        ax.set_ylabel(yt, fontsize=12)
        ax.set_title(
            f"{self.current_model} Distribution Fit", fontsize=14, fontweight="bold"
        )
        ax.set_xscale(SCALE_MAP.get(self.scale_x.get(), self.scale_x.get()))
        ax.set_yscale(SCALE_MAP.get(self.scale_y.get(), self.scale_y.get()))
        # 科学计数法：跨量级时每个 tick 独立显示 a.aa×10ⁿ
        from matplotlib.ticker import FuncFormatter

        def _sci_fmt(v, _):
            if v == 0:
                return "0"
            exp = int(np.floor(np.log10(abs(v))))
            mant = v / 10**exp
            if abs(exp) <= 1:
                return f"{v:#.4g}"
            return f"{mant:.2f}e{exp:+d}"

        ax.xaxis.set_major_formatter(FuncFormatter(_sci_fmt))
        ax.yaxis.set_major_formatter(FuncFormatter(_sci_fmt))
        self._apply_axis_limits(ax)
        # 图例由 _apply_visibility() 统一构建和刷新
        ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self._embed_canvas()
        self._apply_visibility()
        self._setup_interaction()
        self._update_stats_tree()

    def _fit_plot(self, ax, model, samples, df_indices, col, group, si, color):
        s = np.asarray(samples)
        idx = np.argsort(s)
        ss, di = s[idx], np.asarray(df_indices)[idx]
        try:
            popt, pcov, r2, xs, cdf = model.fit(ss)
            self._log.debug(
                "拟合 %s[%s] n=%d R²=%.5f params=%s",
                col,
                group or "All",
                len(ss),
                r2,
                [f"{v:.4g}" for v in popt],
            )
        except Exception as e:
            self._log.warning("拟合失败 %s[%s]: %s", col, group or "All", e)
            return
        tr = self.transform_mode.get()
        y = cdf if tr == "CDF" else _safe_lnln(cdf)
        if si >= len(self.selectors):
            return
        mk = self.selectors[si].get_marker()
        ls = self.selectors[si].get_linestyle()
        art = ax.scatter(
            xs, y, alpha=0.6, s=40, color=color, edgecolor="none", picker=5, marker=mk
        )
        # 拟合曲线范围
        limit = self.selectors[si].get_limit() if si < len(self.selectors) else 0
        if tr != "CDF":
            # ln(-ln(1-CDF)) 模式：以 limit 为边界参考
            xf_min = 0.9 * min(limit, xs.min()) if limit > 0 else xs.min() * 0.98
            xf_max = 1.1 * max(limit, xs.max()) if limit > 0 else xs.max() * 1.02
        else:
            xf_min = min(xs.min() * 0.95, limit * 0.9) if limit > 0 else xs.min() * 0.95
            xf_max = max(xs.max() * 1.05, limit * 1.1) if limit > 0 else xs.max() * 1.05
        xf = np.linspace(xf_min, xf_max, 200)
        yc = model.cdf(xf, popt)
        if tr != "CDF":
            yc = _safe_lnln(yc)
        ax.plot(xf, yc, color=color, linestyle=ls, alpha=0.8, linewidth=2)
        key = (col, group if group else "All")
        self.fit_results[key] = (model.name, popt, r2, xs, cdf)
        stats = self._stats(ss)
        try:
            if si < len(self.selectors):
                limit = self.selectors[si].get_limit()
                stats["F_at_limit"] = model.cdf(limit, popt)
        except Exception:
            pass
        self.stats_cache[key] = stats
        self._plot_meta.append(
            {
                "artist": art,
                "col": col,
                "group": group,
                "selector_idx": si,
                "df_indices": di,
                "xs": xs,
                "ys": y,
                "samples": ss,
                "color": color,
                "mk": mk,
                "ls": ls,
                "fit_line": ax.lines[-1],
            }
        )  # 直接保存拟合线引用

    @staticmethod
    def _stats(s):
        s = np.asarray(s)
        return {
            "count": len(s),
            "mean": np.mean(s),
            "std": np.std(s, ddof=1) if len(s) > 1 else 0.0,
            "median": np.median(s),
            "p5": np.percentile(s, 5),
            "p95": np.percentile(s, 95),
            "min": np.min(s),
            "max": np.max(s),
        }

    def _apply_axis_limits(self, ax):
        """应用用户设定的 X/Y 轴范围"""
        try:
            xl, xr, yb, yt = None, None, None, None
            if self.xlim_min.get():
                xl = float(self.xlim_min.get())
            if self.xlim_max.get():
                xr = float(self.xlim_max.get())
            if self.ylim_min.get():
                yb = float(self.ylim_min.get())
            if self.ylim_max.get():
                yt = float(self.ylim_max.get())
            if xl is not None and xr is not None and xl >= xr:
                self._log.warning("X 范围无效: [%s, %s]", xl, xr)
                return
            if yb is not None and yt is not None and yb >= yt:
                self._log.warning("Y 范围无效: [%s, %s]", yb, yt)
                return
            if xl is not None:
                ax.set_xlim(left=xl)
            if xr is not None:
                ax.set_xlim(right=xr)
            if yb is not None:
                ax.set_ylim(bottom=yb)
            if yt is not None:
                ax.set_ylim(top=yt)
        except ValueError as e:
            self._log.debug("应用轴范围异常: %s", e)

    def _embed_canvas(self):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar:
            self.toolbar.destroy()
            self.toolbar = None
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        try:
            if not self.toolbar_frame:
                self.toolbar_frame = ttk.Frame(self.canvas_frame)
                self.toolbar_frame.pack(fill=tk.X, padx=4, pady=2, side=tk.BOTTOM)
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
            self.toolbar.update()
        except Exception as e:
            self._log.debug("工具栏创建失败: %s", e)

    # ==================== 交互 ====================

    def _setup_interaction(self):
        if not self.canvas:
            return
        self._clear_selection()
        self._update_mode_label()

        # 手动右键框选（比 RectangleSelector 更可靠）
        self._box_start = None
        self._box_patch = None

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
                    abs(event.xdata - x0),
                    abs(event.ydata - y0),
                    fill=True,
                    facecolor="blue",
                    edgecolor="blue",
                    alpha=0.2,
                )
                self.ax.add_patch(self._box_patch)
                self.canvas.draw_idle()

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
                self._on_box_select_virtual(x0, y0, x1, y1)
                self.canvas.draw_idle()

        self.canvas.mpl_connect("button_press_event", on_press)
        self.canvas.mpl_connect("motion_notify_event", on_motion)
        self.canvas.mpl_connect("button_release_event", on_release)

        def on_pick(event):
            if len(event.ind) == 0:
                return
            for m in self._plot_meta:
                if m["artist"] is event.artist:
                    if (
                        self._active_selector_idx is not None
                        and m["selector_idx"] != self._active_selector_idx
                    ):
                        continue
                    sel = []
                    for i in event.ind:
                        sel.append(
                            {
                                "col": m["col"],
                                "group": m.get("group"),
                                "point_idx": int(i),
                                "x_raw": float(m["xs"][i]),
                                "y_cdf": float(m["ys"][i]),
                                "df_idx": m["df_indices"][i],
                                "df_indices": m["df_indices"],
                                "samples": m["samples"],
                            }
                        )
                    if self._active_selector_idx is not None:
                        same = [s for s in self._selected_meta if s["col"] == m["col"]]
                        ex = {s["point_idx"] for s in same}
                        new = [s for s in sel if s["point_idx"] not in ex]
                        self._selected_meta = same + new
                        self._highlight_selected(self._selected_meta)
                    else:
                        self._highlight_selected(sel)
                    break

        self.canvas.mpl_connect("pick_event", on_pick)

        def on_dbl(event):
            if self._selected_meta:
                if self._active_selector_idx is not None:
                    self._confirm_remove(list(self._selected_meta))
                else:
                    self._show_popup(self._selected_meta)

        self.canvas.get_tk_widget().bind("<Double-Button-1>", on_dbl)

    def _clear_selection(self):
        if self._highlight_artists or self._selected_meta:
            self._log.debug(
                "清除选中: %d 个高亮, %d 个选中",
                len(self._highlight_artists),
                len(self._selected_meta),
            )
        for a in self._highlight_artists:
            a.remove()
        self._highlight_artists.clear()
        self._selected_meta.clear()
        if self.canvas:
            self.canvas.draw_idle()

    def _show_popup(self, sm):
        """Treeview 弹窗：按列→分组折叠显示全部数据"""
        self._log.info("显示数据点详情弹窗: %d 个点", len(sm))
        top = tk.Toplevel(self)
        top.title("数据点详情")
        top.geometry("650x500")

        tv = ttk.Treeview(top, columns=("PART_ID", "值"), show="tree headings")
        tv.heading("PART_ID", text="PART_ID")
        tv.heading("值", text="值")
        tv.column("PART_ID", width=150, anchor="w")
        tv.column("值", width=150, anchor="e")

        # 按列→分组组织，同时收集最大文本宽度
        max_len = 0
        by_col = {}
        for s in sm:
            by_col.setdefault(s["col"], []).append(s)
            max_len = max(max_len, len(s["col"]))
        for col, items in sorted(by_col.items()):
            cn = tv.insert("", tk.END, text=col, values=("", ""), open=True)
            by_grp = {}
            for s in items:
                r = self.data.iloc[s["df_idx"]]
                g = r.get(self.group_column, "-") if self.group_column else "-"
                max_len = max(max_len, len(str(g)))
                pid = str(r.get("PART_ID", r.get("part_id", str(s["df_idx"]))))
                by_grp.setdefault(g, []).append((pid, s["x_raw"]))
            for g, pts in sorted(by_grp.items()):
                gn = tv.insert(cn, tk.END, text=g, values=("", ""), open=True)
                for pid, val in pts:
                    tv.insert(gn, tk.END, text="", values=(pid, f"{val:.6g}"))

        # 自适应列宽：每字符约 10px + 缩进余量
        tv.column("#0", width=max(80, max_len * 10 + 40), anchor="w", stretch=False)

        sy = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tv.yview)
        sx = ttk.Scrollbar(top, orient=tk.HORIZONTAL, command=tv.xview)
        tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tv.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure(0, weight=1)

    # ==================== 统计信息 ====================

    def _update_stats_tree(self):
        t = self.stats_tree
        for item in t.get_children():
            t.delete(item)
        if not self.fit_results:
            t.insert("", tk.END, text="无数据", values=("",))
            return
        bc = {}
        for (col, grp), (mn, params, r2, xs, cdf) in sorted(self.fit_results.items()):
            bc.setdefault(col, []).append((grp, mn, params, r2))
        for col, items in sorted(bc.items()):
            # 列节点也显示 checkbox（聚合状态）
            col_children = []
            col_all_vis = True
            for grp, mn, params, r2 in items:
                key = (col, grp)
                vis = self._visibility.get(key, True)
                col_children.append((key, vis))
                if not vis:
                    col_all_vis = False
            col_chk = "☑" if col_all_vis else "☐"
            cn = t.insert("", tk.END, text=f"{col_chk} {col}", values=("",), open=True)
            for (key, vis), (grp, mn, params, r2) in zip(col_children, items):
                chk = "☑" if vis else "☐"
                gt = grp if grp != "All" else "(全部)"
                gn = t.insert(
                    cn,
                    tk.END,
                    text=f"{chk} {gt}",
                    values=("",),
                    open=True,
                    tags=("group",),
                )
                model = self.models[mn]
                t.insert(gn, tk.END, text="模型", values=(mn,))
                t.insert(gn, tk.END, text="R²", values=(f"{r2:.6f}",))
                for pn, pv in zip(model.get_param_names(), params):
                    t.insert(gn, tk.END, text=pn, values=(f"{pv:.6g}",))
                st = self.stats_cache.get(key, {})
                for lbl, k in [
                    ("样本数", "count"),
                    ("均值", "mean"),
                    ("标准差", "std"),
                    ("中位数", "median"),
                    ("5%分位数", "p5"),
                    ("95%分位数", "p95"),
                    ("最小值", "min"),
                    ("最大值", "max"),
                    ("limit处F值", "F_at_limit"),
                ]:
                    v = st.get(k)
                    if v is not None:
                        t.insert(
                            gn,
                            tk.END,
                            text=lbl,
                            values=(f"{v:.6g}" if isinstance(v, float) else str(v),),
                        )

    def _on_tree_click(self, event):
        """点击统计树切换显示/隐藏"""
        item = self.stats_tree.identify_row(event.y)
        if not item:
            return
        text = self.stats_tree.item(item, "text")
        self._log.debug("统计树点击: item=%s", text)
        parent = self.stats_tree.parent(item)
        if parent and parent in self.stats_tree.get_children(""):
            # 分组节点：切换单个分组
            if "☑" not in text and "☐" not in text:
                return
            col = self.stats_tree.item(parent, "text")
            if col.startswith("☑ ") or col.startswith("☐ "):
                col = col[2:].strip()
            grp = text[2:].strip()
            if grp == "(全部)":
                grp = "All"
            key = (col, grp)
            vis = not self._visibility.get(key, True)
            self._visibility[key] = vis
            chk = "☑" if vis else "☐"
            gt = grp if grp != "All" else "(全部)"
            self.stats_tree.item(item, text=f"{chk} {gt}")
            # 更新列节点 checkbox
            siblings = self.stats_tree.get_children(parent)
            all_vis = all("☑" in self.stats_tree.item(s, "text") for s in siblings)
            self.stats_tree.item(parent, text=f'{"☑" if all_vis else "☐"} {col}')
        elif not parent:
            # 列节点：切换该列所有分组
            col = text
            if col.startswith("☑ ") or col.startswith("☐ "):
                col = col[2:].strip()
            children = self.stats_tree.get_children(item)
            if not children:
                return
            all_vis = all("☑" in self.stats_tree.item(c, "text") for c in children)
            new_vis = not all_vis
            for c in children:
                ct = self.stats_tree.item(c, "text")
                if "☑" in ct or "☐" in ct:
                    g = ct[2:].strip()
                    if g == "(全部)":
                        g = "All"
                    self._visibility[(col, g)] = new_vis
                    chk = "☑" if new_vis else "☐"
                    gt = g if g != "All" else "(全部)"
                    self.stats_tree.item(c, text=f"{chk} {gt}")
            # 更新列节点
            self.stats_tree.item(item, text=f'{"☑" if new_vis else "☐"} {col}')
        else:
            return
        self._apply_visibility()
        self.canvas.draw_idle()

    def _on_tree_mousewheel(self, e):
        self.stats_tree.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def _apply_visibility(self):
        """应用可见性设置到图上 artists、拟合线、图例（独立控制每列每组）"""
        if not self.ax:
            return
        self._log.debug(
            "应用可见性: %d 条, %s",
            len(self._plot_meta),
            {str(k): v for k, v in self._visibility.items()},
        )
        # 1) 散点和拟合线
        for m in self._plot_meta:
            key = (m["col"], m.get("group") if m.get("group") else "All")
            vis = self._visibility.get(key, True)
            m["artist"].set_visible(vis)
            fit_line = m.get("fit_line")
            if fit_line:
                fit_line.set_visible(vis)
        # 2) 图例 — 移除旧图例，用更新后的 alpha 重建
        old_legend = self.ax.get_legend()
        if old_legend:
            old_legend.remove()
        from matplotlib.lines import Line2D

        leg = []
        col_done = set()
        for m in self._plot_meta:
            c = m["col"]
            g = m.get("group")
            mk = m.get("mk", "o")
            ls = m.get("ls", "-")
            key = (c, g if g else "All")
            vis = self._visibility.get(key, True)
            # 列标题（只在首次出现时添加，根据整列可见性决定 alpha）
            if c not in col_done:
                col_done.add(c)
                col_all_hidden = all(
                    not self._visibility.get(
                        (mm["col"], mm.get("group") if mm.get("group") else "All"), True
                    )
                    for mm in self._plot_meta
                    if mm["col"] == c
                )
                col_h = Line2D(
                    [0],
                    [0],
                    marker=mk,
                    color="#444444",
                    linestyle=ls,
                    label=f"— {c} —",
                    markersize=8,
                    linewidth=2,
                    alpha=0.15 if col_all_hidden else 1.0,
                )
                leg.append(col_h)
                self._col_legends[c] = col_h
            # 分组条目
            r2 = self.fit_results.get(key, (None, None, 0, None, None))[2]
            gtxt = g if g else ""
            grp_h = Line2D(
                [0],
                [0],
                marker=mk,
                color=m["color"],
                linestyle=ls,
                label=f"  {gtxt}  R²={r2:.4f}",
                markersize=6,
                linewidth=2,
                alpha=0.15 if not vis else 1.0,
            )
            leg.append(grp_h)
            m["leg_grp"] = grp_h
        self.ax.legend(
            handles=leg, loc="best", fontsize=9, framealpha=0.9, handlelength=4.0
        )

    # ==================== 导出 ====================

    def export_image(self):
        if self.figure is None:
            messagebox.showwarning("导出", "没有可导出的图表", parent=self)
            return
        self._log.info("导出图表")
        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("PDF", "*.pdf"),
                ("SVG", "*.svg"),
                ("JPG", "*.jpg"),
                ("EPS", "*.eps"),
                ("所有文件", "*.*"),
            ],
            parent=self,
        )
        if p:
            try:
                self.figure.savefig(p, dpi=300, bbox_inches="tight")
                messagebox.showinfo("导出", f"图表已保存至：\n{p}", parent=self)
            except Exception as e:
                messagebox.showerror("导出错误", str(e), parent=self)

    def export_parameters(self):
        if not self.fit_results:
            messagebox.showwarning("导出", "没有可导出的拟合结果", parent=self)
            return
        self._log.info("导出参数, %d 条结果", len(self.fit_results))
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            parent=self,
        )
        if p:
            try:
                rows = []
                for (col, grp), (mn, params, r2, xs, cdf) in sorted(
                    self.fit_results.items()
                ):
                    model = self.models[mn]
                    st = self.stats_cache.get((col, grp), {})
                    row = {
                        "Column": col,
                        "Group": grp,
                        "Model": mn,
                        "R_squared": f"{r2:.6f}",
                        "Sample_Count": len(xs),
                        "Mean": f'{st.get("mean", 0):.6g}',
                        "Std": f'{st.get("std", 0):.6g}',
                        "Median": f'{st.get("median", 0):.6g}',
                        "P5": f'{st.get("p5", 0):.6g}',
                        "P95": f'{st.get("p95", 0):.6g}',
                        "F_at_limit": f'{v:.6g}' if isinstance((v := st.get("F_at_limit")), float) else "",
                    }
                    for pn, pv in zip(model.get_param_names(), params):
                        row[pn.replace(" ", "_")] = f"{pv:.6g}"
                    rows.append(row)
                pd.DataFrame(rows).to_csv(p, index=False)
                messagebox.showinfo("导出", f"参数已保存至：\n{p}", parent=self)
            except Exception as e:
                messagebox.showerror("导出错误", str(e), parent=self)


def launch(dataframe=None, csv_path=None):
    """启动分布拟合工具

    Parameters
    ----------
    dataframe : pd.DataFrame, optional
        直接传入 DataFrame
    csv_path : str, optional
        CSV 文件路径

    Returns
    -------
    App
    """
    app = Model_Fitting_App(dataframe=dataframe)
    if csv_path and dataframe is None:
        app.after(100, lambda: app.load_csv(csv_path))
    app._tk_root.mainloop()
    return app


if __name__ == "__main__":
    launch()
