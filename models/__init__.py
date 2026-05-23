"""
模型注册中心
新增分布模型：在此 import 并加入 MODEL_INSTANCES 即可
"""
try:
    from .base import DistributionModel
    from .weibull import WeibullModel
    from .weibull3p import Weibull3PModel
    from .exponential import ExponentialModel
    from .lognormal import LognormalModel
    from .normal import NormalModel
    from .gamma import GammaModel
    from .loglogistic import LogLogisticModel
    from .gumbel import GumbelModel
    from .birnbaum_saunders import BirnbaumSaundersModel
except ImportError:
    from base import DistributionModel
    from weibull import WeibullModel
    from weibull3p import Weibull3PModel
    from exponential import ExponentialModel
    from lognormal import LognormalModel
    from normal import NormalModel
    from gamma import GammaModel
    from loglogistic import LogLogisticModel
    from gumbel import GumbelModel
    from birnbaum_saunders import BirnbaumSaundersModel

MODEL_INSTANCES = {
    WeibullModel.KEY: WeibullModel(),
    Weibull3PModel.KEY: Weibull3PModel(),
    ExponentialModel.KEY: ExponentialModel(),
    LognormalModel.KEY: LognormalModel(),
    NormalModel.KEY: NormalModel(),
    GammaModel.KEY: GammaModel(),
    LogLogisticModel.KEY: LogLogisticModel(),
    GumbelModel.KEY: GumbelModel(),
    BirnbaumSaundersModel.KEY: BirnbaumSaundersModel(),
}


def get_model(key: str) -> DistributionModel:
    """通过内部键获取模型实例"""
    if key not in MODEL_INSTANCES:
        raise KeyError(f"未知模型: {key}，可用: {list(MODEL_INSTANCES.keys())}")
    return MODEL_INSTANCES[key]


def get_all_models() -> dict:
    """返回所有模型实例"""
    return MODEL_INSTANCES
