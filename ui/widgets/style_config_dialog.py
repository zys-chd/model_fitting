"""
样式配置对话框 — 左右分栏布局

左侧：按钮列表（Canvas+Scrollbar），选中项高亮背景
右侧：Notebook 三标签页（散点/拟合曲线/其他）
底部：确定 / 应用 / 取消

说明：
- 不实时更新，修改在点击「确定」或「应用」后生效
- 「应用」调用 apply_series_styles() 轻量更新（不重建画布）
- 「确定」同应用 + 关闭对话框
- 「取消」放弃当前修改，关闭对话框
"""
import tkinter as tk
from tkinter import ttk

try:
    from ...config import FONT_FAMILY, FONT_SIZE
    from ...config import COLOR_PALETTES, COLOR_PALETTE_KEYS
    from ...widgets import MARKER_ICONS, LINESTYLE_ICONS, SeriesSelector
except ImportError:
    from config import FONT_FAMILY, FONT_SIZE
    from config import COLOR_PALETTES, COLOR_PALETTE_KEYS
    from widgets import MARKER_ICONS, LINESTYLE_ICONS, SeriesSelector


# 选中项的高亮色（浅蓝底深蓝字）
_SELECTED_BG = "#D0E4F7"
_SELECTED_FG = "#1A1A1A"
_NORMAL_BG = "#F0F0F0"
_NORMAL_FG = "#333333"
_BTN_PAD_Y = 6


class _ItemButton(ttk.Frame):
    """左侧列表中的可点击条目（用 ttk.Frame + 内部 Label，确保点击事件可靠）"""

    def __init__(self, master, text, idx, on_click, selected=False):
        super().__init__(master, cursor="hand2")
        self.idx = idx
        self._on_click = on_click
        self._selected = False
        self._text = text

        self._label = tk.Label(
            self, text=text, anchor="w", padx=8,
            font=(FONT_FAMILY, FONT_SIZE),
            bg=_NORMAL_BG, fg=_NORMAL_FG,
        )
        self._label.pack(fill=tk.X, ipady=_BTN_PAD_Y)

        # 多路绑定点击事件，确保任何位置点击都触发
        self._label.bind("<Button-1>", self._click)
        self.bind("<Button-1>", self._click)
        # 悬停
        self._label.bind("<Enter>", lambda e: self._on_hover(True))
        self._label.bind("<Leave>", lambda e: self._on_hover(False))
        self.bind("<Enter>", lambda e: self._on_hover(True))
        self.bind("<Leave>", lambda e: self._on_hover(False))

        self.set_selected(selected)

    def _click(self, event=None):
        if self._on_click:
            self._on_click(self.idx)

    def _on_hover(self, enter: bool):
        if not self._selected:
            bg = "#E8E8E8" if enter else _NORMAL_BG
            self._label.configure(bg=bg)

    def set_selected(self, selected: bool):
        self._selected = selected
        bg = _SELECTED_BG if selected else _NORMAL_BG
        fg = _SELECTED_FG if selected else _NORMAL_FG
        self._label.configure(bg=bg, fg=fg)

    def update_text(self, text: str):
        self._text = text
        self._label.configure(text=text)


class StyleConfigDialog(tk.Toplevel):
    """样式配置对话框 — 主窗口"""

    def __init__(self, parent, selectors: list, initial_idx: int = 0,
                 palette: str = "tab10", on_apply=None):
        """
        Parameters
        ----------
        parent : tk.Widget
            父窗口
        selectors : list[SeriesSelector]
            所有 SeriesSelector 实例
        initial_idx : int
            初始选中的 selector 索引
        on_apply : callable
            点击「确定」或「应用」时的回调 (full_redraw: bool) -> None
            - full_redraw=True 表示需要完整重建（调用 update_all）
            - full_redraw=False 表示只需轻量样式更新（调用 apply_series_styles）
        """
        super().__init__(parent)
        self.title("样式配置")
        self.geometry("680x540")
        self.resizable(True, True)
        self.minsize(600, 420)
        self.transient(parent)
        self.grab_set()

        self.selectors = selectors
        self._on_apply = on_apply
        self._current_idx = initial_idx
        self._current_palette = palette
        self._save_timer = None  # 用于延迟保存

        # ---- 顶部标题 ----
        header = ttk.Label(self, text="样式配置 — 选择数据项并自定义显示样式",
                           font=(FONT_FAMILY, FONT_SIZE + 2, "bold"))
        header.pack(fill=tk.X, padx=12, pady=(10, 2))

        # ---- 主体：左右分栏 ----
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # ========== 左侧：数据项按钮列表 ==========
        left_frame = ttk.LabelFrame(main, text="数据项", width=180)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 6))
        left_frame.pack_propagate(False)

        # Canvas + Scrollbar
        self._list_canvas = tk.Canvas(
            left_frame, highlightthickness=0, borderwidth=0,
            bg="#F8F8F8",
        )
        v_scroll = ttk.Scrollbar(
            left_frame, orient=tk.VERTICAL, command=self._list_canvas.yview,
        )
        self._list_canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0), pady=2)

        # Inner frame 放按钮
        self._list_inner = tk.Frame(self._list_canvas, bg="#F8F8F8")
        self._list_canvas_window = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw", width=170,
        )

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            self._list_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self._list_canvas.bind("<Enter>", lambda e: self._list_canvas.bind_all(
            "<MouseWheel>", _on_mousewheel))
        self._list_canvas.bind("<Leave>", lambda e: self._list_canvas.unbind_all("<MouseWheel>"))

        # 尺寸变化时更新 scroll region
        self._list_inner.bind("<Configure>", self._on_inner_configure)
        self._list_canvas.bind("<Configure>", self._on_canvas_configure)

        # 填充按钮
        self._item_buttons: list[_ItemButton] = []
        self._populate_buttons()

        # ========== 右侧：配置面板 ==========
        self._right_frame = ttk.Frame(main)
        self._right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Notebook（合并为「显示」+「其他」两个标签页）
        self._config_notebook = ttk.Notebook(self._right_frame)
        self._config_notebook.pack(fill=tk.BOTH, expand=True)

        self._build_display_tab()
        # 设置调色板初始值
        self._set_palette_combo(self._current_palette)
        self._build_other_tab()

        # ========== 底部按钮 ==========
        self._build_bottom_bar()

        # 选中初始项
        if 0 <= initial_idx < len(self._item_buttons):
            self._item_buttons[initial_idx].set_selected(True)
            self._current_idx = initial_idx
            self._load_current_style()

        # 窗口关闭：Esc 键 = 取消
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    # ==================== 左侧按钮列表 ====================

    def _populate_buttons(self):
        """填充或刷新左侧按钮列表"""
        # 清除旧按钮
        for btn in self._item_buttons:
            btn.destroy()
        self._item_buttons.clear()

        for i, sel in enumerate(self.selectors):
            col = sel.get_selection() or "(未选择)"
            text = f"#{i+1}  {col}"
            btn = _ItemButton(
                self._list_inner, text, i,
                on_click=self._on_item_click,
                selected=(i == self._current_idx),
            )
            btn.pack(fill=tk.X, padx=2, pady=1)
            self._item_buttons.append(btn)

    def _update_button_text(self):
        """更新所有按钮文本（列名可能变了）"""
        for i, btn in enumerate(self._item_buttons):
            col = self.selectors[i].get_selection() if i < len(self.selectors) else "(未选择)"
            btn.update_text(f"#{i+1}  {col}")

    def _on_inner_configure(self, event=None):
        """内部 Frame 尺寸变化 → 更新 scroll region"""
        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        """Canvas 尺寸变化 → 调整内部 Frame 宽度"""
        self._list_canvas.itemconfig(self._list_canvas_window, width=event.width - 4)

    def _on_item_click(self, idx: int):
        """点击左侧按钮 → 切换选中项"""
        if idx == self._current_idx:
            return
        # 取消旧选中的高亮
        if 0 <= self._current_idx < len(self._item_buttons):
            self._item_buttons[self._current_idx].set_selected(False)
        # 选中新项
        self._current_idx = idx
        self._item_buttons[idx].set_selected(True)
        # 强制加载并刷新
        self._load_current_style()
        try:
            self.update()
        except Exception:
            pass

    # ==================== 右侧标签页 ====================

    def _build_display_tab(self):
        """显示标签页 — 可滚动视图，含颜色/符号/曲线配置"""
        # 外层 Frame（Notebook 不直接参与滚动）
        outer = ttk.Frame(self._config_notebook, padding=0)
        self._config_notebook.add(outer, text="显示")

        # Canvas + Scrollbar
        self._disp_canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0, bg="#fcfcfc")
        v_scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=self._disp_canvas.yview)
        self._disp_canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._disp_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame（真正的内容容器）
        inner = ttk.Frame(self._disp_canvas, padding=12)
        self._disp_canvas_window = self._disp_canvas.create_window((0, 0), window=inner, anchor="nw")

        # 鼠标滚轮
        def _mw(ev):
            self._disp_canvas.yview_scroll(-1 if ev.delta > 0 else 1, "units")
        self._disp_canvas.bind("<Enter>", lambda e: self._disp_canvas.bind_all("<MouseWheel>", _mw))
        self._disp_canvas.bind("<Leave>", lambda e: self._disp_canvas.unbind_all("<MouseWheel>"))

        # 尺寸自适应
        inner.bind("<Configure>", lambda e: self._disp_canvas.configure(
            scrollregion=self._disp_canvas.bbox("all")))
        self._disp_canvas.bind("<Configure>", lambda e: self._disp_canvas.itemconfig(
            self._disp_canvas_window, width=e.width - 4))

        # ========== 以下内容全部放在 inner 中 ==========
        # ──── 颜色与循环 ────
        color_lf = ttk.LabelFrame(inner, text="颜色与循环", padding=8)
        color_lf.pack(fill=tk.X, pady=(0, 8))

        r = 0
        ttk.Label(color_lf, text="调色板：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
        pal_displays = [COLOR_PALETTES[k]["name"] for k in COLOR_PALETTE_KEYS]
        self._palette_var = tk.StringVar()
        self._palette_combo = ttk.Combobox(
            color_lf, textvariable=self._palette_var,
            values=pal_displays, state="readonly",
            width=22, font=(FONT_FAMILY, FONT_SIZE),
        )
        self._palette_combo.grid(row=r, column=1, columnspan=2, sticky="ew", pady=3)
        self._palette_combo.bind("<<ComboboxSelected>>", self._on_palette_change)
        color_lf.columnconfigure(1, weight=1)
        r += 1

        # 色带
        self._palette_strip = tk.Canvas(
            color_lf, height=16, highlightthickness=1,
            highlightbackground="#cccccc", borderwidth=0,
        )
        self._palette_strip.grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=(0, 4))
        r += 1

        # 自定义颜色开关 + 格子
        self._use_custom_color_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            color_lf, text="使用自定义颜色",
            variable=self._use_custom_color_var,
        ).grid(row=r, column=0, columnspan=3, sticky="w", padx=8, pady=1)
        r += 1

        color_grid = ttk.Frame(color_lf)
        color_grid.grid(row=r, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        self._custom_color_slots: list[tk.Canvas] = []
        self._custom_color_values: list[str] = [""] * 10
        for ci in range(10):
            slot = tk.Canvas(
                color_grid, width=22, height=22,
                highlightthickness=2, highlightbackground="#dddddd",
                borderwidth=0, bg="#f0f0f0", cursor="hand2",
            )
            slot.grid(row=ci // 5, column=ci % 5, padx=2, pady=1)
            slot.bind("<Button-1>", lambda e, i=ci: self._pick_color(i))
            slot.bind("<Button-3>", lambda e, i=ci: self._clear_color(i))
            self._custom_color_slots.append(slot)
        ttk.Label(color_lf, text="左键选色 · 右键清除",
                  font=(FONT_FAMILY, FONT_SIZE - 2), foreground="#999999"
                  ).grid(row=r + 1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))
        r += 2

        # ──── 符号样式 ────
        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        sym_lf = ttk.LabelFrame(inner, text="符号样式", padding=8)
        sym_lf.pack(fill=tk.X, pady=(0, 8))

        self._marker_var = tk.StringVar()
        ttk.Label(sym_lf, text="类型：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self._marker_combo = ttk.Combobox(
            sym_lf, textvariable=self._marker_var,
            values=MARKER_ICONS, state="readonly",
            width=6, font=(FONT_FAMILY, FONT_SIZE + 2),
        )
        self._marker_combo.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(sym_lf, text="大小：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=0, column=2, sticky="e", padx=(12, 4), pady=4)
        self._marker_size_var = tk.StringVar(value="6")
        ttk.Spinbox(
            sym_lf, textvariable=self._marker_size_var,
            from_=2, to=20, width=6,
            font=(FONT_FAMILY, FONT_SIZE),
        ).grid(row=0, column=3, sticky="w", pady=4)

        # 符号循环开关（在符号区域）
        self._cycle_marker_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            sym_lf, text="每个分组自动切换符号",
            variable=self._cycle_marker_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=1)

        ttk.Label(sym_lf, text="透明度：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self._scatter_alpha_var = tk.DoubleVar(value=1.0)
        ttk.Scale(
            sym_lf, variable=self._scatter_alpha_var,
            from_=0.0, to=1.0,
            orient=tk.HORIZONTAL, length=120,
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(
            sym_lf, textvariable=self._scatter_alpha_var, width=5,
            font=(FONT_FAMILY, FONT_SIZE),
        ).grid(row=2, column=3, sticky="w", pady=4)

        # ──── 拟合曲线样式 ────
        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)
        curve_lf = ttk.LabelFrame(inner, text="拟合曲线样式", padding=8)
        curve_lf.pack(fill=tk.X, pady=(0, 8))

        self._ls_var = tk.StringVar()
        ttk.Label(curve_lf, text="线型：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self._ls_combo = ttk.Combobox(
            curve_lf, textvariable=self._ls_var,
            values=LINESTYLE_ICONS, state="readonly",
            width=10, font=(FONT_FAMILY, FONT_SIZE + 1),
        )
        self._ls_combo.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(curve_lf, text="线宽：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=0, column=2, sticky="e", padx=(12, 4), pady=4)
        self._line_width_var = tk.StringVar(value="2")
        ttk.Spinbox(
            curve_lf, textvariable=self._line_width_var,
            from_=1, to=6, width=6,
            font=(FONT_FAMILY, FONT_SIZE),
        ).grid(row=0, column=3, sticky="w", pady=4)

        # 线型循环开关（在线型区域）
        self._cycle_ls_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            curve_lf, text="每个分组自动切换线型",
            variable=self._cycle_ls_var,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=12, pady=1)

        ttk.Label(curve_lf, text="透明度：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self._curve_alpha_var = tk.DoubleVar(value=1.0)
        ttk.Scale(
            curve_lf, variable=self._curve_alpha_var,
            from_=0.0, to=1.0,
            orient=tk.HORIZONTAL, length=120,
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(
            curve_lf, textvariable=self._curve_alpha_var, width=5,
            font=(FONT_FAMILY, FONT_SIZE),
        ).grid(row=2, column=3, sticky="w", pady=4)

    def _pick_color(self, slot_idx: int):
        """打开颜色选择器"""
        from tkinter import colorchooser
        result = colorchooser.askcolor(
            title="选择颜色",
            parent=self,
            color=self._custom_color_values[slot_idx] or None,
        )
        if result and result[1]:  # (rgb, hex) or (None, None) on cancel
            hex_c = result[1]
            self._custom_color_values[slot_idx] = hex_c
            self._custom_color_slots[slot_idx].configure(bg=hex_c)
            if self._current_idx < len(self.selectors):
                self._write_to_selector(self._current_idx, self._read_current_style())

    def _clear_color(self, slot_idx: int):
        """清除自定义颜色（恢复自动）"""
        self._custom_color_values[slot_idx] = ""
        self._custom_color_slots[slot_idx].configure(bg="#f0f0f0")
        if self._current_idx < len(self.selectors):
            self._write_to_selector(self._current_idx, self._read_current_style())

    def _on_palette_change(self, event=None):
        """调色板切换 → 更新色带预览"""
        self._update_palette_strip()

    @staticmethod
    def _rgba_to_hex(c):
        if hasattr(c, '__iter__'):
            r, g, b = c[0], c[1], c[2]
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        return str(c)

    def _update_palette_strip(self):
        """绘制调色板色带"""
        pal_text = self._palette_var.get()
        pal_key = "tab10"
        for k in COLOR_PALETTE_KEYS:
            if COLOR_PALETTES[k]["name"] == pal_text:
                pal_key = k
                break
        self._selected_palette_key = pal_key
        pal = COLOR_PALETTES[pal_key]
        colors = pal["colors"]
        cw = self._palette_strip.winfo_width()
        if cw < 20:
            cw = 240
        n = len(colors)
        bw = max(14, cw // n)
        self._palette_strip.delete("all")
        for i, c in enumerate(colors):
            hex_c = self._rgba_to_hex(c)
            self._palette_strip.create_rectangle(
                i * bw, 1, i * bw + bw - 1, 15,
                fill=hex_c, outline="#cccccc", width=1,
            )
        self._palette_strip.configure(width=cw)

    def _get_color_names(self):
        """生成颜色名称列表（色块+名称）用于下拉"""
        names = []
        for k in COLOR_PALETTE_KEYS:
            pal = COLOR_PALETTES[k]
            names.append(f"■ {pal['name']}")
        return names

    def _set_palette_combo(self, palette_key: str):
        """设置调色板下拉框"""
        if palette_key in COLOR_PALETTES:
            self._palette_var.set(COLOR_PALETTES[palette_key]["name"])
        # 绑定 <Map> 事件：对话框可见后自动刷新色带宽度
        self._palette_strip.bind("<Map>", self._on_strip_mapped, add="+")

    def _on_strip_mapped(self, event=None):
        """色带首次可见时刷新宽度（只执行一次）"""
        if getattr(self, '_strip_mapped_done', False):
            return
        self._strip_mapped_done = True
        self._update_palette_strip()

    def _build_other_tab(self):
        """杂项标签页"""
        tab = ttk.Frame(self._config_notebook, padding=12)
        self._config_notebook.add(tab, text="其他")

        r = 0
        # Limit
        ttk.Label(tab, text="Limit：",
                  font=(FONT_FAMILY, FONT_SIZE)).grid(row=r, column=0, sticky="e", padx=(0, 8), pady=5)
        self._limit_entry = ttk.Entry(tab, width=10, font=(FONT_FAMILY, FONT_SIZE))
        self._limit_entry.grid(row=r, column=1, sticky="w", pady=5)
        r += 1

        # 提示
        hints = [
            "📐 Limit: 分位数限值，用于统计计算",
            "💡 修改 Limit 后应用会触发完整重绘（含重新拟合）",
            "💡 其他样式变更使用轻量更新，无需重建画布",
        ]
        for h in hints:
            ttk.Label(tab, text=h, font=(FONT_FAMILY, FONT_SIZE - 1),
                      foreground="#888888"
                      ).grid(row=r, column=0, columnspan=3, sticky="w", pady=2)
            r += 1

    # ==================== 底部按钮 ====================

    def _build_bottom_bar(self):
        """底部按钮栏"""
        bb = ttk.Frame(self)
        bb.pack(fill=tk.X, padx=12, pady=(2, 10))

        # 左侧：辅助按钮
        ttk.Button(bb, text="应用到全部",
                   command=self._on_apply_to_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(bb, text="恢复默认",
                   command=self._on_reset_current).pack(side=tk.LEFT, padx=2)

        ttk.Separator(bb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        # 右侧：确定/应用/取消
        ttk.Button(bb, text="确定",
                   command=self._apply_and_close).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bb, text="应用",
                   command=self._apply_changes).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bb, text="取消",
                   command=self._on_cancel).pack(side=tk.RIGHT, padx=3)

    # ==================== 读写样式 ====================

    def _load_current_style(self):
        """从当前 SeriesSelector 加载样式到界面控件（通过 Variable 绑定自动更新）"""
        if self._current_idx >= len(self.selectors):
            return
        sel = self.selectors[self._current_idx]
        cfg = sel.get_style_dict()

        # 颜色与循环
        self._cycle_marker_var.set(cfg.get("cycle_marker", True))
        self._cycle_ls_var.set(cfg.get("cycle_linestyle", True))
        # 自定义颜色 → 填充 slots（pipe 分隔的多色或单色）
        custom_color = cfg.get("custom_color", "")
        self._use_custom_color_var.set(bool(custom_color))
        # 先清空所有 slots
        for i in range(10):
            self._custom_color_values[i] = ""
            self._custom_color_slots[i].configure(bg="#f0f0f0")
        if custom_color:
            colors = custom_color.split("|") if "|" in custom_color else [custom_color]
            for i in range(min(10, len(colors))):
                c = colors[i].strip()
                if c:
                    self._custom_color_values[i] = c
                    self._custom_color_slots[i].configure(bg=c)

        # 符号
        self._marker_var.set(cfg.get("marker_icon", "●"))
        self._marker_size_var.set(str(cfg.get("marker_size", 6)))
        self._scatter_alpha_var.set(cfg.get("scatter_alpha", 1.0))

        # 线
        self._ls_var.set(cfg.get("ls_icon", "────"))
        self._line_width_var.set(str(cfg.get("line_width", 2)))
        self._curve_alpha_var.set(cfg.get("curve_alpha", 1.0))

        # 其他
        self._limit_entry.delete(0, tk.END)
        self._limit_entry.insert(0, str(cfg.get("limit", 0.1)))

        # 刷新色带
        self._update_palette_strip()

    def _resolve_custom_color(self, combo_value: str) -> str:
        """将颜色下拉的值解析为自定义颜色值或空字符串"""
        if not combo_value or combo_value == "(自动调色板)":
            return ""
        # 格式是 "■ Set1 (鲜明)"，找对应的 key
        for k in COLOR_PALETTE_KEYS:
            pal = COLOR_PALETTES[k]
            # 用颜色名中的 key 段匹配
            combo_short = combo_value.replace("■ ", "").strip()
            if pal["name"].strip() == combo_short:
                return k  # 返回调色板 key 作为 custom_color 标记
        return ""

    def _read_current_style(self) -> dict:
        """从界面控件读取当前值（通过 Variable 绑定自动获取）"""
        try:
            old_limit = float(self.selectors[self._current_idx].get_limit())
        except (IndexError, ValueError):
            old_limit = 0.1
        try:
            new_limit = float(self._limit_entry.get())
        except ValueError:
            new_limit = old_limit

        return {
            "marker_icon": self._marker_var.get(),
            "ls_icon": self._ls_var.get(),
            "marker_size": int(self._marker_size_var.get()),
            "line_width": int(self._line_width_var.get()),
            "scatter_alpha": self._scatter_alpha_var.get(),
            "curve_alpha": self._curve_alpha_var.get(),
            "cycle_marker": self._cycle_marker_var.get(),
            "cycle_linestyle": self._cycle_ls_var.get(),
            "custom_color": "|".join(
                [c for c in self._custom_color_values if c]
            ) if self._use_custom_color_var.get() else "",
            "limit": new_limit,
            "_limit_changed": abs(new_limit - old_limit) > 1e-9,
        }

    def _write_to_selector(self, idx: int, cfg: dict):
        """将配置字典写入指定 selector"""
        if idx >= len(self.selectors):
            return
        self.selectors[idx].apply_style_dict(cfg)

    # ==================== 操作按钮 ====================

    def _apply_changes(self):
        """应用当前配置到图表（不关闭对话框）"""
        # 保存当前项
        if self._current_idx < len(self.selectors):
            cfg = self._read_current_style()
            self._write_to_selector(self._current_idx, cfg)
        else:
            cfg = {}

        # 读取调色板设置
        palette_key = self._current_palette
        pal_text = self._palette_var.get()
        for k in COLOR_PALETTE_KEYS:
            if COLOR_PALETTES[k]["name"] == pal_text:
                palette_key = k
                break

        # 统一完整重绘
        if self._on_apply:
            self._on_apply(full_redraw=True, palette=palette_key)

        # 更新左侧按钮文本
        self._update_button_text()

    def _apply_and_close(self):
        """确定：应用 + 关闭"""
        self._apply_changes()
        self.destroy()

    def _on_cancel(self):
        """取消：关闭对话框，不应用任何修改"""
        self.destroy()

    def _on_apply_to_all(self):
        """应用到全部数据项"""
        if not self.selectors or self._current_idx >= len(self.selectors):
            return
        cfg = self._read_current_style()
        for i in range(len(self.selectors)):
            self._write_to_selector(i, cfg)
        # 读取调色板
        pal_text = self._palette_var.get()
        palette_key = self._current_palette
        for k in COLOR_PALETTE_KEYS:
            if COLOR_PALETTES[k]["name"] == pal_text:
                palette_key = k
                break
        if self._on_apply:
            self._on_apply(full_redraw=True, palette=palette_key)
        self._update_button_text()

    def _on_reset_current(self):
        """恢复当前项为默认"""
        if self._current_idx >= len(self.selectors):
            return
        default = {
            "marker_icon": MARKER_ICONS[0],
            "ls_icon": LINESTYLE_ICONS[0],
            "limit": 0.1,
            "scatter_alpha": 1.0,
            "curve_alpha": 1.0,
            "marker_size": 6,
            "line_width": 2,
            "cycle_marker": True,
            "cycle_linestyle": True,
            "custom_color": "",
        }
        self._write_to_selector(self._current_idx, default)
        self._load_current_style()
        self._update_palette_strip()
