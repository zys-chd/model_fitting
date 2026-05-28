"""
FittingService — 拟合调度服务

依赖：models.DistributionModel（分布模型策略）
       services.transform_registry（变换策略）
       services.cdf_estimator_registry（CDF 估计策略）
       services.outlier_registry（离群检测策略）
"""
import logging
from typing import Optional
import numpy as np

from .transform_registry import TransformStrategy, get_transform, TRANSFORM_REGISTRY
from .cdf_estimator_registry import CDFEstimator, get_cdf_estimator, CDF_ESTIMATOR_REGISTRY
from .outlier_registry import OutlierDetector, get_outlier_detector, OUTLIER_REGISTRY

try:
    from ..models import MODEL_INSTANCES
    from ..models.base import DistributionModel
except ImportError:
    from models import MODEL_INSTANCES
    from models.base import DistributionModel

logger = logging.getLogger(__name__)


class FitResult:
    """单次拟合结果"""

    __slots__ = ("model_name", "params", "pcov", "r_squared",
                 "xs", "cdf_raw", "y_transformed", "n_samples")

    def __init__(self, model_name, params, pcov, r_squared,
                 xs, cdf_raw, y_transformed, n_samples):
        self.model_name = model_name
        self.params = params
        self.pcov = pcov
        self.r_squared = r_squared
        self.xs = xs
        self.cdf_raw = cdf_raw
        self.y_transformed = y_transformed
        self.n_samples = n_samples


class FittingService:
    """
    拟合调度服务 — 协调模型拟合、变换和离群检测。

    通过依赖注入传入注册表，测试时可替换。
    """

    def __init__(
        self,
        models: dict[str, DistributionModel] | None = None,
        transform_registry: dict[str, TransformStrategy] | None = None,
        cdf_estimator_registry: dict[str, CDFEstimator] | None = None,
        outlier_registry: dict[str, OutlierDetector] | None = None,
    ):
        self._models = models if models is not None else MODEL_INSTANCES
        self._transform_registry = transform_registry or TRANSFORM_REGISTRY
        self._cdf_estimator_registry = cdf_estimator_registry or CDF_ESTIMATOR_REGISTRY
        self._outlier_registry = outlier_registry or OUTLIER_REGISTRY

    # ---- 模型管理 ----

    def get_model(self, key: str) -> DistributionModel:
        if key not in self._models:
            raise KeyError(f"未知模型: {key}，可用: {list(self._models.keys())}")
        return self._models[key]

    def get_available_models(self) -> dict[str, DistributionModel]:
        return dict(self._models)

    def get_model_keys(self) -> list[str]:
        return list(self._models.keys())

    # ---- 变换管理 ----

    def get_transform(self, key: str) -> TransformStrategy:
        return get_transform(key)

    def get_available_transforms(self) -> dict[str, TransformStrategy]:
        return dict(self._transform_registry)

    # ---- CDF 估计器 ----

    def get_cdf_estimator(self, key: str) -> CDFEstimator:
        return get_cdf_estimator(key)

    # ---- 离群检测 ----

    def get_outlier_detector(self, key: str) -> OutlierDetector:
        return get_outlier_detector(key)

    def detect_outliers(
        self,
        samples: np.ndarray,
        model_key: str,
        outlier_key: str = "mad",
        cdf_estimator_key: str = "median_rank",
    ) -> np.ndarray:
        """
        对样本执行离群点检测。

        Returns
        -------
        np.ndarray
            布尔掩码，True 表示离群点
        """
        model = self.get_model(model_key)
        cdf_est = self.get_cdf_estimator(cdf_estimator_key)
        detector = self.get_outlier_detector(outlier_key)

        # 获取拟合值和观测值
        fit_result = self.fit_single(samples, model_key, cdf_estimator_key)
        cdf_pred = model.cdf(fit_result.xs, fit_result.params)
        cdf_obs = fit_result.cdf_raw

        mask = detector.detect(samples, cdf_obs, cdf_pred)
        logger.debug(
            "离群检测: model=%s detector=%s n=%d outliers=%d",
            model_key, outlier_key, len(samples), int(mask.sum()),
        )
        return mask

    # ---- 拟合 ----

    def fit_single(
        self,
        samples: np.ndarray,
        model_key: str,
        cdf_estimator_key: str = "median_rank",
        transform_key: str = "cdf",
    ) -> FitResult:
        """
        对单组样本执行拟合。

        Parameters
        ----------
        samples : np.ndarray
            原始样本
        model_key : str
            模型标识键
        cdf_estimator_key : str
            CDF 估计器键
        transform_key : str
            变换模式键

        Returns
        -------
        FitResult
        """
        x = np.asarray(samples)
        x = x[np.isfinite(x)]

        model = self.get_model(model_key)
        cdf_estimator = self.get_cdf_estimator(cdf_estimator_key)
        transform = self.get_transform(transform_key)

        # 使用 CDFEstimator 估计
        xs, cdf_raw = cdf_estimator.estimate(x)

        # 调用 DistributionModel.fit()（传入 cdf_estimator，若模型支持）
        try:
            popt, pcov, r2, _xs, _cdf = model.fit(x, cdf_estimator=cdf_estimator)
        except TypeError:
            # 兼容旧模型（不接受 cdf_estimator 参数）
            popt, pcov, r2, _xs, _cdf = model.fit(x)

        # 变换 CDF 值
        y_transformed = transform.transform(_cdf)

        return FitResult(
            model_name=model_key,
            params=popt,
            pcov=pcov,
            r_squared=r2,
            xs=_xs,
            cdf_raw=_cdf,
            y_transformed=y_transformed,
            n_samples=len(x),
        )

    def fit_for_plot(
        self,
        samples: np.ndarray,
        model_key: str,
        transform_key: str = "cdf",
        cdf_estimator_key: str = "median_rank",
    ) -> FitResult:
        """拟合并返回可用于绘图的 FitResult（等同于 fit_single）"""
        return self.fit_single(
            samples, model_key,
            cdf_estimator_key=cdf_estimator_key,
            transform_key=transform_key,
        )

    def fit_grouped(
        self,
        df,
        col: str,
        group_col: str,
        groups: list[str],
        model_key: str,
        transform_key: str = "cdf",
        cdf_estimator_key: str = "median_rank",
    ) -> dict[str, FitResult]:
        """
        对 DataFrame 的每个分组执行拟合。

        Returns
        -------
        dict[str, FitResult]
            {group_name: FitResult}
        """
        results = {}
        for g in groups:
            sub = df.loc[df[group_col] == g, col].dropna()
            if len(sub) < 3:
                continue
            try:
                results[g] = self.fit_single(
                    sub.values, model_key,
                    cdf_estimator_key=cdf_estimator_key,
                    transform_key=transform_key,
                )
            except Exception as e:
                logger.warning("拟合失败 col=%s group=%s: %s", col, g, e)
        return results
