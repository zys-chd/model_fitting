"""
数据工作簿 — 类 Excel 数据预览

功能：
- 表格展示当前 DataFrame（支持横向/纵向滚动）
- 点击列标题排序（升序/降序/还原）
- 搜索过滤行
- 显示列统计信息（非空数、最小值、最大值等）
"""
import tkinter as tk
from tkinter import ttk
import numpy as np

try:
    from ...config import FONT_FAMILY, FONT_SIZE
except ImportError:
    from config import FONT_FAMILY, FONT_SIZE


class DataWorkbook(tk.Toplevel):
    """数据工作簿对话框"""

    def __init__(self, parent, dataframe, group_column=None, title="数据工作簿"):
        """
        Parameters
        ----------
        parent : tk.Widget
            父窗口
        dataframe : pd.DataFrame
            要展示的数据
        group_column : str or None
            分组列名（用于特殊标记）
        title : str
            窗口标题
        """
        super().__init__(parent)
        self.title(title)
        self.geometry("900x500")
        self.minsize(600, 300)
        self.transient(parent)
        self.grab_set()

        self._df = dataframe.copy() if dataframe is not None else None
        self._group_column = group_column
        self._sort_col = None
        self._sort_reverse = False
        self._filter_text = tk.StringVar()
        self._filter_text.trace_add("write", lambda *a: self._apply_filter())

        if self._df is None or self._df.empty:
            ttk.Label(self, text="无数据", font=(FONT_FAMILY, FONT_SIZE + 4)).pack(expand=True)
            return

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        # ---- 顶部：信息栏 + 搜索 ----
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))

        rows, cols = self._df.shape
        ttk.Label(top, text=f"共 {rows} 行 × {cols} 列",
                  font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="搜索：", font=(FONT_FAMILY, FONT_SIZE)).pack(
            side=tk.LEFT, padx=(20, 4))
        ttk.Entry(top, textvariable=self._filter_text, width=25,
                  font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT)

        # 统计信息
        stat_text = self._calc_stats()
        self._stat_label = ttk.Label(
            top, text=stat_text, font=(FONT_FAMILY, FONT_SIZE - 1),
            foreground="#666666",
        )
        self._stat_label.pack(side=tk.RIGHT, padx=4)

        # ---- 表格 ----
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 列名
        columns = list(self._df.columns)
        # 显示列 #0 为行号
        self._tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="tree headings",
            height=20,
        )
        self._tree.heading("#0", text="#", anchor="center")
        self._tree.column("#0", width=50, anchor="center", stretch=False)

        for col in columns:
            self._tree.heading(col, text=col, anchor="w",
                               command=lambda c=col: self._on_sort(c))
            # 自适应列宽
            max_w = max(
                len(str(col)) * 9,
                self._df[col].astype(str).str.len().max() * 8 if len(self._df) > 0 else 60,
                60,
            )
            self._tree.column(col, width=min(max_w + 10, 200), anchor="w")

        # 滚动条
        v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 双击复制单元格
        self._tree.bind("<Double-Button-1>", self._on_cell_double_click)

        # 填充数据
        self._populate_data()

        # ---- 底部按钮 ----
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=(2, 8))

        ttk.Label(btn_frame, text="双击单元格复制值",
                  font=(FONT_FAMILY, FONT_SIZE - 1), foreground="#999999"
                  ).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="刷新", width=8,
                   command=self._refresh).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="关闭", width=8,
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)

        self.bind("<Escape>", lambda e: self.destroy())

    def _populate_data(self, data=None):
        """填充数据到 Treeview"""
        # 清空
        for item in self._tree.get_children():
            self._tree.delete(item)

        df = data if data is not None else self._df
        if df is None or df.empty:
            return

        # 搜索过滤
        ft = self._filter_text.get().strip().lower()
        if ft:
            mask = df.astype(str).apply(
                lambda row: row.str.lower().str.contains(ft, na=False).any(), axis=1)
            df = df[mask]

        # 排序
        if self._sort_col and self._sort_col in df.columns:
            try:
                df = df.sort_values(by=self._sort_col, ascending=not self._sort_reverse)
            except Exception:
                pass

        # 插入行
        for idx, (_, row) in enumerate(df.iterrows()):
            vals = []
            for col in df.columns:
                v = row[col]
                if isinstance(v, float):
                    vals.append(f"{v:.6g}")
                else:
                    vals.append(str(v))
            tags = ()
            self._tree.insert("", tk.END, text=str(idx + 1), values=vals, tags=tags)

        # 更新统计
        self._update_stat(df)

    def _on_sort(self, col: str):
        """点击列标题排序"""
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._populate_data()

        # 更新列标题箭头
        for c in self._tree["columns"]:
            txt = c
            if c == self._sort_col:
                txt = f"{c} {'▼' if self._sort_reverse else '▲'}"
            self._tree.heading(c, text=txt)

    def _apply_filter(self):
        """搜索过滤"""
        self._populate_data()

    def _on_cell_double_click(self, event):
        """双击复制单元格值到剪贴板"""
        item = self._tree.identify_row(event.y)
        col = self._tree.identify_column(event.x)
        if not item or not col:
            return
        col_idx = int(col.replace("#", "")) - 1  # #0 是行号列
        vals = self._tree.item(item, "values")
        if 0 <= col_idx < len(vals):
            val = vals[col_idx]
            self.clipboard_clear()
            self.clipboard_append(val)
            # 临时状态提示（通过修改标题）
            old_title = self.title()
            self.title(f"✅ 已复制: {val}")
            self.after(1200, lambda: self.title(old_title))

    def _calc_stats(self) -> str:
        """计算统计摘要"""
        if self._df is None or self._df.empty:
            return ""
        numeric_cols = self._df.select_dtypes(include=[np.number]).columns
        parts = []
        for col in numeric_cols[:3]:  # 只显示前3列
            s = self._df[col]
            parts.append(f"{col}: min={s.min():.4g}, max={s.max():.4g}")
        return "  |  ".join(parts)

    def _update_stat(self, df):
        """更新状态栏统计"""
        if df is None or df.empty:
            self._stat_label.configure(text="0 行")
            return
        rows = len(df)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            col = numeric_cols[0]
            s = df[col]
            self._stat_label.configure(
                text=f"{rows} 行 | {col}: {s.min():.4g} ~ {s.max():.4g}")
        else:
            self._stat_label.configure(text=f"{rows} 行")

    def _refresh(self):
        """刷新数据（从外部重新获取已不现实，直接用当前缓存）"""
        self._populate_data()
