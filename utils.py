"""
工具函数：数据列检测、测试数据生成
"""

import os
import numpy as np
import pandas as pd

try:
    from .config import GROUP_CANDIDATES, ID_CANDIDATES, COLUMN_SUFFIX_CANDIDATES
except ImportError:
    from config import GROUP_CANDIDATES, ID_CANDIDATES, COLUMN_SUFFIX_CANDIDATES


def detect_columns(df: pd.DataFrame) -> dict:
    """
    检测 DataFrame 中的分组列和数值列。
    返回 {
        'columns': [...],
        'group_column': str | None,
        'value_columns': [...],
        'id_columns': [...],
    }
    """
    columns = list(df.columns)

    # 检测分组列
    group_column = None
    for gc in GROUP_CANDIDATES:
        if gc in columns:
            group_column = gc
            break

    # 检测 ID 列
    id_columns = [c for c in columns if c in ID_CANDIDATES]

    # 数值列 = 排除 ID 列和分组列
    exclude = set(id_columns)
    if group_column:
        exclude.add(group_column)
    value_columns = [c for c in columns if c not in exclude]

    return {
        "columns": columns,
        "group_column": group_column,
        "value_columns": value_columns,
        "id_columns": id_columns,
    }


def filter_columns_keep_shift_only(df_columns: list) -> list:
    """
    仅保留以 _shift 结尾的列，去掉所有其他列。

    例如：['IDSS1_T0', 'IDSS1_After', 'IDSS1_shift', 'VTH1']
       → ['IDSS1_shift']
    """
    columns = list(df_columns)
    return [c for c in columns if c.endswith("_shift")]


def generate_test_data(path: str = None) -> pd.DataFrame:
    """
    生成合成测试数据（Weibull 分布）。
    返回 DataFrame，如果指定 path 则同时保存为 CSV。
    """
    rng = np.random.default_rng(12345)
    rows = 200
    groups = ["GroupA", "GroupB", "GroupC", "GroupD", "GroupE"]

    data = {
        "PART_ID": [f"P{i:03d}" for i in range(rows)],
        "group": [groups[i % len(groups)] for i in range(rows)],
    }

    for col_idx, col_name in enumerate(
        [
            "IDSS1_T0",
            "IDSS1_After",
            "IDSS1_shift",
            "IDSS2_T0",
            "IDSS2_After",
            "IDSS2_shift",
            "IGSS1_T0",
            "IGSS2_After",
            "IGSS2_shift",
            "VTH1_T0",
            "VTH2",
            "RDSON1",
            "RDSON2",
            "BVDSS1",
            "BVDSS2",
        ]
    ):
        k = 0.8 + 0.3 * col_idx
        lam = 50 + 10 * col_idx
        samples = rng.weibull(k, size=rows) * lam
        # # 根据数值将原数据限制在 0.5-100 范围内
        # samples = np.clip(samples, 0.5, 100)
        # 注入少量异常值
        samples[rng.choice(rows, size=5, replace=False)] *= rng.uniform(
            1.5, 3.0, size=5
        )
        data[col_name] = samples

    df = pd.DataFrame(data)

    if path is not None:
        df.to_csv(path, index=False)

    return df


def default_test_path() -> str:
    """返回默认测试数据 CSV 路径"""
    return os.path.join(os.path.dirname(__file__), "test_weibull.csv")
