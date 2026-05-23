"""
Birnbaum-Saunders（疲劳寿命）分布模型
F(x) = Φ((1/α) * (√(x/β) - √(β/x)))
参数: α (shape), β (scale)
"""
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm

try:
    from .base import DistributionModel
except ImportError:
    from base import DistributionModel


class BirnbaumSaundersModel(DistributionModel):
    """Birnbaum-Saunders 分布拟合模型 — 参数 α, β"""

    KEY = "BirnbaumSaunders"

    def __init__(self):
        super().__init__(self.KEY)

    def fit(self, samples):
        x = np.asarray(samples)
        x = x[x > 0]
        if len(x) < 3:
            raise RuntimeError("样本量不足")
        xs, cdf = self.prepare_cdf_data(x)
        beta0 = np.mean(xs)
        alpha0 = max(np.std(xs) / beta0, 0.1)
        try:
            popt, pcov = curve_fit(self._cdf_func, xs, cdf,
                                   p0=(alpha0, beta0),
                                   bounds=((0.01, 0.01), (np.inf, np.inf)),
                                   maxfev=10000)
        except Exception:
            raise RuntimeError("Birnbaum-Saunders 拟合失败")
        y_pred = self._cdf_func(xs, *popt)
        r_squared = self.compute_r_squared(cdf, y_pred)
        self.params = popt; self.pcov = pcov; self.r_squared = r_squared
        return popt, pcov, r_squared, xs, cdf

    @staticmethod
    def _cdf_func(x, alpha, beta):
        z = (np.sqrt(x / beta) - np.sqrt(beta / np.maximum(x, 1e-12))) / alpha
        return norm.cdf(z)

    def cdf(self, x, params):
        return self._cdf_func(x, *params)

    def get_formula(self):
        return r"F(x) = \Phi\left(\frac{1}{\alpha}\left[\sqrt{\frac{x}{\beta}} - \sqrt{\frac{\beta}{x}}\right]\right)"

    def get_param_names(self):
        return ["α (shape)", "β (scale)"]

    def get_description(self):
        return (
            "Birnbaum-Saunders 专门用于疲劳裂纹扩展建模。\n\n"
            "参数：α (形状), β (尺度)\n\n"
            "适用：金属疲劳寿命、周期性应力导致的累积损伤。"
        )
