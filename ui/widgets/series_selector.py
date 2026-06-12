"""
SeriesSelector — 数值列选择组件（带 marker/linestyle/limit 控制）

从旧 widgets.py 迁移而来，接口保持不变。
"""
import tkinter as tk
from tkinter import ttk

try:
    from config import FONT_FAMILY, FONT_SIZE
except ImportError:
    from ...config import FONT_FAMILY, FONT_SIZE

# ---- marker 图标 → matplotlib 值映射 ----
_MARKER_MAP = [
    ('●', 'o'), ('■', 's'), ('▲', '^'), ('◆', 'D'), ('▼', 'v'),
    ('⬟', 'p'), ('★', '*'), ('✖', 'X'), ('⬢', 'h'), ('⬣', 'H'),
    ('⬥', 'd'), ('✶', 'P'), ('◁', '<'), ('▷', '>'),
]
MARKER_ICONS = [icon for icon, _ in _MARKER_MAP]
_MARKER_VALUES = [val for _, val in _MARKER_MAP]

# ---- linestyle 图标 → matplotlib 值映射 ----
_LINESTYLE_MAP = [
    ('────', '-'), ('─ ─', '--'), ('····', ':'), ('─·─·', '-.'),
]
LINESTYLE_ICONS = [icon for icon, _ in _LINESTYLE_MAP]
_LINESTYLE_VALUES = [val for _, val in _LINESTYLE_MAP]


class SeriesSelector(ttk.Frame):
    """数值列选择组件 — 含列选择、手动去除离群点、自动去除、恢复按钮"""

    def __init__(self, master, columns, idx,
                 remove_callback=None,
                 manual_remove_callback=None,
                 auto_remove_callback=None,
                 restore_callback=None,
                 selection_change_callback=None,
                 style_change_callback=None,
                 *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.idx = idx
        self.columns = columns
        self.remove_callback = remove_callback
        self.manual_remove_callback = manual_remove_callback
        self.auto_remove_callback = auto_remove_callback
        self.restore_callback = restore_callback
        self.selection_change_callback = selection_change_callback
        self.style_change_callback = style_change_callback
        self.var = tk.StringVar()

        ttk.Label(self, text=f"测试项 {idx + 1}：",
                  font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT, padx=2)

        combo_width = max(14, self._calc_combo_width(columns)) if columns else 14
        self.combo = ttk.Combobox(self, values=columns,
                                  textvariable=self.var, state='readonly', width=combo_width)
        if columns:
            self.combo.current(0)
        self.combo.pack(side=tk.LEFT)
        self.combo.bind('<<ComboboxSelected>>', self._on_selection_change)

        ttk.Button(self, text="移除", width=4,
                   command=self._on_remove).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="手动去除", width=7,
                   command=self._on_manual_remove).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="自动去除", width=7,
                   command=self._on_auto_remove).pack(side=tk.LEFT, padx=2)
        ttk.Button(self, text="恢复", width=5,
                   command=self._on_restore).pack(side=tk.LEFT, padx=2)

        ttk.Label(self, text=" limit:", font=(FONT_FAMILY, FONT_SIZE - 1)).pack(side=tk.LEFT, padx=(4, 0))
        self.limit_var = tk.StringVar(value="0.1")
        ttk.Entry(self, textvariable=self.limit_var, width=5,
                  font=(FONT_FAMILY, FONT_SIZE - 1)).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        self.marker_var = tk.StringVar(value=MARKER_ICONS[0])
        self.marker_combo = ttk.Combobox(self, textvariable=self.marker_var,
                                         values=MARKER_ICONS, state='readonly',
                                         width=4, font=(FONT_FAMILY, FONT_SIZE + 2))
        self.marker_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.marker_combo.bind('<<ComboboxSelected>>', self._on_style_change)

        self.ls_var = tk.StringVar(value=LINESTYLE_ICONS[0])
        self.ls_combo = ttk.Combobox(self, textvariable=self.ls_var,
                                     values=LINESTYLE_ICONS, state='readonly',
                                     width=8, font=(FONT_FAMILY, FONT_SIZE + 1))
        self.ls_combo.pack(side=tk.LEFT)
        self.ls_combo.bind('<<ComboboxSelected>>', self._on_style_change)

    def _on_remove(self):
        if self.remove_callback:
            self.remove_callback(self)

    @staticmethod
    def _calc_combo_width(columns):
        if not columns:
            return 14
        max_w = 0
        for col in columns:
            w = sum(2 if ord(c) > 127 else 1 for c in str(col))
            max_w = max(max_w, w)
        return max_w + 2

    def update_columns(self, columns):
        self.columns = list(columns)
        self.combo["values"] = self.columns
        self.combo["width"] = self._calc_combo_width(self.columns)
        if self.columns and self.var.get() not in self.columns:
            self.var.set(self.columns[0])

    def _on_selection_change(self, event=None):
        if self.selection_change_callback:
            self.selection_change_callback(self)

    def _on_style_change(self, event=None):
        if self.style_change_callback:
            self.style_change_callback(self)

    def _on_manual_remove(self):
        if self.manual_remove_callback:
            self.manual_remove_callback(self)

    def _on_auto_remove(self):
        if self.auto_remove_callback:
            self.auto_remove_callback(self)

    def _on_restore(self):
        if self.restore_callback:
            self.restore_callback(self)

    def get_selection(self):
        return self.var.get()

    def get_limit(self):
        try:
            return float(self.limit_var.get())
        except ValueError:
            return 0.1

    def get_marker(self):
        icon = self.marker_var.get()
        try:
            idx = MARKER_ICONS.index(icon)
            return _MARKER_VALUES[idx]
        except ValueError:
            return None

    def get_linestyle(self):
        icon = self.ls_var.get()
        try:
            idx = LINESTYLE_ICONS.index(icon)
            return _LINESTYLE_VALUES[idx]
        except ValueError:
            return None
