"""
Log-logistic（对数逻辑斯蒂）分布模型
F(x) = 1 / (1 + (x/α)^(-β)) = (x/α)^β / (1 + (x/α)^β)
参数: α (scale), β (shape)
"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class LogLogisticModel(DistributionModel):
    """Log-logistic 分布拟合模型 — 参数 α, β"""

    KEY = "LogLogistic"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")
        xs, cdf = self.prepare_cdf_data(x)
        alpha0 = np.median(xs)
        beta0 = 2.0
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(alpha0, beta0),
                                   bounds=((0.01, 0.1), (np.inf, np.inf)),
                                   maxfev=10000)
        except Exception:
            raise RuntimeError("Log-logistic 拟合失败")
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)
        self.params = popt; self.pcov = pcov; self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, alpha, beta):
        t = (x / alpha) ** beta
        return t / (1 + t)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = \frac{(x/\alpha)^{\beta}}{1 + (x/\alpha)^{\beta}}"

    def get_param_names(self):
        return ["α (scale)", "β (shape)"]

    def get_description(self):
        return (
            "Log-Logistic 具有非单调失效率（先增后减）。\n\n"
            "参数：α (尺度), β (形状)\n\n"
            "适用：某些生物医学存活数据、非单调风险率场景。"
        )
