"""
ImportDialog — 自定义数据读取对话框

允许用户：
- 跳过指定行数
- 选择表头行（-1 = 无表头）
- 选择分组列（可无）
- 实时预览：原始数据 Tab + 解析预览 Tab
"""
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np

try:
    from config import FONT_FAMILY, FONT_SIZE
except ImportError:
    from ...config import FONT_FAMILY, FONT_SIZE


class ImportDialog(tk.Toplevel):
    """自定义数据导入对话框 — 纯 UI 组件，不依赖 Presenter"""

    def __init__(self, parent, raw_df: pd.DataFrame, file_path: str):
        super().__init__(parent)
        self.title("自定义数据读取")
        self.geometry("950x680")
        if parent:
            self.transient(parent)
        self.grab_set()
        self.resizable(True, True)

        self._raw_df = raw_df
        self._file_path = file_path
        self.result_df: pd.DataFrame | None = None

        # 控件变量
        self._skip_first_var = tk.IntVar(value=0)
        self._skip_extra_var = tk.StringVar(value="")  # 额外跳过行号，逗号分隔
        self._header_row_var = tk.IntVar(value=0)  # -1 = 无表头
        self._group_col_var = tk.StringVar(value="(无)")

        self._build_ui()
        self._refresh_preview()

    # ==================== UI 构建 ====================

    def _build_ui(self):
        # 顶部控制栏
        ctrl = ttk.Frame(self, padding=8)
        ctrl.pack(fill=tk.X)

        ttk.Label(ctrl, text=f"文件: {self._file_path}",
                  font=(FONT_FAMILY, 9, "italic")).pack(anchor=tk.W)

        row1 = ttk.Frame(ctrl)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="跳过前N行:", font=(FONT_FAMILY, FONT_SIZE)).pack(side=tk.LEFT)
        ttk.Spinbox(row1, from_=0, to=200, textvariable=self._skip_first_var,
                     width=5, command=self._refresh_preview).pack(side=tk.LEFT, padx=4)
        ttk.Label(row1, text="额外跳过行号:", font=(FONT_FAMILY, FONT_SIZE)).pack(
            side=tk.LEFT, padx=(12, 0))
        skip_entry = ttk.Entry(row1, textvariable=self._skip_extra_var, width=18)
        skip_entry.pack(side=tk.LEFT, padx=4)
        skip_entry.bind("<Return>", lambda e: self._refresh_preview())
        ttk.Label(row1, text="(逗号分隔,支持中英文,)", font=(FONT_FAMILY, 7),
                  foreground="#888").pack(side=tk.LEFT)
        ttk.Button(row1, text="刷新", width=5, command=self._refresh_preview).pack(
            side=tk.LEFT, padx=8)

        row2 = ttk.Frame(ctrl)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="表头行 (-1=无):", font=(FONT_FAMILY, FONT_SIZE)).pack(
            side=tk.LEFT)
        ttk.Spinbox(row2, from_=-1, to=50, textvariable=self._header_row_var,
                     width=5, command=self._refresh_preview).pack(side=tk.LEFT, padx=4)

        ttk.Label(row2, text="分组列:", font=(FONT_FAMILY, FONT_SIZE)).pack(
            side=tk.LEFT, padx=(16, 0))
        self._group_combo = ttk.Combobox(row2, textvariable=self._group_col_var,
                                          state="readonly", width=14)
        self._group_combo.pack(side=tk.LEFT, padx=4)
        self._group_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        self._info_label = ttk.Label(row2, text="", font=(FONT_FAMILY, 8), foreground="#888")
        self._info_label.pack(side=tk.LEFT, padx=(24, 0))

        # Notebook：原始数据 + 解析预览
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Tab 1: 原始数据（Treeview 带行号 + 颜色标记）
        raw_frame = ttk.Frame(nb)
        nb.add(raw_frame, text="原始数据")
        self._raw_tree = ttk.Treeview(raw_frame, show="tree headings",
                                       columns=("row_data",), height=18)
        self._raw_tree.heading("#0", text="行号")
        self._raw_tree.heading("row_data", text="数据")
        self._raw_tree.column("#0", width=60, anchor="e", stretch=False)
        self._raw_tree.column("row_data", width=700, anchor="w")
        raw_sy = ttk.Scrollbar(raw_frame, orient=tk.VERTICAL, command=self._raw_tree.yview)
        raw_sx = ttk.Scrollbar(raw_frame, orient=tk.HORIZONTAL, command=self._raw_tree.xview)
        self._raw_tree.configure(yscrollcommand=raw_sy.set, xscrollcommand=raw_sx.set)
        self._raw_tree.grid(row=0, column=0, sticky="nsew")
        raw_sy.grid(row=0, column=1, sticky="ns")
        raw_sx.grid(row=1, column=0, sticky="ew")
        raw_frame.grid_rowconfigure(0, weight=1)
        raw_frame.grid_columnconfigure(0, weight=1)
        # 配置颜色 tag
        self._raw_tree.tag_configure("skip", background="#e0e0e0", foreground="#999")
        self._raw_tree.tag_configure("header", background="#c8e6c9", foreground="#2e7d32")
        self._raw_tree.tag_configure("extra_skip", background="#ffcdd2", foreground="#c62828")
        # 颜色图例
        legend = ttk.Frame(raw_frame)
        legend.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 0))
        for text, bg, fg in [
            ("灰色=跳过", "#e0e0e0", "#999"),
            ("绿色=表头", "#c8e6c9", "#2e7d32"),
            ("红色=额外跳过", "#ffcdd2", "#c62828"),
        ]:
            lbl = tk.Label(legend, text=f" ● {text} ", font=(FONT_FAMILY, 7),
                           bg=bg, fg=fg, relief=tk.GROOVE, padx=3)
            lbl.pack(side=tk.LEFT, padx=2)

        # Tab 2: 解析预览（Treeview 表格）
        prev_frame = ttk.Frame(nb)
        nb.add(prev_frame, text="解析预览")
        self._preview_tree = ttk.Treeview(prev_frame, show="headings", height=18)
        prev_sy = ttk.Scrollbar(prev_frame, orient=tk.VERTICAL,
                                 command=self._preview_tree.yview)
        prev_sx = ttk.Scrollbar(prev_frame, orient=tk.HORIZONTAL,
                                 command=self._preview_tree.xview)
        self._preview_tree.configure(yscrollcommand=prev_sy.set, xscrollcommand=prev_sx.set)
        self._preview_tree.grid(row=0, column=0, sticky="nsew")
        prev_sy.grid(row=0, column=1, sticky="ns")
        prev_sx.grid(row=1, column=0, sticky="ew")
        prev_frame.grid_rowconfigure(0, weight=1)
        prev_frame.grid_columnconfigure(0, weight=1)

        # 底部按钮
        btn = ttk.Frame(self, padding=8)
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="确认导入", command=self._on_confirm).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Label(btn, text="提示: 调整参数后预览自动刷新",
                  font=(FONT_FAMILY, 8), foreground="#888").pack(side=tk.LEFT)

    # ==================== 预览刷新 ====================

    def _refresh_preview(self):
        """根据当前参数解析并刷新两个预览区"""
        skip = self._skip_first_var.get()
        header_row = self._header_row_var.get()
        n_total = len(self._raw_df)

        # 1. 原始数据 Treeview 预览（带真实行号 + 颜色标记）
        self._refresh_raw_tree(skip, header_row)

        # 2. 解析 DataFrame
        try:
            if header_row < 0:
                df = self._raw_df.iloc[skip:].reset_index(drop=True)
                df.columns = [f"Col{i}" for i in range(len(df.columns))]
            else:
                skip_actual = skip + header_row
                if skip_actual >= n_total:
                    self._update_parsed_tree([])
                    self._info_label.config(text=f"表头行 {header_row} 超出范围")
                    return
                header_vals = self._raw_df.iloc[skip_actual].tolist()
                data_start = skip_actual + 1
                df = self._raw_df.iloc[data_start:].reset_index(drop=True)
                col_names = []
                for i in range(len(df.columns)):
                    if i < len(header_vals) and pd.notna(header_vals[i]):
                        col_names.append(str(header_vals[i]))
                    else:
                        col_names.append(f"Col{i}")
                df.columns = col_names
        except Exception as e:
            self._info_label.config(text=f"解析失败: {e}")
            self._update_parsed_tree([])
            return

        # 3. 跳过额外指定行号
        extra_indices = self._parse_extra_indices()
        if extra_indices:
            valid = [i for i in extra_indices if 0 <= i < len(df)]
            if valid:
                df = df.drop(index=valid).reset_index(drop=True)

        self._parsed_df = df
        self._update_parsed_tree(df)

        # 更新分组列下拉
        options = ["(无)"] + list(df.columns)
        self._group_combo["values"] = options
        if self._group_col_var.get() not in options:
            self._group_col_var.set("(无)")

        self._info_label.config(
            text=f"解析: {len(df)} 行 × {len(df.columns)} 列  (原始 {n_total} 行)")

    def _refresh_raw_tree(self, skip: int, header_row: int):
        """刷新原始数据 Treeview：真实行号 + 颜色区分跳过/表头/数据"""
        tree = self._raw_tree
        for item in tree.get_children():
            tree.delete(item)

        # 额外跳过行号 → 原始文件行号映射
        extra_parsed = set(self._parse_extra_indices())
        if header_row >= 0:
            data_start_raw = skip + header_row + 1
        else:
            data_start_raw = skip
        extra_raw_set = {data_start_raw + j for j in extra_parsed}

        show_rows = min(100, len(self._raw_df))

        for i in range(show_rows):
            line_no = i + 1
            row_vals = self._raw_df.iloc[i].tolist()
            row_str = "\t".join(
                f"{v:.6g}" if isinstance(v, float) and not (np.isnan(v) if isinstance(v, float) else False)
                else str(v) if pd.notna(v) else ""
                for v in row_vals
            )

            # 确定 tag：按优先级
            if i < skip:
                tag = "skip"
            elif header_row >= 0 and i < skip + header_row:
                tag = "skip"
            elif header_row >= 0 and i == skip + header_row:
                tag = "header"
            elif i in extra_raw_set:
                tag = "extra_skip"
            else:
                tag = ""

            tree.insert("", tk.END, text=str(line_no), values=(row_str,),
                        tags=(tag,) if tag else ())

    def _update_parsed_tree(self, df: pd.DataFrame):
        """更新解析预览 Treeview"""
        tree = self._preview_tree
        # 清空列定义
        tree["columns"] = []
        for item in tree.get_children():
            tree.delete(item)

        if df is None or df.empty:
            return

        cols = list(df.columns)
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=str(c))
            tree.column(c, width=max(80, min(150, len(str(c)) * 9)), anchor="w")

        # 只显示前 200 行
        preview = df.head(200)
        for _, row in preview.iterrows():
            values = []
            for c in cols:
                v = row[c]
                if isinstance(v, float):
                    values.append(f"{v:.6g}" if not np.isnan(v) else "")
                else:
                    values.append(str(v) if pd.notna(v) else "")
            tree.insert("", tk.END, values=values)

    # ==================== 确认 ====================

    def _on_confirm(self):
        """确认导入，将解析后的 DataFrame 放入 result_df"""
        if not hasattr(self, '_parsed_df') or self._parsed_df is None:
            self.destroy()
            return

        df = self._parsed_df.copy()

        # 分组列透传
        group_col = self._group_col_var.get()
        if group_col and group_col != "(无)" and group_col in df.columns:
            self._result_group_col = group_col
        else:
            self._result_group_col = None

        self.result_df = df
        self.destroy()

    def _parse_extra_indices(self) -> list[int]:
        """解析额外跳过行号字符串 → 行号列表（支持中英文逗号，从大到小排序以便 df.drop 安全）"""
        raw = self._skip_extra_var.get().strip()
        if not raw:
            return []
        # 全角逗号 → 半角
        raw = raw.replace("\uff0c", ",")
        indices = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                indices.append(int(part))
            except ValueError:
                continue
        return sorted(set(indices), reverse=True)
