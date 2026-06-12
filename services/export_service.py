"""
ExportService — 导出服务

依赖：services.export_handler_registry（导出格式选择）
"""
import os
import logging
from typing import Optional

from .export_handler_registry import ExportHandler, EXPORT_REGISTRY, get_export_handler

logger = logging.getLogger(__name__)


class ExportService:
    """图表与参数导出服务"""

    def __init__(self, export_registry: dict[str, ExportHandler] | None = None):
        self._export_registry = export_registry or EXPORT_REGISTRY

    def export_figure(self, figure, path: str, **kwargs) -> None:
        """
        导出 matplotlib Figure 到图片文件。

        Parameters
        ----------
        figure : matplotlib.figure.Figure
        path : str
            输出路径（扩展名决定格式）
        **kwargs
            传给 savefig 的参数（如 dpi, bbox_inches）
        """
        kwargs.setdefault("dpi", 300)
        kwargs.setdefault("bbox_inches", "tight")
        figure.savefig(path, **kwargs)
        logger.info("图表已导出: %s", path)

    def export_parameters(
        self,
        path: str,
        fit_results: dict,
        models: dict,
        stats_cache: dict,
        **kwargs,
    ) -> None:
        """
        导出拟合参数到文件（根据扩展名自动选择格式）。

        Parameters
        ----------
        path : str
            输出路径
        fit_results : dict
            {(col, group): (model_name, params, r2, xs, cdf)}
        models : dict
            {model_key: DistributionModel}
        stats_cache : dict
            {(col, group): {metric: value}}
        """
        if not fit_results:
            raise ValueError("没有可导出的拟合结果")

        ext = os.path.splitext(path)[1].lower()
        handler = self._find_handler_by_extension(ext)
        if handler is None:
            raise ValueError(f"不支持的导出格式: {ext}")

        handler.export(path, fit_results, models, stats_cache, **kwargs)
        logger.info("参数已导出: %s (格式: %s)", path, handler.FORMAT_NAME)

    def _find_handler_by_extension(self, ext: str) -> Optional[ExportHandler]:
        for handler in self._export_registry.values():
            if ext in handler.EXTENSIONS:
                return handler
        return None

    def get_supported_extensions(self) -> list[str]:
        return [ext for h in self._export_registry.values() for ext in h.EXTENSIONS]
