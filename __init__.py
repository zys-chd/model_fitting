"""
model_fitting — 分布拟合工具包

用法:
    # 新版 MVP 架构（推荐）
    from model_fitting.ui.app_window import AppWindow
    app = AppWindow(dataframe=my_dataframe)

    # 旧版兼容
    from model_fitting import Model_Fitting_App
    app = Model_Fitting_App(dataframe=my_dataframe)

    # 独立运行
    python run.py
    python run.py data.csv
"""
from .model_fitting_app import Model_Fitting_App, launch as launch_legacy

# 新版 MVP 架构
from .ui.app_window import AppWindow
from .presenter import FittingPresenter
from .services import (
    DataService, FittingService, StatsService, ExportService,
    TransformStrategy, StatCalculator, FileFormatHandler,
    OutlierDetector, CDFEstimator, ExportHandler,
)

__all__ = [
    # 旧版兼容
    'Model_Fitting_App', 'launch_legacy',
    # 新版 MVP
    'AppWindow', 'FittingPresenter',
    # 服务层
    'DataService', 'FittingService', 'StatsService', 'ExportService',
    # 扩展点 ABC
    'TransformStrategy', 'StatCalculator', 'FileFormatHandler',
    'OutlierDetector', 'CDFEstimator', 'ExportHandler',
]
