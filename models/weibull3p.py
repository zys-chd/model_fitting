"""
Weibull-3P（威布尔三参数）分布模型
F(x) = 1 - exp(-((x-γ)/η)^β)
参数: β (shape), η (scale), γ (location)
"""
import numpy as np
from scipy.optimize import curve_fit

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class Weibull3PModel(DistributionModel):
    """Weibull 三参数分布拟合模型 — 参数 β, η, γ"""

    KEY = "Weibull3P"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 5:
            raise RuntimeError("样本量不足，无法拟合 Weibull-3P 分布")

        xs, cdf = self.prepare_cdf_data(x)
        xmin = xs.min()
        gamma0 = max(xmin * 0.8, 0.001)
        beta0, eta0 = 1.5, np.mean(xs - gamma0) if np.mean(xs - gamma0) > 0 else np.mean(xs)

        try:
            popt, pcov = curve_fit(
                self._cdf_func, xs, cdf,
                p0=(beta0, eta0, gamma0),
                bounds=((0.1, 0.01, -np.inf), (20, np.inf, xmin - 1e-12)),
                maxfev=50000,
            )
        except Exception:
            raise RuntimeError("Weibull-3P 拟合失败")

        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)

        self.params = popt
        self.pcov = pcov
        self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, beta, eta, gamma):
        t = np.maximum((x - gamma) / eta, 0)
        return 1 - np.exp(-t ** beta)

    def cdf(self, x, params):
        beta, eta, gamma = params
        return self._cdf_func(x, beta, eta, gamma)

    def get_formula(self):
        return r"F(x) = 1 - \exp\left(-\left(\frac{x - \gamma}{\eta}\right)^{\beta}\right)"

    def get_param_names(self):
        return ["β (shape)", "η (scale)", "γ (location)"]

    def get_description(self):
        return (
            "Weibull-3P 在两参数基础上增加位置参数 γ。\n\n"
            "参数：β (形状), η (尺度), γ (位置/阈值)\n"
            "　　　γ — 最小寿命值，x<γ 时失效概率为 0\n\n"
            "适用：存在明确最小寿命阈值的情况，如轴承最小运行时间。"
        )
