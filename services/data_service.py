"""
DataService — 数据加载与预处理

依赖：FileFormatRegistry（文件格式选择）
       utils.detect_columns（列检测）
"""
import os
import logging
from typing import Optional
import pandas as pd

from .file_handler_registry import FileFormatRegistry, FILE_HANDLERS
try:
    from ..utils import detect_columns, filter_columns_keep_shift_only, generate_test_data, default_test_path
except ImportError:
    from utils import detect_columns, filter_columns_keep_shift_only, generate_test_data, default_test_path

logger = logging.getLogger(__name__)


class DataService:
    """数据加载与预处理服务"""

    def __init__(self, file_registry: FileFormatRegistry | None = None):
        self._file_registry = file_registry or FileFormatRegistry(FILE_HANDLERS)

    # ---- 文件加载 ----

    def load_file(self, path: str, **kwargs) -> pd.DataFrame:
        """
        根据扩展名自动选择处理器加载数据文件。

        Raises
        ------
        ValueError
            如果文件格式不支持
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {path}")

        handler = self._file_registry.find_handler(path)
        if handler is None:
            ext = os.path.splitext(path)[1]
            raise ValueError(f"不支持的文件格式: {ext}")

        logger.info("加载文件: %s (格式: %s)", path, handler.FORMAT_NAME)
        return handler.read(path, **kwargs)

    def load_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证并返回 DataFrame"""
        if not isinstance(df, pd.DataFrame):
            raise TypeError("参数必须是 pandas DataFrame")
        return df.copy()

    def get_file_registry(self) -> FileFormatRegistry:
        """返回文件格式注册表（供 UI 构建文件对话框）"""
        return self._file_registry

    # ---- 数据结构检测 ----

    @staticmethod
    def detect_structure(df: pd.DataFrame) -> dict:
        """
        检测 DataFrame 结构：分组列、数值列、ID 列。

        Returns
        -------
        dict
            {"columns": [...], "group_column": str|None, "value_columns": [...], "id_columns": [...]}
        """
        return detect_columns(df)

    # ---- 列过滤 ----

    @staticmethod
    def filter_shift_only(df: pd.DataFrame) -> pd.DataFrame:
        """若存在 _shift 列组，仅保留 _shift 列，去除 _T0 / _After"""
        before = list(df.columns)
        keep = filter_columns_keep_shift_only(before)
        removed = set(before) - set(keep)
        if removed:
            logger.info("后缀过滤: 移除 %s，保留 %d 列", sorted(removed), len(keep))
        return df[keep]

    # ---- 测试数据 ----

    @staticmethod
    def generate_test_data(path: Optional[str] = None) -> pd.DataFrame:
        """生成 Weibull 分布合成测试数据"""
        return generate_test_data(path)

    @staticmethod
    def get_default_test_path() -> str:
        """返回默认测试 CSV 路径"""
        return default_test_path()
