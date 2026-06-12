"""
变换模式策略 — ABC + 内置实现 + 注册表

新增变换模式：
    1. 继承 TransformStrategy，实现 KEY / DISPLAY_NAME / transform / get_ylabel / get_fit_curve_xrange
    2. 在 TRANSFORM_REGISTRY 中注册
"""
from abc import ABC, abstractmethod
import numpy as np


class TransformStrategy(ABC):
    """CDF → Y 轴 变换策略抽象基类"""

    KEY: str = ""            # 唯一标识，如 "cdf", "lnln"
    DISPLAY_NAME: str = ""   # UI 显示名，如 "CDF", "ln(-ln(1-CDF))"

    @abstractmethod
    def transform(self, cdf: np.ndarray) -> np.ndarray:
        """将 CDF 值 [0,1] 变换到 Y 轴显示值"""
        ...

    @abstractmethod
    def get_ylabel(self) -> str:
        """返回 Y 轴标签文本"""
        ...

    def get_fit_curve_xrange(self, xs: np.ndarray, limit: float = 0) -> tuple:
        """
        返回拟合曲线建议的 X 范围 (xmin, xmax)。

        不同变换对边界敏感度不同——例如 CDF 模式下 x 范围可以略宽，
        ln(-ln) 模式下需要以 limit 为参考收紧边界。
        """
        if limit > 0:
            return (min(xs.min() * 0.95, limit * 0.9),
                    max(xs.max() * 1.05, limit * 1.1))
        return (xs.min() * 0.95, xs.max() * 1.05)


# ============================================================
# 内置实现
# ============================================================

class CDFTransform(TransformStrategy):
    """恒等变换：直接显示经验 CDF"""

    KEY = "cdf"
    DISPLAY_NAME = "CDF"

    def transform(self, cdf: np.ndarray) -> np.ndarray:
        return np.asarray(cdf)

    def get_ylabel(self) -> str:
        return "CDF"


class LnLnTransform(TransformStrategy):
    """ln(-ln(1-CDF)) 变换（Weibull 概率纸坐标）"""

    KEY = "lnln"
    DISPLAY_NAME = "ln(-ln(1-CDF))"

    def transform(self, cdf: np.ndarray) -> np.ndarray:
        return _safe_lnln(cdf)

    def get_ylabel(self) -> str:
        return "ln(-ln(1-CDF))"

    def get_fit_curve_xrange(self, xs: np.ndarray, limit: float = 0) -> tuple:
        """ln(-ln) 模式下需要以 limit 为边界参考"""
        if limit > 0:
            xmin = 0.9 * min(limit, xs.min())
            xmax = 1.1 * max(limit, xs.max())
        else:
            xmin = xs.min() * 0.98
            xmax = xs.max() * 1.02
        return (xmin, xmax)


# ---- 工具函数 ----

def _safe_lnln(cdf_vals):
    """安全的 ln(-ln(1-CDF)) 变换，返回 (transformed)"""
    import warnings

    inner = 1 - np.asarray(cdf_vals, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        warnings.filterwarnings("ignore", "divide by zero")
        warnings.filterwarnings("ignore", "invalid value")
        inner = np.where(inner <= 0, 1e-300, inner)
        result = np.log(-np.log(inner))
        warnings.resetwarnings()
    return np.nan_to_num(result, nan=-100, posinf=100, neginf=-100)


# ============================================================
# 注册表
# ============================================================

TRANSFORM_REGISTRY: dict[str, TransformStrategy] = {
    "cdf": CDFTransform(),
    "lnln": LnLnTransform(),
}


def get_transform(key: str) -> TransformStrategy:
    """通过 key 获取变换策略实例"""
    if key not in TRANSFORM_REGISTRY:
        raise KeyError(f"未知变换模式: {key}，可用: {list(TRANSFORM_REGISTRY.keys())}")
    return TRANSFORM_REGISTRY[key]


def get_all_transforms() -> dict[str, TransformStrategy]:
    """返回所有已注册的变换策略"""
    return dict(TRANSFORM_REGISTRY)
