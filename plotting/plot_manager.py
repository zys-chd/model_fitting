"""
PlotManager — matplotlib 绘图管理（不依赖 tkinter）

接收 PlotSpec，返回 matplotlib Figure。
"""
import logging
from typing import Optional
import matplotlib
matplotlib.use("Agg")  # 非交互后端，测试安全
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np

from .plot_data import PlotSpec, SeriesPlotData

logger = logging.getLogger(__name__)


# 绘图颜色（与旧 config.COLORS 一致）
_COLORS = plt.cm.tab10(np.linspace(0, 1, 10))


class PlotManager:
    """matplotlib 绘图管理器 — 纯绘图逻辑"""

    def __init__(self):
        self._current_figure: Optional[Figure] = None
        self._current_theme: str = "default"

    # ---- 核心方法 ----

    def build_figure(self, plot_spec: PlotSpec) -> Figure:
        """
        根据 PlotSpec 构建完整的 matplotlib Figure。

        Parameters
        ----------
        plot_spec : PlotSpec

        Returns
        -------
        matplotlib.figure.Figure
        """
        fig = Figure(figsize=(10, 6), dpi=100)
        ax = fig.add_subplot(111)

        # 绘制每个系列
        for series in plot_spec.series_list:
            self._draw_series(ax, series)

        # 轴配置
        ax.set_xlabel(plot_spec.x_label, fontsize=12)
        ax.set_ylabel(plot_spec.y_label, fontsize=12)
        ax.set_title(plot_spec.title, fontsize=14, fontweight="bold")
        ax.set_xscale(plot_spec.x_scale)
        ax.set_yscale(plot_spec.y_scale)
        self._apply_axis_limits(ax, plot_spec.x_limits, plot_spec.y_limits)
        self._apply_sci_formatter(ax)
        ax.grid(True, alpha=0.3)

        # 图例
        self._build_legend(ax, plot_spec)

        fig.tight_layout()
        self._current_figure = fig
        return fig

    def _draw_series(self, ax, series: SeriesPlotData):
        """绘制单个数据系列：散点 + 拟合曲线"""
        # 散点
        ax.scatter(
            series.xs, series.ys,
            alpha=0.6, s=40,
            color=series.color,
            edgecolor="none",
            picker=5,
            marker=series.marker,
        )
        # 拟合曲线
        ax.plot(
            series.fit_x, series.fit_y,
            color=series.color,
            linestyle=series.linestyle,
            alpha=0.8,
            linewidth=2,
        )

    def draw_limit_lines(self, ax, plot_spec: PlotSpec):
        """在图上绘制 limit 竖线"""
        seen_selectors = set()
        for series in plot_spec.series_list:
            if series.selector_idx in seen_selectors:
                continue
            seen_selectors.add(series.selector_idx)
            # limit 需要从外部传入，这里简化处理
            # 完整逻辑由 Presenter 调用时传入 limit_values
            pass

    # ---- 主题 ----

    def apply_theme(self, theme_name: str):
        """切换 matplotlib 样式主题"""
        self._current_theme = theme_name
        try:
            if theme_name == "default":
                plt.style.use("default")
            else:
                plt.style.use(theme_name)
        except Exception as e:
            logger.warning("应用主题失败 %s: %s", theme_name, e)

    @staticmethod
    def get_available_themes() -> list[str]:
        """返回可用主题列表"""
        return [
            "default",
            "ggplot",
            "seaborn-v0_8",
            "bmh",
            "fivethirtyeight",
            "dark_background",
            "classic",
        ]

    # ---- 清理 ----

    def clear(self):
        """关闭当前 figure，释放内存"""
        if self._current_figure:
            plt.close(self._current_figure)
            self._current_figure = None

    # ---- 内部辅助 ----

    @staticmethod
    def _apply_axis_limits(ax, x_limits, y_limits):
        xl, xr = x_limits
        yb, yt = y_limits
        try:
            if xl is not None:
                ax.set_xlim(left=float(xl))
            if xr is not None:
                ax.set_xlim(right=float(xr))
            if yb is not None:
                ax.set_ylim(bottom=float(yb))
            if yt is not None:
                ax.set_ylim(top=float(yt))
        except (ValueError, TypeError):
            pass

    @staticmethod
    def _apply_sci_formatter(ax):
        """为 x/y 轴应用科学计数法格式化器"""
        from matplotlib.ticker import FuncFormatter

        def _sci_fmt(v, _):
            if v == 0:
                return "0"
            exp = int(np.floor(np.log10(abs(v))))
            mant = v / 10 ** exp
            if abs(exp) <= 1:
                return f"{v:#.4g}"
            return f"{mant:.2f}e{exp:+d}"

        ax.xaxis.set_major_formatter(FuncFormatter(_sci_fmt))
        ax.yaxis.set_major_formatter(FuncFormatter(_sci_fmt))

    @staticmethod
    def _build_legend(ax, plot_spec: PlotSpec):
        """根据 PlotSpec 构建图例"""
        from matplotlib.lines import Line2D

        handles = []
        col_done = set()
        for series in plot_spec.series_list:
            if series.col_name not in col_done:
                col_done.add(series.col_name)
                handles.append(
                    Line2D(
                        [0], [0],
                        marker=series.marker,
                        color="#444444",
                        linestyle=series.linestyle,
                        label=f"— {series.col_name} —",
                        markersize=8,
                        linewidth=2,
                    )
                )
            gtxt = series.group or ""
            handles.append(
                Line2D(
                    [0], [0],
                    marker=series.marker,
                    color=series.color,
                    linestyle=series.linestyle,
                    label=f"  {gtxt}  R²={series.r_squared:.4f}",
                    markersize=6,
                    linewidth=2,
                )
            )
        if handles:
            ax.legend(
                handles=handles,
                loc="best",
                fontsize=9,
                framealpha=0.9,
                handlelength=4.0,
            )
