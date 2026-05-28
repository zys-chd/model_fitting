"""
SessionService — 会话保存/加载（.rda 格式，gzip 压缩）

文件格式: gzip 压缩的 JSON，包含 DataFrame + 完整会话状态。
"""
import json
import gzip
import os
import logging
from io import StringIO
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SESSION_VERSION = "1.0"


class SessionService:
    """会话持久化服务"""

    @staticmethod
    def save(path: str, original_df: pd.DataFrame, state: dict,
             removed_points: dict | None = None) -> None:
        """
        保存会话到 .rda 文件。

        Parameters
        ----------
        path : str
            输出路径
        original_df : pd.DataFrame
            原始数据（不含去除）
        state : dict
            配置状态
        removed_points : dict, optional
            {col: [df_index, ...]} 去除点映射
        """
        removed = removed_points or {}
        # 确保 index values 可 JSON 序列化
        cleaned_removed = {}
        for col, indices in removed.items():
            cleaned_removed[col] = [int(i) if isinstance(i, (int, float, np.integer)) else i for i in indices]

        session = {
            "version": SESSION_VERSION,
            "dataframe": original_df.to_json(orient="split", date_format="iso"),
            "removed_points": cleaned_removed,
            "state": state,
        }

        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
        logger.info("会话已保存: %s (%d 列, %d 行)", path,
                     len(original_df.columns), len(original_df))

    @staticmethod
    def load(path: str) -> dict:
        """
        加载 .rda 会话文件。

        Returns
        -------
        dict
            {"dataframe": pd.DataFrame, "state": {...}, "removed_points": {...}}
        """
        with gzip.open(path, "rt", encoding="utf-8") as f:
            session = json.load(f)

        version = session.get("version", "1.0")
        logger.info("加载会话: %s (版本 %s)", path, version)

        # 恢复 DataFrame（不含去除点标记，由 Presenter 负责应用）
        df = pd.read_json(StringIO(session["dataframe"]), orient="split")

        return {
            "dataframe": df,
            "state": session.get("state", {}),
            "removed_points": session.get("removed_points", {}),
        }
