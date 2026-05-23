"""
模型注册中心
新增分布模型：在此 import 并加入 MODEL_INSTANCES 即可
"""
try:
    from .base import DistributionModel
    from .weibull import WeibullModel
    from .lognormal import LognormalModel
    from .normal import NormalModel
except ImportError:
    from base import DistributionModel
    from weibull import WeibullModel
    from lognormal import LognormalModel
    from normal import NormalModel

# 模型实例注册表（内部键 -> 模型实例）
MODEL_INSTANCES = {
    WeibullModel.KEY: WeibullModel(),
    LognormalModel.KEY: LognormalModel(),
    NormalModel.KEY: NormalModel(),
}


def get_model(key: str) -> DistributionModel:
    """通过内部键获取模型实例"""
    if key not in MODEL_INSTANCES:
        raise KeyError(f"未知模型: {key}，可用: {list(MODEL_INSTANCES.keys())}")
    return MODEL_INSTANCES[key]


def get_all_models() -> dict:
    """返回所有模型实例"""
    return MODEL_INSTANCES
