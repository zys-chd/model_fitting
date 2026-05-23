"""
可复用 UI 组件
"""
import tkinter as tk
from tkinter import ttk

try:
    from .config import FONT_FAMILY, FONT_SIZE
except ImportError:
    from config import FONT_FAMILY, FONT_SIZE


class SeriesSelector(ttk.Frame):
    """数值列选择组件 — 含列选择、手动去除离群点、自动去除、恢复按钮"""

    def __init__(self, master, columns, idx,
                 remove_callback=None,
                 manual_remove_callback=None,
                 auto_remove_callback=None,
                 restore_callback=None,
                 selection_change_callback=None,
                 *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.idx = idx
        self.columns = columns
        self.remove_callback = remove_callback
        self.manual_remove_callback = manual_remove_callback
        self.auto_remove_callback = auto_remove_callback
        self.restore_callback = restore_callback
        self.selection_change_callback = selection_change_callback
        self.var = tk.StringVar()

        # 单行：列选择下拉 + 移除 + 手动去除 + 自动去除 + 恢复
        ttk.Label(self, text=f"列 {idx + 1}：",
                  font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT, padx=2)
        self.combo = ttk.Combobox(self, values=columns,
                                  textvariable=self.var, state='readonly', width=14)
        if columns:
            self.combo.current(0)
        self.combo.pack(side=tk.LEFT)
        self.combo.bind('<<ComboboxSelected>>', self._on_selection_change)

        ttk.Button(self, text="移除", width=4,
                   command=self._on_remove).pack(side=tk.LEFT, padx=1)
        ttk.Button(self, text="手动去除", width=7,
                   command=self._on_manual_remove).pack(side=tk.LEFT, padx=1)
        ttk.Button(self, text="自动去除", width=7,
                   command=self._on_auto_remove).pack(side=tk.LEFT, padx=1)
        ttk.Button(self, text="恢复", width=5,
                   command=self._on_restore).pack(side=tk.LEFT, padx=1)

    def _on_remove(self):
        if self.remove_callback:
            self.remove_callback(self)

    def _on_selection_change(self, event=None):
        if self.selection_change_callback:
            self.selection_change_callback(self)

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
