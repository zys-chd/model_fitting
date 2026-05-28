"""测试所有的扩展点 ABC 一致性"""
import inspect
from abc import ABC, abstractmethod

# 导入所有 ABC
from services.transform_registry import TransformStrategy
from services.stat_registry import StatCalculator
from services.file_handler_registry import FileFormatHandler
from services.outlier_registry import OutlierDetector
from services.cdf_estimator_registry import CDFEstimator
from services.export_handler_registry import ExportHandler
from models.base import DistributionModel


ALL_ABCS = [
    TransformStrategy,
    StatCalculator,
    FileFormatHandler,
    OutlierDetector,
    CDFEstimator,
    ExportHandler,
    DistributionModel,
]


class TestAllABCsAreAbstract:
    """验证所有基类确实是抽象类"""

    def test_cannot_instantiate_abc_directly(self):
        for abc_cls in ALL_ABCS:
            try:
                abc_cls()
                assert False, f"{abc_cls.__name__} should not be instantiable"
            except TypeError:
                pass  # expected

    def test_all_are_abc_subclasses(self):
        for abc_cls in ALL_ABCS:
            assert issubclass(abc_cls, ABC), f"{abc_cls.__name__} should subclass ABC"

    def test_each_has_abstract_methods(self):
        for abc_cls in ALL_ABCS:
            abs_methods = [
                name for name, method in inspect.getmembers(abc_cls, inspect.isfunction)
                if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
            ]
            assert len(abs_methods) > 0, f"{abc_cls.__name__} should have at least one abstract method"
