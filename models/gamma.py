"""
Gamma 分布模型
F(x) = P(k, x/θ)   (正则化下不完全 Gamma 函数)
参数: k (shape), θ (scale)
"""
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import gammainc

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class GammaModel(DistributionModel):
    """Gamma 分布拟合模型 — 参数 k, θ"""

    KEY = "Gamma"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")
        xs, cdf = self.prepare_cdf_data(x)
        m, v = np.mean(xs), np.var(xs)
        k0 = max(m ** 2 / v if v > 0 else 1.5, 0.5)
        theta0 = max(v / m if m > 0 else m, 0.5)
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(k0, theta0),
                                   bounds=((0.1, 0.01), (np.inf, np.inf)),
                                   maxfev=10000)
        except Exception:
            raise RuntimeError("Gamma 拟合失败")
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)
        self.params = popt; self.pcov = pcov; self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, k, theta):
        return gammainc(k, x / theta)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = \frac{\gamma(k, x/\theta)}{\Gamma(k)}"

    def get_param_names(self):
        return ["k (shape)", "θ (scale)"]

    def get_description(self):
        return (
            "Gamma 分布可描述多阶段独立失效过程的累计时间。\n\n"
            "参数：k (形状), θ (尺度)\n\n"
            "适用：备用冗余系统、k 个独立指数过程的总和。"
        )
