"""
可复用 UI 组件
"""
import tkinter as tk
from tkinter import ttk

try:
    from .config import FONT_FAMILY, FONT_SIZE
except ImportError:
    from config import FONT_FAMILY, FONT_SIZE

# ---- marker 图标 → matplotlib 值映射 ----
_MARKER_MAP = [
    ('●',   'o'),
    ('■',   's'),
    ('▲',   '^'),
    ('◆',   'D'),
    ('▼',   'v'),
    ('⬟',   'p'),
    ('★',   '*'),
    ('✖',   'X'),
    ('⬢',   'h'),
    ('⬣',   'H'),
    ('⬥',   'd'),
    ('✶',   'P'),
    ('◁',   '<'),
    ('▷',   '>'),
]
MARKER_ICONS = [icon for icon, _ in _MARKER_MAP]
_MARKER_VALUES = [val for _, val in _MARKER_MAP]

# ---- linestyle 图标 → matplotlib 值映射 ----
_LINESTYLE_MAP = [
    ('────', '-'),
    ('─ ─', '--'),
    ('····', ':'),
    ('─·─·', '-.'),
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

        # 单行：测试项选择下拉 + 移除 + 手动去除 + 自动去除 + 恢复
        ttk.Label(self, text=f"测试项 {idx + 1}：",
                  font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT, padx=2)
        self.combo = ttk.Combobox(self, values=columns,
                                  textvariable=self.var, state='readonly', width=14)
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

        # ---- 分隔 ----
        ttk.Separator(self, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        # marker 选择（图标不加标签）
        self.marker_var = tk.StringVar(value=MARKER_ICONS[0])
        self.marker_combo = ttk.Combobox(self, textvariable=self.marker_var,
                                         values=MARKER_ICONS, state='readonly',
                                         width=4, font=(FONT_FAMILY, FONT_SIZE + 2))
        self.marker_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.marker_combo.bind('<<ComboboxSelected>>', self._on_style_change)

        # linestyle 选择（图标不加标签）
        self.ls_var = tk.StringVar(value=LINESTYLE_ICONS[0])
        self.ls_combo = ttk.Combobox(self, textvariable=self.ls_var,
                                     values=LINESTYLE_ICONS, state='readonly',
                                     width=8, font=(FONT_FAMILY, FONT_SIZE + 1))
        self.ls_combo.pack(side=tk.LEFT)
        self.ls_combo.bind('<<ComboboxSelected>>', self._on_style_change)

    def _on_remove(self):
        if self.remove_callback:
            self.remove_callback(self)

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
        """获取 marker 值，auto 返回 None 表示由代码自动选择"""
        icon = self.marker_var.get()
        try:
            idx = MARKER_ICONS.index(icon)
            return _MARKER_VALUES[idx]
        except ValueError:
            return None

    def get_linestyle(self):
        """获取 linestyle 值，auto 返回 None 表示由代码自动选择"""
        icon = self.ls_var.get()
        try:
            idx = LINESTYLE_ICONS.index(icon)
            return _LINESTYLE_VALUES[idx]
        except ValueError:
            return None
