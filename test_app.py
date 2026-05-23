"""
测试文件：在自定义 tkinter 窗口中调用 App 组件
演示 App 作为子窗口嵌入、以及在新窗口中打开 CSV
"""
import tkinter as tk
from tkinter import ttk
import sys
import os

# 确保能导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import App


class TestHost(tk.Tk):
    """测试宿主窗口"""

    def __init__(self):
        super().__init__()
        self.title("测试 — 分布拟合工具宿主")
        self.geometry("500x300")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._child_windows: list[App] = []

    def _build_ui(self):
        f = ttk.Frame(self, padding=20)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="分布拟合工具 — 测试启动器",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))

        ttk.Label(f, text="选择一种方式启动 App：",
                  font=("Microsoft YaHei", 10)).pack(pady=(0, 15))

        btn_frame = ttk.Frame(f)
        btn_frame.pack()

        ttk.Button(btn_frame, text="在当前窗口中作为子窗口打开",
                   command=self._open_as_child, width=36).pack(pady=5)
        ttk.Button(btn_frame, text="加载 test_weibull.csv 作为子窗口",
                   command=self._open_with_csv, width=36).pack(pady=5)
        ttk.Button(btn_frame, text="作为独立窗口打开（新 Tk 根）",
                   command=self._open_standalone, width=36).pack(pady=5)

        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        ttk.Label(f, text="打开的子窗口数: 0",
                  font=("Microsoft YaHei", 9), name="counter").pack()

    def _open_as_child(self):
        """作为当前 Tk 的子窗口"""
        app = App(parent=self)
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        self._update_counter()

    def _open_with_csv(self):
        """加载测试 CSV 作为子窗口"""
        csv_path = os.path.join(os.path.dirname(__file__), "test_weibull.csv")
        if not os.path.exists(csv_path):
            from tkinter import messagebox
            messagebox.showwarning("缺少文件", f"找不到 {csv_path}，请先生成测试数据。")
            return
        import pandas as pd
        app = App(parent=self)
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        app.after(150, lambda: app.load_csv(csv_path))
        self._update_counter()

    def _open_standalone(self):
        """独立窗口（自带 Tk 根）"""
        app = App()  # parent=None → standalone
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        self._update_counter()

    def _remove_child(self, app: App):
        if app in self._child_windows:
            self._child_windows.remove(app)
        app._on_close()  # 先执行 App 的清理逻辑（关闭 matplotlib 等）
        try:
            app.destroy()
        except Exception:
            pass
        self._update_counter()

    def _update_counter(self):
        for child in self.children.values():
            if isinstance(child, ttk.Label) and "counter" in str(child):
                child.config(text=f"打开的子窗口数: {len(self._child_windows)}")

    def _on_close(self):
        for app in list(self._child_windows):
            try:
                app.destroy()
            except Exception:
                pass
        self._child_windows.clear()
        self.destroy()


if __name__ == "__main__":
    host = TestHost()
    host.mainloop()
