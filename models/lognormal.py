"""
Lognormal（对数正态）分布模型
F(x) = Φ((ln(x)-μ)/σ)
"""
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import lognorm

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class LognormalModel(DistributionModel):
    """对数正态分布拟合模型"""

    KEY = "Lognormal"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足，无法拟合 Lognormal 分布")

        xs, cdf = self.prepare_cdf_data(x)

        log_x = np.log(x)
        mu = np.mean(log_x)
        sigma = np.std(log_x)

        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(sigma, 0, mu), maxfev=10000)
        except Exception:
            raise RuntimeError("Lognormal 拟合失败")

        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)

        self.params = popt
        self.pcov = pcov
        self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, s, loc, scale):
        return lognorm.cdf(x, s, loc, scale)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = \Phi\left(\frac{\ln(x) - \mu}{\sigma}\right)"

    def get_param_names(self):
        return ["σ (shape)", "μ (location)", "scale"]
