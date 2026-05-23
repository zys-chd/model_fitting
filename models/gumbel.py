"""
Gumbel（极值I型最小值）分布模型
F(x) = 1 - exp(-exp((x-μ)/σ))
参数: μ (location), σ (scale)
"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class GumbelModel(DistributionModel):
    """Gumbel（最小值型）分布拟合模型 — 参数 μ, σ"""

    KEY = "Gumbel"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")
        xs, cdf = self.prepare_cdf_data(x)
        mu0, sigma0 = np.mean(xs) * 0.85, np.std(xs)
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(mu0, sigma0),
                                   bounds=((-np.inf, 0.01), (np.inf, np.inf)),
                                   maxfev=10000)
        except Exception:
            raise RuntimeError("Gumbel 拟合失败")
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)
        self.params = popt; self.pcov = pcov; self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, mu, sigma):
        z = (x - mu) / sigma
        return 1 - np.exp(-np.exp(z))

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = 1 - \exp\left(-e^{(x - \mu) / \sigma}\right)"

    def get_param_names(self):
        return ["μ (location)", "σ (scale)"]

    def get_description(self):
        return (
            "Gumbel 是最小值极值分布，常用于最弱环节建模。\n\n"
            "参数：μ (位置), σ (尺度)\n\n"
            "适用：腐蚀深度、电介质击穿电压、最弱链模型。"
        )
