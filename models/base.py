"""
分布模型抽象基类
所有分布模型必须继承此类并实现 fit / cdf / get_formula / get_param_names
"""
from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class DistributionModel(ABC):
    """分布模型基类 — 抽象基类"""

    KEY: str = ""  # 子类必须定义，如 "Weibull"

    def __init__(self, name: str):
        self.name = name
        self.params = None
        self.pcov = None
        self.r_squared = None

    @abstractmethod
    def fit(self, samples, cdf_estimator=None):
        """
        拟合模型到样本数据。

        Parameters
        ----------
        samples : array-like
            原始样本数据
        cdf_estimator : CDFEstimator, optional
            经验 CDF 估计器，默认为 None 时内部使用 prepare_cdf_data

        Returns
        -------
        (params, pcov, r_squared, xs, cdf)
        """
        ...

    @abstractmethod
    def cdf(self, x, params):
        """计算 x 处的累积分布函数值"""
        ...

    @abstractmethod
    def get_formula(self):
        """返回 LaTeX 公式字符串"""
        ...

    @abstractmethod
    def get_param_names(self):
        """返回参数名列表"""
        ...

    def get_description(self) -> str:
        """返回模型介绍文本（可选重写）"""
        return ""

    @staticmethod
    def compute_r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """计算 R² 决定系数"""
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        return float(1 - (ss_res / ss_tot)) if ss_tot != 0 else 0.0

    @staticmethod
    def prepare_cdf_data(samples) -> tuple:
        """从样本数据计算经验 CDF（中位秩 (i-0.3)/(N+0.4)）"""
        xs = np.sort(np.asarray(samples))
        n = len(xs)
        cdf = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        return xs, cdf
