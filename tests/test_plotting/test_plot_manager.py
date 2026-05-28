"""测试绘图管理器"""
import numpy as np
from plotting.plot_data import PlotSpec, SeriesPlotData, FitResult
from plotting.plot_manager import PlotManager


class TestPlotManager:
    def test_build_figure_empty(self):
        pm = PlotManager()
        spec = PlotSpec(title="Test", x_label="X", y_label="Y")
        fig = pm.build_figure(spec)
        assert fig is not None
        assert len(fig.axes) == 1
        pm.clear()

    def test_build_figure_with_series(self):
        pm = PlotManager()
        rng = np.random.default_rng(42)
        xs = np.sort(rng.weibull(1.5, size=50) * 50)
        cdf = np.linspace(0, 1, 50)

        series = SeriesPlotData(
            col_name="TestCol",
            group="A",
            marker="o",
            linestyle="-",
            color="blue",
            xs=xs,
            ys=cdf,
            fit_x=np.linspace(0, 200, 100),
            fit_y=np.linspace(0, 1, 100),
            r_squared=0.95,
            selector_idx=0,
        )

        spec = PlotSpec(
            title="Test Fit",
            x_label="Value",
            y_label="CDF",
            series_list=[series],
        )
        fig = pm.build_figure(spec)
        ax = fig.axes[0]
        assert ax.get_title() == "Test Fit"
        assert ax.get_xlabel() == "Value"
        assert ax.get_ylabel() == "CDF"
        pm.clear()

    def test_themes_list(self):
        themes = PlotManager.get_available_themes()
        assert "default" in themes
        assert "ggplot" in themes

    def test_apply_theme(self):
        pm = PlotManager()
        pm.apply_theme("ggplot")
        assert pm._current_theme == "ggplot"
        # 不应抛出异常
        pm.apply_theme("default")
