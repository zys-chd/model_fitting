"""
services — 业务逻辑层（纯 Python，零 GUI 依赖）

分层：
    *_registry.py   — 扩展点 ABC + 内置实现 + 注册表
    *_service.py    — 业务编排（组合注册表能力）
"""
from .transform_registry import TransformStrategy, TRANSFORM_REGISTRY, get_transform, get_all_transforms
from .stat_registry import StatCalculator, STAT_REGISTRY, CompositeStatsCalculator, get_calculator, get_all_calculators
from .file_handler_registry import FileFormatHandler, FileFormatRegistry, FILE_HANDLERS
from .outlier_registry import OutlierDetector, OUTLIER_REGISTRY, get_outlier_detector
from .cdf_estimator_registry import CDFEstimator, CDF_ESTIMATOR_REGISTRY, get_cdf_estimator
from .export_handler_registry import ExportHandler, EXPORT_REGISTRY, get_export_handler
from .data_service import DataService
from .fitting_service import FittingService
from .stats_service import StatsService
from .export_service import ExportService

__all__ = [
    "TransformStrategy", "TRANSFORM_REGISTRY", "get_transform", "get_all_transforms",
    "StatCalculator", "STAT_REGISTRY", "CompositeStatsCalculator", "get_calculator", "get_all_calculators",
    "FileFormatHandler", "FileFormatRegistry", "FILE_HANDLERS",
    "OutlierDetector", "OUTLIER_REGISTRY", "get_outlier_detector",
    "CDFEstimator", "CDF_ESTIMATOR_REGISTRY", "get_cdf_estimator",
    "ExportHandler", "EXPORT_REGISTRY", "get_export_handler",
    "DataService", "FittingService", "StatsService", "ExportService",
]
