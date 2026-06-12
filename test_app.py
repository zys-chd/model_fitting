"""
测试文件：演示 App 的多种启动方式
- 作为子窗口嵌入
- 通过 launch() 传入 DataFrame
- 通过 launch() 传入 CSV 路径
"""
import tkinter as tk
from tkinter import ttk
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_fitting_app import Model_Fitting_App, launch


class TestHost(tk.Tk):
    """测试宿主窗口 — 演示 App 作为子窗口的用法"""

    def __init__(self):
        super().__init__()
        self.title("分布拟合工具 — 测试启动器")
        self.geometry("520x400")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._child_windows: list[Model_Fitting_App] = []
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self, padding=20)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="分布拟合工具 — 测试启动器",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))

        ttk.Label(f, text="嵌入模式（App 作为子窗口）：",
                  font=("Microsoft YaHei", 10)).pack(pady=(0, 5))

        btn = ttk.Frame(f)
        btn.pack()
        ttk.Button(btn, text="空窗口", command=self._open_as_child, width=20).pack(pady=3)
        ttk.Button(btn, text="加载 CSV", command=self._open_with_csv, width=20).pack(pady=3)
        ttk.Button(btn, text="传入 DataFrame", command=self._open_with_df, width=20).pack(pady=3)

        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(f, text="独立模式（launch 函数，自带事件循环）：",
                  font=("Microsoft YaHei", 10)).pack(pady=(0, 5))

        btn2 = ttk.Frame(f)
        btn2.pack()
        ttk.Button(btn2, text="launch(csv_path=...)", command=self._launch_csv, width=20).pack(pady=3)
        ttk.Button(btn2, text="launch(dataframe=...)", command=self._launch_df, width=20).pack(pady=3)

        ttk.Separator(f, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(f, text="打开的子窗口数: 0",
                  font=("Microsoft YaHei", 9), name="counter").pack()

    def _open_as_child(self):
        app = Model_Fitting_App(parent=self)
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        self._update_counter()

    def _open_with_csv(self):
        csv_path = os.path.join(os.path.dirname(__file__), "test_weibull.csv")
        if not os.path.exists(csv_path):
            from tkinter import messagebox
            messagebox.showwarning("缺少文件", f"找不到 {csv_path}")
            return
        app = Model_Fitting_App(parent=self)
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        app.after(150, lambda: app.load_csv(csv_path))
        self._update_counter()

    def _open_with_df(self):
        """直接传入 DataFrame 作为子窗口"""
        csv_path = os.path.join(os.path.dirname(__file__), "test_weibull.csv")
        if not os.path.exists(csv_path):
            from tkinter import messagebox
            messagebox.showwarning("缺少文件", f"找不到 {csv_path}")
            return
        df = pd.read_csv(csv_path)
        app = Model_Fitting_App(parent=self, dataframe=df)
        self._child_windows.append(app)
        app.protocol("WM_DELETE_WINDOW", lambda a=app: self._remove_child(a))
        self._update_counter()

    def _launch_csv(self):
        """通过 launch() 独立启动，传入 CSV 路径（阻塞直到窗口关闭）"""
        csv_path = os.path.join(os.path.dirname(__file__), "test_weibull.csv")
        launch(csv_path=csv_path)

    def _launch_df(self):
        """通过 launch() 独立启动，传入 DataFrame（阻塞直到窗口关闭）"""
        csv_path = os.path.join(os.path.dirname(__file__), "test_weibull.csv")
        df = pd.read_csv(csv_path)
        launch(dataframe=df)

    def _remove_child(self, app: Model_Fitting_App):
        if app in self._child_windows:
            self._child_windows.remove(app)
        app._on_close()
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
