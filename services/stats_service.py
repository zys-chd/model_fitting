"""
StatsService — 统计计算服务

依赖：services.stat_registry.CompositeStatsCalculator
"""
import logging
from typing import Any
import numpy as np

from .stat_registry import CompositeStatsCalculator, StatCalculator, STAT_REGISTRY

logger = logging.getLogger(__name__)


class StatsService:
    """描述性统计服务 — 组合多个 StatCalculator"""

    def __init__(self, calculators: list[StatCalculator] | None = None):
        self._composite = CompositeStatsCalculator(calculators)

    def compute_all(self, samples: np.ndarray, **context) -> dict[str, Any]:
        """
        计算所有已注册的统计量。

        Parameters
        ----------
        samples : np.ndarray
            样本数据
        **context
            传给各 StatCalculator 的上下文，如 model, params, limit

        Returns
        -------
        dict[str, Any]
            {显示名: 值}
        """
        return self._composite.compute_all(samples, **context)

    def compute_basic(self, samples: np.ndarray) -> dict[str, Any]:
        """仅计算基础统计量（不含依赖拟合上下文的指标）"""
        return self._composite.compute_all(samples)

    @staticmethod
    def compute_f_at_limit(model, params, limit: float) -> float:
        """计算 limit 处的拟合 CDF 值"""
        try:
            return float(model.cdf(limit, params))
        except Exception as e:
            logger.debug("F_at_limit 计算失败: %s", e)
            return float("nan")
