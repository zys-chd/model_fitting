"""
经验 CDF 估计器 — ABC + 内置实现 + 注册表

新增 CDF 估计方法：
    1. 继承 CDFEstimator，实现 KEY / DISPLAY_NAME / estimate
    2. 在 CDF_ESTIMATOR_REGISTRY 中注册
"""
from abc import ABC, abstractmethod
from typing import ClassVar
import numpy as np


class CDFEstimator(ABC):
    """经验累积分布函数估计器抽象基类"""

    KEY: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""

    @abstractmethod
    def estimate(self, samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        从样本估计经验 CDF。

        Parameters
        ----------
        samples : np.ndarray
            原始样本数据

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (sorted_x, cdf_values) — 排序后的 x 和对应 CDF 值
        """
        ...


# ============================================================
# 内置实现
# ============================================================

class MedianRankEstimator(CDFEstimator):
    """
    中位秩估计: F(i) = (i - 0.3) / (N + 0.4)

    最常用的经验 CDF 公式，对小样本无偏性较好。
    """

    KEY: ClassVar[str] = "median_rank"
    DISPLAY_NAME: ClassVar[str] = "中位秩 (i-0.3)/(N+0.4)"

    def estimate(self, samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs = np.sort(np.asarray(samples))
        n = len(xs)
        cdf = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        return xs, cdf


class MeanRankEstimator(CDFEstimator):
    """
    平均秩估计: F(i) = i / (N + 1)

    简单直接，适用于大样本。
    """

    KEY: ClassVar[str] = "mean_rank"
    DISPLAY_NAME: ClassVar[str] = "平均秩 i/(N+1)"

    def estimate(self, samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs = np.sort(np.asarray(samples))
        n = len(xs)
        cdf = np.arange(1, n + 1) / (n + 1)
        return xs, cdf


class KaplanMeierEstimator(CDFEstimator):
    """
    Kaplan-Meier 乘积极限估计

    适用于含右删失数据的场景。对于完整数据，退化为 1 - 生存函数。
    """

    KEY: ClassVar[str] = "kaplan_meier"
    DISPLAY_NAME: ClassVar[str] = "Kaplan-Meier"

    def estimate(self, samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # 完整数据场景：Kaplan-Meier = 经验生存函数的补集
        # 等价于 1 - (N - rank + 1) / N
        xs = np.sort(np.asarray(samples))
        n = len(xs)
        # 对于完整数据，KM 生存函数 = (N-i)/N，所以 CDF = i/N
        # 这里使用略有偏差的版本更接近中位秩
        survival = np.ones(n)
        for i in range(n):
            at_risk = n - i
            events = 1
            survival[i] = survival[i - 1] * (1 - events / at_risk) if i > 0 else (1 - events / at_risk)
        cdf = 1 - survival
        return xs, cdf


# ============================================================
# 注册表
# ============================================================

CDF_ESTIMATOR_REGISTRY: dict[str, CDFEstimator] = {
    "median_rank": MedianRankEstimator(),
    "mean_rank": MeanRankEstimator(),
    "kaplan_meier": KaplanMeierEstimator(),
}


def get_cdf_estimator(key: str) -> CDFEstimator:
    """通过 key 获取 CDF 估计器"""
    if key not in CDF_ESTIMATOR_REGISTRY:
        raise KeyError(f"未知 CDF 估计器: {key}，可用: {list(CDF_ESTIMATOR_REGISTRY.keys())}")
    return CDF_ESTIMATOR_REGISTRY[key]


def get_all_cdf_estimators() -> dict[str, CDFEstimator]:
    """返回所有已注册的 CDF 估计器"""
    return dict(CDF_ESTIMATOR_REGISTRY)
