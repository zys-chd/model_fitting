"""
绘图数据类 — 纯数据结构，不含逻辑
"""
from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np


@dataclass
class FitResult:
    """单次拟合结果（用于跨层传递）"""
    model_name: str
    params: tuple
    pcov: Any = None
    r_squared: float = 0.0
    xs: Optional[np.ndarray] = None
    cdf_raw: Optional[np.ndarray] = None
    y_transformed: Optional[np.ndarray] = None
    n_samples: int = 0


@dataclass
class SeriesPlotData:
    """单条数据系列的绘图数据"""
    col_name: str
    group: Optional[str]
    marker: str
    linestyle: str
    color: Any
    xs: np.ndarray          # 散点 x
    ys: np.ndarray          # 散点 y
    fit_x: np.ndarray       # 拟合曲线 x
    fit_y: np.ndarray       # 拟合曲线 y
    r_squared: float
    selector_idx: int
    df_indices: Optional[np.ndarray] = None
    samples: Optional[np.ndarray] = None
    # 独立控制散点与拟合曲线可见性
    scatter_visible: bool = True
    curve_visible: bool = True


@dataclass
class PlotSpec:
    """完整绘图的规格说明"""
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    x_scale: str = "linear"
    y_scale: str = "linear"
    x_limits: tuple = (None, None)
    y_limits: tuple = (None, None)
    series_list: list[SeriesPlotData] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    draw_limit_lines: bool = False
