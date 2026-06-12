"""测试 Presenter 可见性逻辑 — 使用 mock view，不依赖 tkinter"""
import numpy as np
import pandas as pd


class TestPresenterVisibility:
    """测试可见性 toggle 逻辑（Bug 2 修复 + 无重建优化验证）"""

    @staticmethod
    def _make_presenter():
        """创建 Presenter 实例（使用 mock view）"""
        from unittest.mock import MagicMock
        from model_fitting.presenter import FittingPresenter
        from model_fitting.services.data_service import DataService
        from model_fitting.services.fitting_service import FittingService
        from model_fitting.services.stats_service import StatsService
        from model_fitting.plotting.plot_manager import PlotManager

        view = MagicMock()
        view.get_selected_columns.return_value = [(0, "IDSS1")]
        view.get_series_styles.return_value = [{"marker": "o", "linestyle": "-", "limit": 0}]
        view.get_max_series.return_value = 4
        view.get_series_count.return_value = 1
        view.ask_yes_no.return_value = True

        presenter = FittingPresenter(
            view=view,
            data_service=DataService(),
            fitting_service=FittingService(),
            stats_service=StatsService(),
            plot_manager=PlotManager(),
        )
        return presenter, view

    def test_initial_visibility_state(self):
        """初始状态下可见性应为空字典"""
        presenter, view = self._make_presenter()
        assert presenter._state.visibility == {}

    def test_toggle_visibility(self):
        """toggle_visibility 应切换整体可见性"""
        presenter, view = self._make_presenter()
        key = ("IDSS1", "All")
        presenter._state.visibility[key] = {"scatter": True, "curve": True}
        presenter.toggle_visibility("IDSS1", "All")
        entry = presenter._state.visibility[key]
        assert entry["scatter"] is False
        assert entry["curve"] is False
        # 再次切换
        presenter.toggle_visibility("IDSS1", "All")
        entry = presenter._state.visibility[key]
        assert entry["scatter"] is True
        assert entry["curve"] is True

    def test_toggle_scatter_visibility(self):
        """toggle_scatter_visibility 应仅切换散点"""
        presenter, view = self._make_presenter()
        key = ("IDSS1", "All")
        presenter._state.visibility[key] = {"scatter": True, "curve": True}
        presenter.toggle_scatter_visibility("IDSS1", "All")
        entry = presenter._state.visibility[key]
        assert entry["scatter"] is False
        assert entry["curve"] is True  # 曲线不变

    def test_toggle_curve_visibility(self):
        """toggle_curve_visibility 应仅切换曲线"""
        presenter, view = self._make_presenter()
        key = ("IDSS1", "All")
        presenter._state.visibility[key] = {"scatter": True, "curve": True}
        presenter.toggle_curve_visibility("IDSS1", "All")
        entry = presenter._state.visibility[key]
        assert entry["scatter"] is True  # 散点不变
        assert entry["curve"] is False

    def test_toggle_column_visibility(self):
        """toggle_column_visibility 应切换整列所有分组"""
        presenter, view = self._make_presenter()
        presenter._state.visibility = {
            ("IDSS1", "A"): {"scatter": True, "curve": True},
            ("IDSS1", "B"): {"scatter": True, "curve": True},
        }
        presenter.toggle_column_visibility("IDSS1")
        assert presenter._state.visibility[("IDSS1", "A")] == {"scatter": False, "curve": False}
        assert presenter._state.visibility[("IDSS1", "B")] == {"scatter": False, "curve": False}

    def test_apply_visibility_no_figure(self):
        """apply_visibility 在没有 figure 时应安全返回"""
        presenter, view = self._make_presenter()
        presenter._plot_manager._current_figure = None
        # 不应抛出异常
        presenter.apply_visibility()

    def test_build_stats_tree_data(self):
        """_build_stats_tree_data 应正确包含可见性信息"""
        presenter, view = self._make_presenter()
        presenter._state.visibility = {
            ("IDSS1", "All"): {"scatter": False, "curve": True},
        }
        fit_results = {("IDSS1", "All"): ("Weibull", (1.5, 50), 0.95, None, None)}
        stats_cache = {("IDSS1", "All"): {"count": 10, "mean": 1.0}}
        data = presenter._build_stats_tree_data(fit_results, stats_cache)
        assert len(data) == 1
        item = data[0]
        assert item["col"] == "IDSS1"
        assert item["group"] == "All"
        assert item["scatter_visible"] is False
        assert item["curve_visible"] is True
        assert item["r_squared"] == 0.95

    def test_groups_as_strings(self):
        """_get_groups 应返回字符串，即使原始数据是数字（Bug 2 修复）"""
        presenter, view = self._make_presenter()
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "group": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        presenter._state.data = df
        presenter._state.group_column = "group"
        groups = presenter._get_groups()
        assert all(isinstance(g, str) for g in groups), f"groups should be str, got {groups}"
        assert groups == ["1", "2"]


class TestPresenterScaleLimits:
    """测试轴刻度和范围的就地更新"""

    @staticmethod
    def _make_presenter():
        from unittest.mock import MagicMock
        from model_fitting.presenter import FittingPresenter
        from model_fitting.services.data_service import DataService
        from model_fitting.services.fitting_service import FittingService
        from model_fitting.services.stats_service import StatsService
        from model_fitting.plotting.plot_manager import PlotManager

        view = MagicMock()
        presenter = FittingPresenter(
            view=view,
            data_service=DataService(),
            fitting_service=FittingService(),
            stats_service=StatsService(),
            plot_manager=PlotManager(),
        )
        return presenter, view

    def test_set_x_scale_stores_value(self):
        """set_x_scale 应更新 state 而不调用 update_all"""
        presenter, view = self._make_presenter()
        presenter.set_x_scale("对数")
        assert presenter._state.x_scale == "对数"

    def test_set_y_scale_stores_value(self):
        presenter, view = self._make_presenter()
        presenter.set_y_scale("对数")
        assert presenter._state.y_scale == "对数"

    def test_set_axis_limits_stores_values(self):
        presenter, view = self._make_presenter()
        presenter.set_axis_limits((0, 100), (None, None))
        assert presenter._state.x_limits == (0, 100)
