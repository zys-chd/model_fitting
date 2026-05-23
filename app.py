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
        self.geometry("1400x900")
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
        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="加载 CSV", command=self.load_csv)
        fm.add_command(label="生成测试数据", command=self.generate_and_load)
        fm.add_separator()
        fm.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=fm)
        self.config(menu=menubar)

    def _build_top_bar(self):
        tf = ttk.Frame(self)
        tf.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        self._build_column_selector(tf)
        self._build_control_panel(tf)
        self._build_export_panel(tf)

    def _build_column_selector(self, p):
        f = ttk.LabelFrame(p, text="数值列")
        f.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)
        self.left_inner = ttk.Frame(f)
        self.left_inner.pack()

    def _build_control_panel(self, p):
        c = ttk.LabelFrame(p, text="显示控制")
        c.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # 统一使用 grid 布局对齐
        r = 0
        ttk.Button(c, text="添加列", command=self.add_selector).grid(row=r, column=0, padx=2, pady=2, sticky='w')
        ttk.Button(c, text="移除列", command=self.remove_last).grid(row=r, column=1, padx=2, pady=2, sticky='w')
        r += 1
        ttk.Separator(c, orient=tk.HORIZONTAL).grid(row=r, column=0, columnspan=4, sticky='ew', pady=4)
        r += 1

        ttk.Label(c, text="模型：", font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky='w')
        self.model_var = tk.StringVar(value=MODEL_DISPLAY[0])
        mc = ttk.Combobox(c, textvariable=self.model_var, values=MODEL_DISPLAY,
                          state='readonly', width=18)
        mc.grid(row=r, column=1, sticky='w')
        mc.bind('<<ComboboxSelected>>', lambda e: self._on_model_change())
        ttk.Label(c, text="变换：", font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=2, sticky='w', padx=(8, 0))
        self.transform_mode = tk.StringVar(value='CDF')
        ttk.Combobox(c, textvariable=self.transform_mode, values=TRANSFORM_OPTIONS,
                     state='readonly', width=11).grid(row=r, column=3, sticky='w')
        r += 1

        ttk.Label(c, text="X 轴：", font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky='w')
        self.scale_x = tk.StringVar(value='线性')
        ttk.Combobox(c, textvariable=self.scale_x, values=SCALE_DISPLAY,
                     state='readonly', width=11).grid(row=r, column=1, sticky='w')
        ttk.Label(c, text="Y 轴：", font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=2, sticky='w', padx=(8, 0))
        self.scale_y = tk.StringVar(value='线性')
        ttk.Combobox(c, textvariable=self.scale_y, values=SCALE_DISPLAY,
                     state='readonly', width=11).grid(row=r, column=3, sticky='w')
        r += 1

        # LaTeX 公式渲染区（用 matplotlib figure 渲染后嵌入）
        self.formula_fig = Figure(figsize=(4.5, 0.55), dpi=100)
        self.formula_fig.set_facecolor('#f0f0f0')
        self.formula_ax = self.formula_fig.add_subplot(111)
        self.formula_ax.axis('off')
        self.formula_canvas = FigureCanvasTkAgg(self.formula_fig, master=c)
        self.formula_canvas.get_tk_widget().grid(row=r, column=0, columnspan=4, sticky='ew', pady=(2, 0))
        self._on_model_change()

    def _build_export_panel(self, p):
        f = ttk.LabelFrame(p, text="导出")
        f.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)
        ttk.Button(f, text="导出图片\n(PNG/PDF)", command=self.export_image).pack(fill=tk.X, pady=2)
        ttk.Button(f, text="导出参数\n(CSV)", command=self.export_parameters).pack(fill=tk.X, pady=2)

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
                text="● 普通：单击/右键框选高亮，双击显示数据",
                foreground='#555555')

    def _on_box_select(self, eclick, erelease):
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        if None in (x1, y1, x2, y2):
            return
        xmin, xmax = sorted([x1, x2])
        ymin, ymax = sorted([y1, y2])
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
        if self._rect_selector is not None:
            self._rect_selector.set_active(False)
            self._rect_selector = None
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
        ax.set_xlabel('X 值', fontsize=12)
        ax.set_ylabel(yt, fontsize=12)
        ax.set_title(f'{self.current_model} 分布拟合', fontsize=14, fontweight='bold')
        ax.set_xscale(SCALE_MAP.get(self.scale_x.get(), self.scale_x.get()))
        ax.set_yscale(SCALE_MAP.get(self.scale_y.get(), self.scale_y.get()))
        ax.xaxis.set_major_formatter(_SCIFMT)
        ax.yaxis.set_major_formatter(_SCIFMT)
        ax.legend(loc='best', fontsize=9, framealpha=0.9)
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
        lbl = f'{col}' + (f' - {group}' if group else '') + f' (R²={r2:.4f})'
        art = ax.scatter(xs, y, alpha=0.6, s=40, color=color, label=lbl,
                         edgecolor='none', picker=5, marker=mk)
        xf = np.linspace(xs.min(), xs.max() * 1.1, 200)
        yc = model.cdf(xf, popt)
        if tr != 'CDF':
            yc = np.log(np.maximum(-np.log(np.maximum(1 - yc, 1e-10)), 1e-10))
        ax.plot(xf, yc, color=color, linestyle=ls, alpha=0.8, linewidth=2)
        key = (col, group if group else 'All')
        self.fit_results[key] = (model.name, popt, r2, xs, cdf)
        self.stats_cache[key] = self._stats(ss)
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
        if self._rect_selector is not None:
            self._rect_selector.set_active(False)
            self._rect_selector = None
        props = dict(facecolor='blue', edgecolor='blue', alpha=0.2, fill=True)
        self._rect_selector = RectangleSelector(
            self.ax, self._on_box_select, useblit=True, button=[3],
            minspanx=0.5, minspany=0.5, spancoords='data',
            interactive=False, props=props)

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

        def on_press(event):
            if event.inaxes is None:
                self._clear_selection()
                self.canvas.draw_idle()

        self.canvas.mpl_connect('pick_event', on_pick)
        self.canvas.mpl_connect('button_press_event', on_press)

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

    def _show_popup(self, sm):
        """Treeview 弹窗：按列→分组折叠显示全部数据"""
        top = tk.Toplevel(self)
        top.title("数据点详情")
        top.geometry("650x500")

        tv = ttk.Treeview(top, columns=('PART_ID', 'group', '值'), show='tree headings')
        tv.heading('PART_ID', text='PART_ID')
        tv.heading('group', text='分组')
        tv.heading('值', text='值')
        tv.column('#0', width=40, anchor='w', stretch=False)
        tv.column('PART_ID', width=120, anchor='w')
        tv.column('group', width=80, anchor='w')
        tv.column('值', width=120, anchor='e')

        # 按列→分组组织
        by_col = {}
        for s in sm:
            by_col.setdefault(s['col'], []).append(s)
        for col, items in sorted(by_col.items()):
            cn = tv.insert('', tk.END, text=col, values=('', '', ''), open=True)
            by_grp = {}
            for s in items:
                r = self.data.iloc[s['df_idx']]
                g = r.get(self.group_column, '-') if self.group_column else '-'
                pid = str(r.get('PART_ID', r.get('part_id', str(s['df_idx']))))
                by_grp.setdefault(g, []).append((pid, s['x_raw']))
            for g, pts in sorted(by_grp.items()):
                gn = tv.insert(cn, tk.END, text=g, values=('', '', ''), open=True)
                for pid, val in pts:
                    tv.insert(gn, tk.END, text='', values=(pid, g, f'{val:.6g}'))

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
                               ('最小值', 'min'), ('最大值', 'max')]:
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
