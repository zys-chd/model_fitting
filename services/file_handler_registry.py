"""
文件格式处理器 — ABC + 内置实现 + 注册表 + 自动匹配

新增文件格式：
    1. 继承 FileFormatHandler，实现 EXTENSIONS / FORMAT_NAME / read / write
    2. 在 FILE_HANDLERS 列表中注册
    3. 重启应用即可自动出现在文件对话框中
"""
from abc import ABC, abstractmethod
import os
from typing import ClassVar, Optional
import pandas as pd


class FileFormatHandler(ABC):
    """数据文件读写处理器抽象基类"""

    EXTENSIONS: ClassVar[list[str]] = []   # 如 ['.csv']
    FORMAT_NAME: ClassVar[str] = ""         # 如 "CSV"

    @abstractmethod
    def read(self, path: str, **kwargs) -> pd.DataFrame:
        """从文件读取 DataFrame"""
        ...

    def write(self, path: str, df: pd.DataFrame, **kwargs) -> None:
        """将 DataFrame 写入文件（默认 raise，子类按需实现）"""
        raise NotImplementedError(f"{self.FORMAT_NAME} 写入尚未实现")

    @classmethod
    def can_handle(cls, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in cls.EXTENSIONS


# ============================================================
# 内置实现
# ============================================================

class CSVHandler(FileFormatHandler):
    """CSV 文件读写"""

    EXTENSIONS: ClassVar[list[str]] = [".csv"]
    FORMAT_NAME: ClassVar[str] = "CSV"

    def read(self, path: str, **kwargs) -> pd.DataFrame:
        return pd.read_csv(path, **kwargs)

    def write(self, path: str, df: pd.DataFrame, **kwargs) -> None:
        df.to_csv(path, index=False, **kwargs)


class ExcelHandler(FileFormatHandler):
    """Excel 文件读写（.xlsx / .xls）"""

    EXTENSIONS: ClassVar[list[str]] = [".xlsx", ".xls"]
    FORMAT_NAME: ClassVar[str] = "Excel"

    def read(self, path: str, **kwargs) -> pd.DataFrame:
        sheet_name = kwargs.pop("sheet_name", 0)
        return pd.read_excel(path, sheet_name=sheet_name, **kwargs)

    def write(self, path: str, df: pd.DataFrame, **kwargs) -> None:
        df.to_excel(path, index=False, **kwargs)


class ParquetHandler(FileFormatHandler):
    """Parquet 文件读写（需 pyarrow 或 fastparquet）"""

    EXTENSIONS: ClassVar[list[str]] = [".parquet"]
    FORMAT_NAME: ClassVar[str] = "Parquet"

    def read(self, path: str, **kwargs) -> pd.DataFrame:
        return pd.read_parquet(path, **kwargs)

    def write(self, path: str, df: pd.DataFrame, **kwargs) -> None:
        df.to_parquet(path, index=False, **kwargs)


class JSONHandler(FileFormatHandler):
    """JSON 文件读写"""

    EXTENSIONS: ClassVar[list[str]] = [".json"]
    FORMAT_NAME: ClassVar[str] = "JSON"

    def read(self, path: str, **kwargs) -> pd.DataFrame:
        return pd.read_json(path, **kwargs)

    def write(self, path: str, df: pd.DataFrame, **kwargs) -> None:
        df.to_json(path, orient="records", force_ascii=False, indent=2, **kwargs)


# ============================================================
# 处理器列表（注册表）
# ============================================================

FILE_HANDLERS: list[FileFormatHandler] = [
    CSVHandler(),
    ExcelHandler(),
    ParquetHandler(),
    JSONHandler(),
]


# ============================================================
# 注册表工具
# ============================================================

class FileFormatRegistry:
    """文件格式注册表：根据扩展名自动匹配处理器"""

    def __init__(self, handlers: list[FileFormatHandler] | None = None):
        self._handlers: list[FileFormatHandler] = list(handlers or FILE_HANDLERS)
        # 构建扩展名 → handler 映射
        self._ext_map: dict[str, FileFormatHandler] = {}
        for h in self._handlers:
            for ext in h.EXTENSIONS:
                self._ext_map[ext.lower()] = h

    def find_handler(self, path: str) -> Optional[FileFormatHandler]:
        """根据文件扩展名找到匹配的处理器"""
        ext = os.path.splitext(path)[1].lower()
        return self._ext_map.get(ext)

    def get_all_extensions(self) -> list[str]:
        """返回所有支持的扩展名"""
        return sorted(self._ext_map.keys())

    def get_filter_pattern(self) -> list[tuple[str, str]]:
        """
        返回 tkinter 文件对话框 filetypes 格式的模式列表。

        Returns
        -------
        list[tuple[str, str]]
            如 [("数据文件", "*.csv *.xlsx *.xls"), ("CSV 文件", "*.csv"), ...]
        """
        # 按 FORMAT_NAME 分组
        by_format: dict[str, list[str]] = {}
        for h in self._handlers:
            exts = " ".join(f"*{e}" for e in h.EXTENSIONS)
            by_format[h.FORMAT_NAME] = h.EXTENSIONS

        all_exts = " ".join(f"*{e}" for e in self.get_all_extensions())
        patterns = [("所有支持格式", all_exts)]
        for h in self._handlers:
            exts_str = " ".join(f"*{e}" for e in h.EXTENSIONS)
            patterns.append((f"{h.FORMAT_NAME} 文件", exts_str))
        patterns.append(("所有文件", "*.*"))
        return patterns

    def register(self, handler: FileFormatHandler):
        """动态注册新的文件格式处理器"""
        self._handlers.append(handler)
        for ext in handler.EXTENSIONS:
            self._ext_map[ext.lower()] = handler
