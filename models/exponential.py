"""
Exponential（指数）分布模型
F(x) = 1 - exp(-x/θ)
参数: θ (scale) = 1/λ
"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class ExponentialModel(DistributionModel):
    """指数分布拟合模型 — 参数 θ"""

    KEY = "Exponential"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")
        xs, cdf = self.prepare_cdf_data(x)
        theta0 = np.mean(xs)
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(theta0,), maxfev=10000)
        except Exception:
            raise RuntimeError("Exponential 拟合失败")
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)
        self.params = popt; self.pcov = pcov; self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, theta):
        return 1 - np.exp(-x / theta)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = 1 - e^{-x / \theta}"

    def get_param_names(self):
        return ["θ (scale)"]

    def get_description(self):
        return (
            "指数分布是 Weibull β=1 的特例，失效率恒定。\n\n"
            "参数：θ (尺度/均值) = 1/λ\n\n"
            "适用：无记忆性系统，随机失效阶段（浴盆曲线底部）。"
        )
