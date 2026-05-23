"""
主窗口 App 类 — 分布拟合工具的 UI 编排
"""
import sys
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from matplotlib.ticker import ScalarFormatter

if __package__ is None or __package__ == '':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                        SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                        MODEL_DISPLAY, MODEL_KEY_MAP)
    from models import MODEL_INSTANCES
    from widgets import SeriesSelector
    from utils import detect_columns, generate_test_data, default_test_path
else:
    from .config import (FONT_FAMILY, FONT_SIZE, MAX_SERIES, COLORS,
                         SCALE_DISPLAY, SCALE_MAP, TRANSFORM_OPTIONS,
                         MODEL_DISPLAY, MODEL_KEY_MAP)
    from .models import MODEL_INSTANCES
    from .widgets import SeriesSelector
    from .utils import detect_columns, generate_test_data, default_test_path

_SCIFMT = ScalarFormatter(useMathText=True)
_SCIFMT.set_scientific(True)
_SCIFMT.set_powerlimits((-2, 4))

class App(tk.Toplevel):
    """分布拟合工具主窗口"""

    def __init__(self, parent=None, dataframe=None):
        self._standalone = parent is None
        if self._standalone:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            super().__init__(self._tk_root)
        else:
            super().__init__(parent)
        self.title("分布拟合工具")
        self.geometry("1450x900")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        style = ttk.Style(self)
        style.configure('.', font=(FONT_FAMILY, FONT_SIZE))

        self.data = None
        self.original_data = None
        self.columns = []
        self.value_columns = []
        self.group_column = None
        self.selectors = []
        self.models = MODEL_INSTANCES
        self.current_model = 'Weibull'
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
        self._rect_selector = None
        self._active_selector_idx = None

        self._build_ui()
        self.max_series = MAX_SERIES
        self.add_selector()
        if dataframe is not None:
            self.after(100, lambda: self.load_dataframe(dataframe))

    def _on_close(self):
        if self._standalone:
            self._tk_root.destroy()
        else:
            self.destroy()

    # ==================== UI ====================

    def _build_ui(self):
        self._build_menu()
        self._build_top_bar()
        self._build_middle_area()

    def _build_menu(self):
        menubar = tk.Menu(self)
        self._menubar = menubar  # 保存引用供状态更新

        # ===== 文件 =====
        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="加载 CSV", command=self.load_csv)
        fm.add_command(label="加载 CSV（新窗口）", command=self._open_new_window)
        fm.add_command(label="生成测试数据", command=self.generate_and_load)
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
            model_sub.add_radiobutton(label=md, variable=self._model_radio,
                                      value=md, command=lambda m=md: self._menu_set_model(m))
        dm.add_cascade(label="模型选择", menu=model_sub)
        # 变换子菜单
        trans_sub = tk.Menu(dm, tearoff=0)
        self._trans_radio = tk.StringVar(value='CDF')
        for t in TRANSFORM_OPTIONS:
            trans_sub.add_radiobutton(label=t, variable=self._trans_radio,
                                      value=t, command=lambda v=t: self._menu_set_transform(v))
        dm.add_cascade(label="变换选择", menu=trans_sub)
        menubar.add_cascade(label="数据", menu=dm)

        # ===== 绘图 =====
        pm = tk.Menu(menubar, tearoff=0)
        # X轴缩放
        x_sub = tk.Menu(pm, tearoff=0)
        self._xscale_radio = tk.StringVar(value='线性')
        for s in SCALE_DISPLAY:
            x_sub.add_radiobutton(label=s, variable=self._xscale_radio,
                                  value=s, command=lambda v=s: self._menu_set_xscale(v))
        pm.add_cascade(label="X 轴缩放", menu=x_sub)
        # Y轴缩放
        y_sub = tk.Menu(pm, tearoff=0)
        self._yscale_radio = tk.StringVar(value='线性')
        for s in SCALE_DISPLAY:
            y_sub.add_radiobutton(label=s, variable=self._yscale_radio,
                                  value=s, command=lambda v=s: self._menu_set_yscale(v))
        pm.add_cascade(label="Y 轴缩放", menu=y_sub)
        # 主题
        th_sub = tk.Menu(pm, tearoff=0)
        self._theme_radio = tk.StringVar(value='default')
        themes = ['default', 'ggplot', 'seaborn-v0_8', 'bmh', 'fivethirtyeight', 'dark_background', 'classic']
        for t in themes:
            th_sub.add_radiobutton(label=t, variable=self._theme_radio,
                                   value=t, command=lambda v=t: self._menu_set_theme(v))
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
            am.add_command(label=f"  {md}", command=lambda m=md: self._show_model_info(m))
        am.add_separator()
        am.add_command(label="版本: 1.0", command=None)
        menubar.add_cascade(label="关于", menu=am)

        self.config(menu=menubar)

    def _open_new_window(self):
        """在新窗口中打开另一个分布拟合工具实例"""
        path = filedialog.askopenfilename(
            filetypes=[('CSV 文件', '*.csv'), ('所有文件', '*.*')], parent=self)
        if path:
            try:
                df = pd.read_csv(path)
            except Exception as e:
                messagebox.showerror("加载错误", str(e), parent=self)
                return
            App(parent=self, dataframe=df)

    def _show_model_info(self, display_name):
        """弹窗显示模型公式和介绍（从模型实例读取）"""
        key = MODEL_KEY_MAP.get(display_name)
        if not key:
            return
        model = self.models.get(key)
        if not model:
            return
        formula = f'${model.get_formula()}$'
        desc = model.get_description()

        top = tk.Toplevel(self)
        top.title(display_name)
        top.geometry("520x420")
        top.resizable(False, False)

        # 公式图
        fig = Figure(figsize=(5, 0.7), dpi=100)
        fig.set_facecolor('#f5f5f5')
        fax = fig.add_subplot(111)
        fax.axis('off')
        fax.text(0.5, 0.5, formula, transform=fax.transAxes,
                 fontsize=14, ha='center', va='center')
        canvas = FigureCanvasTkAgg(fig, master=top)
        canvas.get_tk_widget().pack(fill=tk.X, padx=10, pady=(10, 5))
        canvas.draw()

        # 分隔线
        ttk.Separator(top, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # 描述文本
        text = tk.Text(top, wrap=tk.WORD, font=(FONT_FAMILY, 10), padx=10, pady=5,
                       relief=tk.FLAT, bg='#f5f5f5')
        text.insert(tk.END, desc)
        text.config(state=tk.DISABLED)
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=(0, 10))

    def _menu_set_model(self, label):
        self.model_var.set(label)
        self._on_model_change()

    def _menu_set_transform(self, val):
        self.transform_mode.set(val)
        self.update_plot()

    def _menu_set_xscale(self, val):
        self.scale_x.set(val)
        self.update_plot()

    def _menu_set_yscale(self, val):
        self.scale_y.set(val)
        self.update_plot()

    def _menu_set_theme(self, val):
        self.theme_var.set(val)
        self._apply_theme()

    def _menu_range_dialog(self):
        """弹窗设置 X/Y 范围"""
        dlg = tk.Toplevel(self)
        dlg.title("设置 X/Y 范围")
        dlg.geometry("300x180")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        f = ttk.Frame(dlg, padding=10)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="X 最小：").grid(row=0, column=0, sticky='e', pady=3)
        xmin_e = ttk.Entry(f, width=10)
        xmin_e.insert(0, self.xlim_min.get())
        xmin_e.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(f, text="X 最大：").grid(row=1, column=0, sticky='e', pady=3)
        xmax_e = ttk.Entry(f, width=10)
        xmax_e.insert(0, self.xlim_max.get())
        xmax_e.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(f, text="Y 最小：").grid(row=2, column=0, sticky='e', pady=3)
        ymin_e = ttk.Entry(f, width=10)
        ymin_e.insert(0, self.ylim_min.get())
        ymin_e.grid(row=2, column=1, sticky='w', padx=5)

        ttk.Label(f, text="Y 最大：").grid(row=3, column=0, sticky='e', pady=3)
        ymax_e = ttk.Entry(f, width=10)
        ymax_e.insert(0, self.ylim_max.get())
        ymax_e.grid(row=3, column=1, sticky='w', padx=5)

        def on_confirm():
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
        ttk.Button(c, text="添加列", command=self.add_selector).grid(row=r, column=0, sticky='w', padx=(0,1), pady=(0,1))
        ttk.Button(c, text="移除列", command=self.remove_last).grid(row=r, column=1, sticky='w', padx=(0,1), pady=(0,1))
        ttk.Button(c, text="导出图", command=self.export_image).grid(row=r, column=2, sticky='w', padx=(0,1), pady=(0,1))
        ttk.Button(c, text="导出参数", command=self.export_parameters).grid(row=r, column=3, sticky='w', padx=(0,1), pady=(0,1))
        r += 1

        LW = 5
        ttk.Label(c, text="模型：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky='e', padx=(0,1))
        self.model_var = tk.StringVar(value=MODEL_DISPLAY[0])
        mc = ttk.Combobox(c, textvariable=self.model_var, values=MODEL_DISPLAY, state='readonly', width=24)
        mc.grid(row=r, column=1, sticky='w')
        mc.bind('<<ComboboxSelected>>', lambda e: self._on_model_change())

        ttk.Label(c, text="变换：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=2, sticky='e', padx=(4,1))
        self.transform_mode = tk.StringVar(value='CDF')
        tc = ttk.Combobox(c, textvariable=self.transform_mode, values=TRANSFORM_OPTIONS, state='readonly', width=12)
        tc.grid(row=r, column=3, sticky='w')
        tc.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        r += 1

        self.formula_fig = Figure(figsize=(4.5, 0.55), dpi=100)
        self.formula_fig.set_facecolor('#f0f0f0')
        self.formula_ax = self.formula_fig.add_subplot(111)
        self.formula_ax.axis('off')
        self.formula_canvas = FigureCanvasTkAgg(self.formula_fig, master=c)
        self.formula_canvas.get_tk_widget().grid(row=r, column=0, columnspan=4, sticky='ew', pady=(1, 0))
        self._on_model_change()

    def _build_plot_control_panel(self, p):
        c = ttk.LabelFrame(p, text="绘图控制")
        c.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=4)
        LW = 5

        r = 0
        # X/Y 轴 + 主题 同行排列
        ttk.Label(c, text="X 轴：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky='e', padx=(0,1))
        self.scale_x = tk.StringVar(value='线性')
        xc = ttk.Combobox(c, textvariable=self.scale_x, values=SCALE_DISPLAY, state='readonly', width=6)
        xc.grid(row=r, column=1, sticky='w', padx=(0,2))
        xc.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

        ttk.Label(c, text="Y 轴：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=2, sticky='e', padx=(2,1))
        self.scale_y = tk.StringVar(value='线性')
        yc = ttk.Combobox(c, textvariable=self.scale_y, values=SCALE_DISPLAY, state='readonly', width=6)
        yc.grid(row=r, column=3, sticky='w', padx=(0,2))
        yc.bind('<<ComboboxSelected>>', lambda e: self.update_plot())

        ttk.Label(c, text="主题：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=4, sticky='e', padx=(2,1))
        self.theme_var = tk.StringVar(value='default')
        themes = ['default', 'ggplot', 'seaborn-v0_8', 'bmh', 'fivethirtyeight', 'dark_background', 'classic']
        th = ttk.Combobox(c, textvariable=self.theme_var, values=themes, state='readonly', width=12)
        th.grid(row=r, column=5, sticky='w')
        th.bind('<<ComboboxSelected>>', lambda e: self._apply_theme())
        r += 1
        ttk.Separator(c, orient=tk.HORIZONTAL).grid(row=r, column=0, columnspan=6, sticky='ew', pady=2)

        r += 1
        # X/Y 范围 + 按钮
        ttk.Label(c, text="X 范围：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=0, sticky='e', padx=(0,1))
        self.xlim_min = tk.StringVar(value='')
        ttk.Entry(c, textvariable=self.xlim_min, width=5).grid(row=r, column=1, sticky='w')
        ttk.Label(c, text="~", font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=2)
        self.xlim_max = tk.StringVar(value='')
        ttk.Entry(c, textvariable=self.xlim_max, width=5).grid(row=r, column=3, sticky='w')
        r += 1

        ttk.Label(c, text="Y 范围：", width=LW, anchor='e', font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=0, sticky='e', padx=(0,1))
        self.ylim_min = tk.StringVar(value='')
        ttk.Entry(c, textvariable=self.ylim_min, width=5).grid(row=r, column=1, sticky='w')
        ttk.Label(c, text="~", font=(FONT_FAMILY, FONT_SIZE - 1)).grid(row=r, column=2)
        self.ylim_max = tk.StringVar(value='')
        ttk.Entry(c, textvariable=self.ylim_max, width=5).grid(row=r, column=3, sticky='w')
        r += 1

        ttk.Button(c, text="取消选中", command=self._clear_selection).grid(row=r, column=0, columnspan=3, pady=2, sticky='ew', padx=(0,1))
        ttk.Button(c, text="应用范围", command=self.update_plot).grid(row=r, column=3, columnspan=3, pady=2, sticky='ew', padx=(1,0))
        r += 1

        ttk.Button(c, text="绘制 limit 线", command=self._draw_limit_lines).grid(row=r, column=0, columnspan=6, pady=2, sticky='ew')

    def _draw_limit_lines(self):
        """重新绘图并绘制 limit 竖线"""
        self.update_plot()
        if not self.ax or not self._plot_meta:
            return
        seen = set()
        for meta in self._plot_meta:
            col = meta['col']
            si = meta['selector_idx']
            if si in seen:
                continue
            seen.add(si)
            try:
                limit = self.selectors[si].get_limit()
            except Exception:
                continue
            color = meta['color']
            self.ax.axvline(x=limit, color=color, linestyle=':', alpha=0.7, linewidth=1.5)
            self.ax.text(limit, 0.02, f'{col}={limit:.3g}', color=color, fontsize=7,
                         rotation=90, va='bottom', ha='right',
                         transform=self.ax.get_xaxis_transform())
        self.canvas.draw_idle()

    def _apply_theme(self):
        theme = self.theme_var.get()
        try:
            if theme == 'default':
                plt.style.use('default')
            else:
                plt.style.use(theme)
        except Exception:
            pass
        self.update_plot()

    def _build_export_panel(self, p):
        f = ttk.LabelFrame(p, text="导出")
        f.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4, ipadx=6, ipady=4)
        ttk.Button(f, text="导出图片\n(PNG/PDF)", command=self.export_image).pack(fill=tk.X, pady=3, padx=4)
        ttk.Button(f, text="导出参数\n(CSV)", command=self.export_parameters).pack(fill=tk.X, pady=3, padx=4)

    def _build_middle_area(self):
        m = ttk.Frame(self)
        m.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
        pf = ttk.LabelFrame(m, text="图表")
        pf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.canvas_frame = ttk.Frame(pf)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        sf = ttk.LabelFrame(m, text="统计信息")
        sf.pack(side=tk.LEFT, fill=tk.BOTH, padx=4, pady=4, ipadx=2)
        self.mode_label = ttk.Label(sf, text="", font=(FONT_FAMILY, 8),
                                    foreground='#555555', anchor=tk.W)
        self.mode_label.pack(fill=tk.X, padx=2, pady=(0, 2))
        tc = ttk.Frame(sf)
        tc.pack(fill=tk.BOTH, expand=True)
        self.stats_tree = ttk.Treeview(tc, columns=('值',),
                                       show='tree headings', height=22)
        self.stats_tree.heading('值', text='值')
        self.stats_tree.column('#0', width=160, anchor='w', stretch=False)
        self.stats_tree.column('值', width=180, anchor='w', stretch=False)
        sy = ttk.Scrollbar(tc, orient=tk.VERTICAL, command=self.stats_tree.yview)
        sx = ttk.Scrollbar(tc, orient=tk.HORIZONTAL, command=self.stats_tree.xview)
        self.stats_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.stats_tree.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        tc.grid_rowconfigure(0, weight=1)
        tc.grid_columnconfigure(0, weight=1)
        self.stats_tree.bind("<MouseWheel>", self._on_tree_mousewheel)

    # ==================== 选择器 ====================

    def _make_selector(self):
        return SeriesSelector(self.left_inner, self.value_columns, len(self.selectors),
                              remove_callback=self._remove_selector,
                              manual_remove_callback=self._on_manual_remove,
                              auto_remove_callback=self._on_auto_remove,
                              restore_callback=self._on_restore,
                              selection_change_callback=lambda s: self.update_plot())

    def add_selector(self):
        if len(self.selectors) >= self.max_series:
            messagebox.showinfo("已达上限", f"最多支持 {self.max_series} 列", parent=self)
            return
        s = self._make_selector()
        s.pack(fill=tk.X, pady=1)
        self.selectors.append(s)
        self.update_plot()

    def remove_last(self):
        if self.selectors:
            self.selectors.pop().destroy()
            self.update_plot()

    def _remove_selector(self, s):
        if s in self.selectors:
            self.selectors.remove(s)
            s.destroy()
            self.update_plot()

    def _on_model_change(self):
        k = MODEL_KEY_MAP.get(self.model_var.get(), 'Weibull')
        formula = self.models[k].get_formula()
        self.formula_ax.clear()
        self.formula_ax.axis('off')
        self.formula_ax.text(0.5, 0.5, f'${formula}$', transform=self.formula_ax.transAxes,
                             fontsize=14, ha='center', va='center')
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
        self._active_selector_idx = sel.idx if self._active_selector_idx != sel.idx else None
        self._clear_selection()
        self._update_mode_label()
        self.canvas.draw_idle()

    def _on_auto_remove(self, sel):
        if self.data is None:
            return
        c = sel.get_selection()
        if not c or c not in self.data.columns:
            return
        if self.original_data is None:
            self.original_data = self.data.copy()
        model = self.models[self.current_model]
        cnt = 0
        for meta in self._plot_meta:
            if meta['selector_idx'] != sel.idx or meta['col'] != c:
                continue
            try:
                popt, _, _, _, _ = model.fit(meta['samples'])
                yp = model.cdf(meta['samples'], popt)
                yt = np.arange(1, len(yp) + 1) / (len(yp) + 1)
                res = np.abs(yt - yp)
                th = 3 * np.std(res)
                mask = res > th
                if mask.any():
                    drop = meta['df_indices'][mask]
                    self.data.loc[drop, c] = np.nan
                    cnt += mask.sum()
            except Exception:
                continue
        if cnt:
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()
        messagebox.showinfo("自动去除", f"列 {c} 已自动去除 {cnt} 个离群点。", parent=self)

    def _on_restore(self, sel=None):
        if self.original_data is not None:
            self.data = self.original_data.copy()
            self.original_data = None
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()
            messagebox.showinfo("恢复", "数据已恢复到最初加载状态。", parent=self)

    def _update_mode_label(self):
        if self._active_selector_idx is not None:
            sel = self.selectors[self._active_selector_idx]
            self.mode_label.config(
                text=f"⚠ 手动去除：右键框选去除「{sel.get_selection()}」数据点（再点退出）",
                foreground='red')
        else:
            self.mode_label.config(
                text="● 普通：单击选点 / 右键框选 / 双击显示数据",
                foreground='#555555')

    def _on_box_select_virtual(self, x0, y0, x1, y1):
        """手动框选回调，x0,y0,x1,y1 为数据坐标"""
        xmin, xmax = sorted([x0, x1])
        ymin, ymax = sorted([y0, y1])
        sel = []
        for m in self._plot_meta:
            if self._active_selector_idx is not None and m['selector_idx'] != self._active_selector_idx:
                continue
            inside = (m['xs'] >= xmin) & (m['xs'] <= xmax) & (m['ys'] >= ymin) & (m['ys'] <= ymax)
            for i in np.where(inside)[0]:
                sel.append({'col': m['col'], 'group': m.get('group'),
                            'df_indices': m['df_indices'], 'samples': m['samples'],
                            'point_idx': int(i), 'x_raw': float(m['xs'][i]),
                            'y_cdf': float(m['ys'][i]), 'df_idx': m['df_indices'][i]})
        if not sel:
            return
        if self._active_selector_idx is not None:
            self._confirm_remove(sel)
        else:
            self._highlight_selected(sel)

    def _highlight_selected(self, sel):
        self._clear_selection()
        self._selected_meta = sel
        if sel:
            hl = self.ax.scatter([s['x_raw'] for s in sel], [s['y_cdf'] for s in sel],
                                 s=80, facecolor='none', edgecolor='red', linewidth=2, zorder=10)
            self._highlight_artists.append(hl)
            self.canvas.draw_idle()

    def _confirm_remove(self, sel):
        lines = [f"以下 {len(sel)} 个点将被去除：\n", f"列: {sel[0]['col']}\n", "-" * 50 + "\n"]
        for i, s in enumerate(sel[:20]):
            g = f" [{s.get('group', '-')}]" if s.get('group') else ""
            lines.append(f"  #{i+1}: 值={s['x_raw']:.6g}  CDF={s['y_cdf']:.4f}{g}\n")
        if len(sel) > 20:
            lines.append(f"  ... 还有 {len(sel) - 20} 个\n")
        if messagebox.askyesno("确认去除", "".join(lines), parent=self):
            if self.original_data is None:
                self.original_data = self.data.copy()
            for s in sel:
                self.data.loc[s['df_idx'], s['col']] = np.nan
            self._active_selector_idx = None
            self.fit_results.clear()
            self.stats_cache.clear()
            self.update_plot()

    # ==================== 数据加载 ====================

    def _apply_dataframe(self, df):
        info = detect_columns(df)
        self.data = df
        self.original_data = df.copy()
        self.columns = info['columns']
        self.group_column = info['group_column']
        self.value_columns = info['value_columns']
        self.fit_results.clear()
        self.stats_cache.clear()
        for s in self.selectors:
            s.combo['values'] = self.value_columns
            s.columns = self.value_columns
            if self.value_columns:
                s.combo.current(0)
        self.update_plot()

    def load_dataframe(self, df):
        if not isinstance(df, pd.DataFrame):
            raise TypeError("参数必须是 pandas DataFrame")
        self._apply_dataframe(df)

    def load_csv(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[('CSV 文件', '*.csv'), ('所有文件', '*.*')], parent=self)
            if not path:
                return
        try:
            self._apply_dataframe(pd.read_csv(path))
        except Exception as e:
            messagebox.showerror("加载错误", str(e), parent=self)

    def generate_and_load(self):
        p = default_test_path()
        generate_test_data(p)
        self.load_csv(p)

    # ==================== 绘图 ====================

    def update_plot(self):
        if self.data is None or not self.selectors:
            return
        self.current_model = MODEL_KEY_MAP.get(self.model_var.get(), 'Weibull')
        model = self.models[self.current_model]
        self._active_selector_idx = None
        if self.figure:
            plt.close(self.figure)
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.ax = ax = self.figure.add_subplot(111)
        groups = sorted(self.data[self.group_column].unique()) if self.group_column else ['All']
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
                    self._fit_plot(ax, model, sub.values, sub.index.values, c, g, si, gcolors[g])
            else:
                sub = self.data[c].dropna()
                if len(sub) >= 3:
                    self._fit_plot(ax, model, sub.values, sub.index.values, c, None, si, gcolors['All'])
        tr = self.transform_mode.get()
        yt = 'CDF' if tr == 'CDF' else 'ln(-ln(1-CDF))'
        ax.set_xlabel('')
        ax.set_ylabel(yt, fontsize=12)
        ax.set_title(f'{self.current_model} Distribution Fit', fontsize=14, fontweight='bold')
        ax.set_xscale(SCALE_MAP.get(self.scale_x.get(), self.scale_x.get()))
        ax.set_yscale(SCALE_MAP.get(self.scale_y.get(), self.scale_y.get()))
        # 科学计数法：跨量级时每个 tick 独立显示 a.aa×10ⁿ
        from matplotlib.ticker import FuncFormatter
        def _sci_fmt(v, _):
            if v == 0:
                return '0'
            exp = int(np.floor(np.log10(abs(v))))
            mant = v / 10**exp
            if abs(exp) <= 1:
                return f'{v:#.4g}'
            return f'{mant:.2f}e{exp:+d}'
        ax.xaxis.set_major_formatter(FuncFormatter(_sci_fmt))
        ax.yaxis.set_major_formatter(FuncFormatter(_sci_fmt))
        self._apply_axis_limits(ax)
        # 构建分层图例：列名(带marker) → 分组(R²)
        from matplotlib.lines import Line2D
        leg = []
        mklist = ['o', 's', '^', 'D', 'v', 'p', '*', 'X']
        lslist = ['-', '--', '-.', ':']
        col_done = set()
        for m in self._plot_meta:
            c = m['col']
            g = m.get('group')
            si = m['selector_idx']
            mk = mklist[si % len(mklist)]
            ls = lslist[si % len(lslist)]
            if c not in col_done:
                col_done.add(c)
                leg.append(Line2D([0], [0], marker=mk, color='#444444', linestyle=ls,
                                  label=f'— {c} —', markersize=8, linewidth=2))
            key = (c, g if g else 'All')
            r2 = self.fit_results.get(key, (None, None, 0, None, None))[2]
            gtxt = g if g else ''
            leg.append(Line2D([0], [0], marker=mk, color=m['color'], linestyle=ls,
                              label=f'  {gtxt}  R²={r2:.4f}', markersize=6, linewidth=2))
        ax.legend(handles=leg, loc='best', fontsize=9, framealpha=0.9, handlelength=4.0)
        ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self._embed_canvas()
        self._setup_interaction()
        self._update_stats_tree()

    def _fit_plot(self, ax, model, samples, df_indices, col, group, si, color):
        s = np.asarray(samples)
        idx = np.argsort(s)
        ss, di = s[idx], np.asarray(df_indices)[idx]
        try:
            popt, pcov, r2, xs, cdf = model.fit(ss)
        except Exception:
            return
        tr = self.transform_mode.get()
        y = cdf if tr == 'CDF' else np.log(np.maximum(-np.log(np.maximum(1 - cdf, 1e-10)), 1e-10))
        # 不同列不同 marker / 不同 group 同一列用同 marker
        markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'X']
        linestyles = ['-', '--', '-.', ':']
        mk = markers[si % len(markers)]
        ls = linestyles[si % len(linestyles)]
        art = ax.scatter(xs, y, alpha=0.6, s=40, color=color,
                         edgecolor='none', picker=5, marker=mk)
        # 拟合曲线延伸覆盖 limit
        limit = self.selectors[si].get_limit()
        xf_min = min(xs.min() * 0.95, limit * 0.9) if limit > 0 else xs.min() * 0.95
        xf_max = max(xs.max() * 1.05, limit * 1.1) if limit > 0 else xs.max() * 1.05
        xf = np.linspace(xf_min, xf_max, 200)
        yc = model.cdf(xf, popt)
        if tr != 'CDF':
            yc = np.log(np.maximum(-np.log(np.maximum(1 - yc, 1e-10)), 1e-10))
        ax.plot(xf, yc, color=color, linestyle=ls, alpha=0.8, linewidth=2)
        key = (col, group if group else 'All')
        self.fit_results[key] = (model.name, popt, r2, xs, cdf)
        stats = self._stats(ss)
        # 计算 limit 处模型值
        try:
            limit = self.selectors[si].get_limit()
            stats['F_at_limit'] = model.cdf(limit, popt)
        except Exception:
            pass
        self.stats_cache[key] = stats
        self._plot_meta.append({'artist': art, 'col': col, 'group': group,
                                'selector_idx': si, 'df_indices': di,
                                'xs': xs, 'ys': y, 'samples': ss, 'color': color})

    @staticmethod
    def _stats(s):
        s = np.asarray(s)
        return {'count': len(s), 'mean': np.mean(s),
                'std': np.std(s, ddof=1) if len(s) > 1 else 0.0,
                'median': np.median(s), 'p5': np.percentile(s, 5),
                'p95': np.percentile(s, 95), 'min': np.min(s), 'max': np.max(s)}

    def _apply_axis_limits(self, ax):
        """应用用户设定的 X/Y 轴范围"""
        try:
            if self.xlim_min.get():
                ax.set_xlim(left=float(self.xlim_min.get()))
            if self.xlim_max.get():
                ax.set_xlim(right=float(self.xlim_max.get()))
            if self.ylim_min.get():
                ax.set_ylim(bottom=float(self.ylim_min.get()))
            if self.ylim_max.get():
                ax.set_ylim(top=float(self.ylim_max.get()))
        except ValueError:
            pass

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
        except Exception:
            pass

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
            if event.button == 3 and event.inaxes and event.xdata and event.ydata:
                self._box_start = (event.xdata, event.ydata)

        def on_motion(event):
            if self._box_start and event.inaxes and event.xdata and event.ydata:
                if self._box_patch:
                    self._box_patch.remove()
                x0, y0 = self._box_start
                import matplotlib.patches as mpatches
                self._box_patch = mpatches.Rectangle(
                    (min(x0, event.xdata), min(y0, event.ydata)),
                    abs(event.xdata - x0), abs(event.ydata - y0),
                    fill=True, facecolor='blue', edgecolor='blue', alpha=0.2)
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
                if x1 is None or y1 is None:
                    return
                self._on_box_select_virtual(x0, y0, x1, y1)
                self.canvas.draw_idle()

        self.canvas.mpl_connect('button_press_event', on_press)
        self.canvas.mpl_connect('motion_notify_event', on_motion)
        self.canvas.mpl_connect('button_release_event', on_release)

        def on_pick(event):
            if len(event.ind) == 0:
                return
            for m in self._plot_meta:
                if m['artist'] is event.artist:
                    if self._active_selector_idx is not None and m['selector_idx'] != self._active_selector_idx:
                        continue
                    sel = []
                    for i in event.ind:
                        sel.append({'col': m['col'], 'group': m.get('group'),
                                    'point_idx': int(i), 'x_raw': float(m['xs'][i]),
                                    'y_cdf': float(m['ys'][i]), 'df_idx': m['df_indices'][i],
                                    'df_indices': m['df_indices'], 'samples': m['samples']})
                    if self._active_selector_idx is not None:
                        same = [s for s in self._selected_meta if s['col'] == m['col']]
                        ex = {s['point_idx'] for s in same}
                        new = [s for s in sel if s['point_idx'] not in ex]
                        self._selected_meta = same + new
                        self._redraw_hl()
                    else:
                        self._highlight_selected(sel)
                    break

        self.canvas.mpl_connect('pick_event', on_pick)

        def on_dbl(event):
            if self._selected_meta:
                if self._active_selector_idx is not None:
                    self._confirm_remove(list(self._selected_meta))
                else:
                    self._show_popup(self._selected_meta)

        self.canvas.get_tk_widget().bind('<Double-Button-1>', on_dbl)

    def _redraw_hl(self):
        for a in self._highlight_artists:
            a.remove()
        self._highlight_artists.clear()
        if self._selected_meta:
            hl = self.ax.scatter([s['x_raw'] for s in self._selected_meta],
                                 [s['y_cdf'] for s in self._selected_meta],
                                 s=80, facecolor='none', edgecolor='red', linewidth=2, zorder=10)
            self._highlight_artists.append(hl)
            self.canvas.draw_idle()

    def _clear_selection(self):
        for a in self._highlight_artists:
            a.remove()
        self._highlight_artists.clear()
        self._selected_meta.clear()
        if self.canvas:
            self.canvas.draw_idle()

    def _show_popup(self, sm):
        """Treeview 弹窗：按列→分组折叠显示全部数据"""
        top = tk.Toplevel(self)
        top.title("数据点详情")
        top.geometry("650x500")

        tv = ttk.Treeview(top, columns=('PART_ID', '值'), show='tree headings')
        tv.heading('PART_ID', text='PART_ID')
        tv.heading('值', text='值')
        tv.column('PART_ID', width=150, anchor='w')
        tv.column('值', width=150, anchor='e')

        # 按列→分组组织，同时收集最大文本宽度
        max_len = 0
        by_col = {}
        for s in sm:
            by_col.setdefault(s['col'], []).append(s)
            max_len = max(max_len, len(s['col']))
        for col, items in sorted(by_col.items()):
            cn = tv.insert('', tk.END, text=col, values=('', ''), open=True)
            by_grp = {}
            for s in items:
                r = self.data.iloc[s['df_idx']]
                g = r.get(self.group_column, '-') if self.group_column else '-'
                max_len = max(max_len, len(str(g)))
                pid = str(r.get('PART_ID', r.get('part_id', str(s['df_idx']))))
                by_grp.setdefault(g, []).append((pid, s['x_raw']))
            for g, pts in sorted(by_grp.items()):
                gn = tv.insert(cn, tk.END, text=g, values=('', ''), open=True)
                for pid, val in pts:
                    tv.insert(gn, tk.END, text='', values=(pid, f'{val:.6g}'))

        # 自适应列宽：每字符约 10px + 缩进余量
        tv.column('#0', width=max(80, max_len * 10 + 40), anchor='w', stretch=False)

        sy = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tv.yview)
        sx = ttk.Scrollbar(top, orient=tk.HORIZONTAL, command=tv.xview)
        tv.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tv.grid(row=0, column=0, sticky='nsew')
        sy.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure(0, weight=1)

    # ==================== 统计信息 ====================

    def _update_stats_tree(self):
        t = self.stats_tree
        for item in t.get_children():
            t.delete(item)
        if not self.fit_results:
            t.insert('', tk.END, text='无数据', values=('',))
            return
        bc = {}
        for (col, grp), (mn, params, r2, xs, cdf) in sorted(self.fit_results.items()):
            bc.setdefault(col, []).append((grp, mn, params, r2))
        for col, items in sorted(bc.items()):
            cn = t.insert('', tk.END, text=col, values=('',), open=True)
            for grp, mn, params, r2 in items:
                gt = grp if grp != 'All' else '(全部)'
                gn = t.insert(cn, tk.END, text=gt, values=('',), open=True)
                model = self.models[mn]
                t.insert(gn, tk.END, text='模型', values=(mn,))
                t.insert(gn, tk.END, text='R²', values=(f'{r2:.6f}',))
                for pn, pv in zip(model.get_param_names(), params):
                    t.insert(gn, tk.END, text=pn, values=(f'{pv:.6g}',))
                st = self.stats_cache.get((col, grp), {})
                for lbl, k in [('样本数', 'count'), ('均值', 'mean'), ('标准差', 'std'),
                               ('中位数', 'median'), ('5%分位数', 'p5'), ('95%分位数', 'p95'),
                               ('最小值', 'min'), ('最大值', 'max'),
                               ('limit处F值', 'F_at_limit')]:
                    v = st.get(k)
                    if v is not None:
                        t.insert(gn, tk.END, text=lbl,
                                 values=(f'{v:.6g}' if isinstance(v, float) else str(v),))

    def _on_tree_mousewheel(self, e):
        self.stats_tree.yview_scroll(-1 if e.delta > 0 else 1, "units")

    # ==================== 导出 ====================

    def export_image(self):
        if self.figure is None:
            messagebox.showwarning("导出", "没有可导出的图表", parent=self)
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 文件", "*.png"), ("PDF 文件", "*.pdf"), ("所有文件", "*.*")],
            parent=self)
        if p:
            try:
                self.figure.savefig(p, dpi=300, bbox_inches='tight')
                messagebox.showinfo("导出", f"图表已保存至：\n{p}", parent=self)
            except Exception as e:
                messagebox.showerror("导出错误", str(e), parent=self)

    def export_parameters(self):
        if not self.fit_results:
            messagebox.showwarning("导出", "没有可导出的拟合结果", parent=self)
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")],
            parent=self)
        if p:
            try:
                rows = []
                for (col, grp), (mn, params, r2, xs, cdf) in sorted(self.fit_results.items()):
                    model = self.models[mn]
                    st = self.stats_cache.get((col, grp), {})
                    row = {'Column': col, 'Group': grp, 'Model': mn,
                           'R_squared': f'{r2:.6f}', 'Sample_Count': len(xs),
                           'Mean': f'{st.get("mean", 0):.6g}',
                           'Std': f'{st.get("std", 0):.6g}',
                           'Median': f'{st.get("median", 0):.6g}',
                           'P5': f'{st.get("p5", 0):.6g}',
                           'P95': f'{st.get("p95", 0):.6g}'}
                    for pn, pv in zip(model.get_param_names(), params):
                        row[pn.replace(' ', '_')] = f'{pv:.6g}'
                    rows.append(row)
                pd.DataFrame(rows).to_csv(p, index=False)
                messagebox.showinfo("导出", f"参数已保存至：\n{p}", parent=self)
            except Exception as e:
                messagebox.showerror("导出错误", str(e), parent=self)


if __name__ == '__main__':
    app = App()
    app._tk_root.mainloop()
