"""
Normal（正态）分布模型
F(x) = Φ((x-μ)/σ)
"""
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class NormalModel(DistributionModel):
    """正态分布拟合模型"""

    KEY = "Normal"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        if len(x) < 3:
            raise RuntimeError("样本量不足，无法拟合 Normal 分布")

        xs, cdf = self.prepare_cdf_data(x)

        mu = np.mean(x)
        sigma = np.std(x)

        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(mu, sigma), maxfev=10000)
        except Exception:
            raise RuntimeError("Normal 拟合失败")

        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)

        self.params = popt
        self.pcov = pcov
        self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, mu, sigma):
        return norm.cdf(x, mu, sigma)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = \Phi\left(\frac{x - \mu}{\sigma}\right)"

    def get_param_names(self):
        return ["μ (mean)", "σ (std)"]
