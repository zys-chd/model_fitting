"""
plotting 包 — 纯绘图层（依赖 matplotlib，不依赖 tkinter）
"""
from .plot_data import FitResult, SeriesPlotData, PlotSpec
from .plot_manager import PlotManager

__all__ = ["FitResult", "SeriesPlotData", "PlotSpec", "PlotManager"]
