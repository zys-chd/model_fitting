"""
统计量计算器 — ABC + 内置实现 + 注册表 + 组合器

新增统计指标：
    1. 继承 StatCalculator，实现 KEY / DISPLAY_ORDER / compute
    2. 在 STAT_REGISTRY 中注册
    3. （可选）在 StatsService 的默认 calculator 列表中添加
"""
from abc import ABC, abstractmethod
from typing import Any, ClassVar
import numpy as np


class StatCalculator(ABC):
    """统计量计算器抽象基类 — 无状态，可组合"""

    KEY: ClassVar[str] = ""
    DISPLAY_ORDER: ClassVar[int] = 100  # 越小越靠前

    @abstractmethod
    def compute(self, samples: np.ndarray, **context) -> dict[str, Any]:
        """
        计算统计量。

        Parameters
        ----------
        samples : np.ndarray
            样本数据
        **context
            额外上下文，可包含: model, params, limit, fit_result

        Returns
        -------
        dict[str, Any]
            {显示名: 值}，如 {"均值": 1.23, "标准差": 0.45}
        """
        ...


# ============================================================
# 内置实现
# ============================================================

class BasicStatsCalculator(StatCalculator):
    """基础描述性统计：count, mean, std, median, quantiles, min, max, skewness, CV"""

    KEY: ClassVar[str] = "basic"
    DISPLAY_ORDER: ClassVar[int] = 10

    def compute(self, samples: np.ndarray, **context) -> dict[str, Any]:
        from scipy import stats as sp_stats
        s = np.asarray(samples)
        n = len(s)
        if n == 0:
            return {}
        q_low = context.get("quantile_low", 5)
        q_high = context.get("quantile_high", 95)
        q_low_v = float(np.percentile(s, q_low))
        q_high_v = float(np.percentile(s, q_high))
        mean_v = float(np.mean(s))
        std_v = float(np.std(s, ddof=1)) if n > 1 else 0.0
        cv_pct = (std_v / mean_v * 100) if mean_v != 0 else float('nan')
        iqr = q_high_v - q_low_v
        riqr = (iqr / mean_v) if mean_v != 0 else float('nan')
        return {
            "样本数": n,
            "均值": mean_v,
            "标准差": std_v,
            "中位数": float(np.median(s)),
            f"{q_low:.0f}%分位数": q_low_v,
            f"{q_high:.0f}%分位数": q_high_v,
            "分位数间距": round(iqr, 4),
            "相对分位数间距": round(riqr, 4),
            "最小值": float(np.min(s)),
            "最大值": float(np.max(s)),
            "偏度": float(sp_stats.skew(s)),
            "变异系数(%)": round(cv_pct, 2),
        }


class FitAtLimitCalculator(StatCalculator):
    """在 limit 值处的拟合 CDF 值 F(limit)"""

    KEY: ClassVar[str] = "fit_at_limit"
    DISPLAY_ORDER: ClassVar[int] = 90

    def compute(self, samples: np.ndarray, **context) -> dict[str, Any]:
        model = context.get("model")
        params = context.get("params")
        limit = context.get("limit")
        if model is None or params is None or limit is None:
            return {}
        try:
            f_at_limit = float(model.cdf(limit, params))
        except Exception:
            return {}
        return {"limit处F值": f_at_limit}


# ============================================================
# 注册表
# ============================================================

STAT_REGISTRY: dict[str, StatCalculator] = {
    "basic": BasicStatsCalculator(),
    "fit_at_limit": FitAtLimitCalculator(),
}


def get_calculator(key: str) -> StatCalculator:
    """通过 key 获取统计计算器"""
    if key not in STAT_REGISTRY:
        raise KeyError(f"未知统计量: {key}，可用: {list(STAT_REGISTRY.keys())}")
    return STAT_REGISTRY[key]


def get_all_calculators() -> dict[str, StatCalculator]:
    """返回所有已注册的统计计算器"""
    return dict(STAT_REGISTRY)


# ============================================================
# 组合器
# ============================================================

class CompositeStatsCalculator:
    """组合多个 StatCalculator，统一计算所有统计量"""

    def __init__(self, calculators: list[StatCalculator] | None = None):
        if calculators is None:
            # 默认使用全部注册的计算器，按 DISPLAY_ORDER 排序
            calculators = sorted(
                STAT_REGISTRY.values(), key=lambda c: c.DISPLAY_ORDER
            )
        self._calculators = list(calculators)

    def add_calculator(self, calculator: StatCalculator):
        """动态添加计算器"""
        self._calculators.append(calculator)
        self._calculators.sort(key=lambda c: c.DISPLAY_ORDER)

    def compute_all(self, samples: np.ndarray, **context) -> dict[str, Any]:
        """依次调用所有计算器，合并结果"""
        result: dict[str, Any] = {}
        for calc in self._calculators:
            try:
                result.update(calc.compute(samples, **context))
            except Exception:
                continue
        return result
