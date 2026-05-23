"""
Weibull（威布尔）分布模型
F(x) = 1 - exp(-(x/η)^β)
"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class WeibullModel(DistributionModel):
    """Weibull 分布拟合模型 — 参数 β (shape), η (scale)"""

    KEY = "Weibull"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足，无法拟合 Weibull 分布")

        xs, cdf = self.prepare_cdf_data(x)
        beta0, eta0 = 1.5, np.mean(xs)

        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(beta0, eta0), maxfev=10000)
        except Exception:
            raise RuntimeError("Weibull 拟合失败")

        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)

        self.params = popt
        self.pcov = pcov
        self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, beta, eta):
        return 1 - np.exp(-(x / eta) ** beta)

    def cdf(self, x, params):
        beta, eta = params
        return self._cdf_func(x, beta, eta)

    def get_formula(self):
        # return "F(x) = 1 - exp(-(x/η)^β)"
        return r"F(x) = 1 - \exp\left(-\left(\frac{x}{\eta}\right)^{\beta}\right)"

    def get_param_names(self):
        return ["β (shape)", "η (scale)"]
