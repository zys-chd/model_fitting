"""\
model_fitting — 分布拟合工具包

用法:
    # 推荐用法（新版 MVP 架构）
    from model_fitting.ui.app_window import AppWindow
    app = AppWindow(dataframe=my_dataframe)

    # 旧版兼容（自动转为 AppWindow）
    from model_fitting import Model_Fitting_App
    app = Model_Fitting_App(dataframe=my_dataframe)

    # 独立运行
    python run.py
    python run.py data.csv

"""

# 核心服务与模型（零 GUI 依赖，可安全导入）
from .presenter import FittingPresenter
from .services import (
    DataService, FittingService, StatsService, ExportService,
    TransformStrategy, StatCalculator, FileFormatHandler,
    OutlierDetector, CDFEstimator, ExportHandler,
)

# 旧版兼容别名：Model_Fitting_App → AppWindow，launch_legacy → run.launch
def Model_Fitting_App(parent=None, dataframe=None):
    """旧版兼容构造器 — 内部使用新版 AppWindow"""
    from .ui.app_window import AppWindow
    return AppWindow(parent=parent, dataframe=dataframe)

def launch_legacy(dataframe=None, csv_path=None):
    """旧版兼容启动器 — 内部使用新版 run.launch"""
    from .run import launch
    return launch(dataframe=dataframe, csv_path=csv_path)

# AppWindow 不在此处顶级导入（避免无 GUI 环境强制依赖 tkinter）
# 使用方请直接：from model_fitting.ui.app_window import AppWindow
def AppWindow(parent=None, dataframe=None):
    """便利构造器 — 自动延迟导入 AppWindow"""
    from .ui.app_window import AppWindow as _AppWindow
    return _AppWindow(parent=parent, dataframe=dataframe)

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
