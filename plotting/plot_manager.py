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
        """绘制单个数据系列：散点 + 拟合曲线（分别受可见性控制）"""
        # 散点
        if series.scatter_visible:
            scat = ax.scatter(
                series.xs, series.ys,
                alpha=series.scatter_alpha,
                s=series.marker_size ** 2,
                color=series.color,
                edgecolor="none",
                picker=5,
                marker=series.marker,
            )
        else:
            scat = ax.scatter(
                series.xs, series.ys,
                alpha=series.scatter_alpha,
                s=series.marker_size ** 2,
                color=series.color,
                edgecolor="none",
                picker=5,
                marker=series.marker,
                visible=False,
            )
        series.scatter_artist = scat
        # 拟合曲线
        if series.curve_visible:
            line, = ax.plot(
                series.fit_x, series.fit_y,
                color=series.color,
                linestyle=series.linestyle,
                alpha=series.curve_alpha,
                linewidth=series.line_width,
            )
        else:
            line, = ax.plot(
                series.fit_x, series.fit_y,
                color=series.color,
                linestyle=series.linestyle,
                alpha=series.curve_alpha,
                linewidth=series.line_width,
                visible=False,
            )
        series.line_artist = line

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

    def apply_visibility(self, fig: Figure, series_list: list[SeriesPlotData]) -> None:
        """无重建的可见性更新：直接修改现有 figure 上的 artist 可见性 + 重建图例

        不销毁画布、不重新拟合、不创建新 Figure，仅跳变图例和可见性。
        """
        if not fig or not fig.axes:
            return
        ax = fig.axes[0]

        # 1. 更新各系列的 scatter / line artist 可见性
        for series in series_list:
            if series.scatter_artist is not None:
                series.scatter_artist.set_visible(series.scatter_visible)
            if series.line_artist is not None:
                series.line_artist.set_visible(series.curve_visible)

        # 2. 重建图例
        old_legend = ax.get_legend()
        if old_legend:
            old_legend.remove()

        from matplotlib.lines import Line2D
        handles = []
        col_done = set()
        for series in series_list:
            if series.col_name not in col_done:
                col_done.add(series.col_name)
                col_all_hidden = all(
                    not s.scatter_visible and not s.curve_visible
                    for s in series_list if s.col_name == series.col_name
                )
                handles.append(
                    Line2D([0], [0], marker=series.marker, color="#444444",
                           linestyle=series.linestyle,
                           label=f"— {series.col_name} —",
                           markersize=series.marker_size + 2, linewidth=2,
                           alpha=0.15 if col_all_hidden else 1.0)
                )
            gtxt = series.group or ""
            # 图例条目三态模式：根据散点/曲线独立可见性控制 marker 和 linestyle
            both_vis = series.scatter_visible and series.curve_visible
            neither_vis = not series.scatter_visible and not series.curve_visible
            if both_vis:
                mk, ls, al = series.marker, series.linestyle, 1.0
            elif neither_vis:
                mk, ls, al = series.marker, '', 0.15  # 淡出
            elif not series.scatter_visible and series.curve_visible:
                mk, ls, al = '', series.linestyle, 1.0  # 仅曲线（无点标记）
            else:  # scatter_visible and not curve_visible
                mk, ls, al = series.marker, '', 1.0     # 仅散点（无线条）
            handles.append(
                Line2D([0], [0], marker=mk, color=series.color,
                       linestyle=ls,
                       label=f"  {gtxt}  R²={series.r_squared:.4f}",
                       markersize=series.marker_size, linewidth=series.line_width,
                       alpha=al)
            )
        if handles:
            ax.legend(handles=handles, loc="best", fontsize=9,
                      framealpha=0.9, handlelength=4.0)

        fig.canvas.draw_idle()

    def apply_styles(self, fig: Figure, series_list: list[SeriesPlotData]) -> None:
        """就地更新样式属性（marker、alpha、大小、线型、线宽），不重建画布

        仅修改现有 artist 的属性 + 重建图例，不重新拟合、不创建新 Figure。
        适用场景：marker 类型/大小、线型/线宽、透明度 变更。
        """
        if not fig or not fig.axes:
            return
        ax = fig.axes[0]
        needs_redraw = False

        for series in series_list:
            if series.scatter_artist is not None:
                try:
                    series.scatter_artist.set_marker(series.marker)
                    series.scatter_artist.set_sizes([series.marker_size ** 2])
                    series.scatter_artist.set_alpha(series.scatter_alpha)
                    series.scatter_artist.set_color(series.color)
                except Exception:
                    pass
                needs_redraw = True
            if series.line_artist is not None:
                try:
                    series.line_artist.set_linestyle(series.linestyle)
                    series.line_artist.set_linewidth(series.line_width)
                    series.line_artist.set_alpha(series.curve_alpha)
                    series.line_artist.set_color(series.color)
                except Exception:
                    pass
                needs_redraw = True

        # 重建图例（反映新的 marker/line 样式和尺寸）
        if needs_redraw:
            old_legend = ax.get_legend()
            if old_legend:
                old_legend.remove()
            from matplotlib.lines import Line2D
            handles = []
            col_done = set()
            for series in series_list:
                if series.col_name not in col_done:
                    col_done.add(series.col_name)
                    col_all_hidden = all(
                        not s.scatter_visible and not s.curve_visible
                        for s in series_list if s.col_name == series.col_name
                    )
                    handles.append(
                        Line2D([0], [0], marker=series.marker, color="#444444",
                               linestyle=series.linestyle,
                               label=f"— {series.col_name} —",
                               markersize=series.marker_size + 2, linewidth=2,
                               alpha=0.15 if col_all_hidden else 1.0)
                    )
                gtxt = series.group or ""
                both_vis = series.scatter_visible and series.curve_visible
                neither_vis = not series.scatter_visible and not series.curve_visible
                if both_vis:
                    mk, ls, al = series.marker, series.linestyle, 1.0
                elif neither_vis:
                    mk, ls, al = series.marker, '', 0.15
                elif not series.scatter_visible and series.curve_visible:
                    mk, ls, al = '', series.linestyle, 1.0
                else:
                    mk, ls, al = series.marker, '', 1.0
                handles.append(
                    Line2D([0], [0], marker=mk, color=series.color,
                           linestyle=ls,
                           label=f"  {gtxt}  R²={series.r_squared:.4f}",
                           markersize=series.marker_size, linewidth=series.line_width,
                           alpha=al)
                )
            if handles:
                ax.legend(handles=handles, loc="best", fontsize=9,
                          framealpha=0.9, handlelength=4.0)
            fig.canvas.draw_idle()

    def apply_scale_limits(self, fig: Figure, x_scale: str, y_scale: str,
                           x_limits: tuple, y_limits: tuple) -> None:
        """就地更新轴的刻度和范围，不重建画布"""
        if not fig or not fig.axes:
            return
        ax = fig.axes[0]
        scale_map = {"线性": "linear", "对数": "log"}
        ax.set_xscale(scale_map.get(x_scale, x_scale))
        ax.set_yscale(scale_map.get(y_scale, y_scale))
        # 更新范围
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
        fig.canvas.draw_idle()

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
        """根据 PlotSpec 构建图例（区分散点/曲线可见性）"""
        from matplotlib.lines import Line2D

        handles = []
        col_done = set()
        for series in plot_spec.series_list:
            # 列标题
            if series.col_name not in col_done:
                col_done.add(series.col_name)
                col_all_hidden = all(
                    not s.scatter_visible and not s.curve_visible
                    for s in plot_spec.series_list
                    if s.col_name == series.col_name
                )
                handles.append(
                    Line2D(
                        [0], [0],
                        marker=series.marker,
                        color="#444444",
                        linestyle=series.linestyle,
                        label=f"— {series.col_name} —",
                        markersize=series.marker_size + 2,
                        linewidth=2,
                        alpha=0.15 if col_all_hidden else 1.0,
                    )
                )
            # 分组条目 — 三态模式：根据散点/曲线独立可见性控制显示
            gtxt = series.group or ""
            both_vis = series.scatter_visible and series.curve_visible
            neither_vis = not series.scatter_visible and not series.curve_visible
            if both_vis:
                mk, ls, al = series.marker, series.linestyle, 1.0
            elif neither_vis:
                mk, ls, al = series.marker, '', 0.15  # 淡出
            elif not series.scatter_visible and series.curve_visible:
                mk, ls, al = '', series.linestyle, 1.0  # 仅曲线（无点标记）
            else:  # scatter_visible and not curve_visible
                mk, ls, al = series.marker, '', 1.0     # 仅散点（无线条）
            handles.append(
                Line2D(
                    [0], [0],
                    marker=mk,
                    color=series.color,
                    linestyle=ls,
                    label=f"  {gtxt}  R²={series.r_squared:.4f}",
                    markersize=series.marker_size,
                    linewidth=series.line_width,
                    alpha=al,
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
