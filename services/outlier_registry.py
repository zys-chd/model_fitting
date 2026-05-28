"""
离群点检测器 — ABC + 内置实现 + 注册表

新增离群检测方法：
    1. 继承 OutlierDetector，实现 KEY / DISPLAY_NAME / detect
    2. 在 OUTLIER_REGISTRY 中注册
    3. UI 中自动出现新选项
"""
from abc import ABC, abstractmethod
from typing import ClassVar
import numpy as np


class OutlierDetector(ABC):
    """离群点检测策略抽象基类"""

    KEY: ClassVar[str] = ""
    DISPLAY_NAME: ClassVar[str] = ""

    @abstractmethod
    def detect(
        self,
        samples: np.ndarray,
        cdf_observed: np.ndarray,
        cdf_predicted: np.ndarray,
    ) -> np.ndarray:
        """
        检测离群点。

        Parameters
        ----------
        samples : np.ndarray
            原始样本值
        cdf_observed : np.ndarray
            经验 CDF 值（与 samples 同长度）
        cdf_predicted : np.ndarray
            模型预测 CDF 值

        Returns
        -------
        np.ndarray
            布尔掩码，True 表示该位置为离群点
        """
        ...

    def get_default_threshold(self) -> float:
        """返回默认阈值（子类可覆盖）"""
        return 3.0


# ============================================================
# 内置实现
# ============================================================

class MADOutlierDetector(OutlierDetector):
    """
    MAD（中位数绝对偏差）检测法

    以 CDF 残差的中位数绝对偏差为基准，对离群点检测更稳健。
    """

    KEY: ClassVar[str] = "mad"
    DISPLAY_NAME: ClassVar[str] = "MAD（中位数绝对偏差）"

    def detect(
        self,
        samples: np.ndarray,
        cdf_observed: np.ndarray,
        cdf_predicted: np.ndarray,
    ) -> np.ndarray:
        residuals = np.abs(np.asarray(cdf_observed) - np.asarray(cdf_predicted))
        med = float(np.median(residuals))
        mad = float(np.median(np.abs(residuals - med)))
        threshold = med + self.get_default_threshold() * 1.4826 * mad if mad > 0 else 3.0 * float(np.std(residuals))
        return residuals > threshold


class ZScoreOutlierDetector(OutlierDetector):
    """
    Z-Score 检测法

    以 CDF 残差的标准分数为基准，适用于残差近似正态分布的场景。
    """

    KEY: ClassVar[str] = "zscore"
    DISPLAY_NAME: ClassVar[str] = "Z-Score（标准分数）"

    def detect(
        self,
        samples: np.ndarray,
        cdf_observed: np.ndarray,
        cdf_predicted: np.ndarray,
    ) -> np.ndarray:
        residuals = np.asarray(cdf_observed) - np.asarray(cdf_predicted)
        mean_r = float(np.mean(residuals))
        std_r = float(np.std(residuals))
        if std_r < 1e-12:
            return np.zeros(len(residuals), dtype=bool)
        z_scores = np.abs(residuals - mean_r) / std_r
        return z_scores > self.get_default_threshold()


class IQROutlierDetector(OutlierDetector):
    """
    IQR（四分位距）检测法

    以残差的 IQR 为基准，经典的箱线图方法。
    """

    KEY: ClassVar[str] = "iqr"
    DISPLAY_NAME: ClassVar[str] = "IQR（四分位距）"

    def detect(
        self,
        samples: np.ndarray,
        cdf_observed: np.ndarray,
        cdf_predicted: np.ndarray,
    ) -> np.ndarray:
        residuals = np.asarray(cdf_observed) - np.asarray(cdf_predicted)
        q1 = float(np.percentile(residuals, 25))
        q3 = float(np.percentile(residuals, 75))
        iqr = q3 - q1
        if iqr < 1e-12:
            return np.zeros(len(residuals), dtype=bool)
        lower = q1 - self.get_default_threshold() * 0.5 * iqr
        upper = q3 + self.get_default_threshold() * 0.5 * iqr
        return (residuals < lower) | (residuals > upper)


# ============================================================
# 注册表
# ============================================================

OUTLIER_REGISTRY: dict[str, OutlierDetector] = {
    "mad": MADOutlierDetector(),
    "zscore": ZScoreOutlierDetector(),
    "iqr": IQROutlierDetector(),
}


def get_outlier_detector(key: str) -> OutlierDetector:
    """通过 key 获取离群检测器"""
    if key not in OUTLIER_REGISTRY:
        raise KeyError(f"未知离群检测器: {key}，可用: {list(OUTLIER_REGISTRY.keys())}")
    return OUTLIER_REGISTRY[key]


def get_all_outlier_detectors() -> dict[str, OutlierDetector]:
    """返回所有已注册的离群检测器"""
    return dict(OUTLIER_REGISTRY)
