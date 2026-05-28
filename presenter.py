"""
MVP Presenter — 核心协调器（纯 Python，零 GUI 依赖）

协调 View（UI 层）与 Model（services 层）之间的所有交互。
"""
import logging
from typing import Optional, Any
import numpy as np
import pandas as pd

from services.data_service import DataService
from services.fitting_service import FittingService, FitResult as SvcFitResult
from services.stats_service import StatsService
from services.export_service import ExportService
from services.transform_registry import TransformStrategy
from services.cdf_estimator_registry import CDFEstimator
from services.outlier_registry import OutlierDetector
from services.file_handler_registry import FileFormatRegistry
from plotting.plot_data import PlotSpec, SeriesPlotData, FitResult as PlotFitResult
from plotting.plot_manager import PlotManager

logger = logging.getLogger(__name__)


class AppState:
    """Presenter 内部应用状态"""
    def __init__(self):
        self.data: Optional[pd.DataFrame] = None
        self.original_data: Optional[pd.DataFrame] = None
        self.columns: list[str] = []
        self.value_columns: list[str] = []
        self.group_column: Optional[str] = None
        self.current_model_key: str = "Weibull"
        self.current_transform_key: str = "cdf"
        self.current_cdf_estimator_key: str = "median_rank"
        self.current_outlier_key: str = "mad"
        self.x_scale: str = "线性"
        self.y_scale: str = "线性"
        self.theme: str = "default"
        self.x_limits: tuple = (None, None)
        self.y_limits: tuple = (None, None)
        self.filter_shift_only: bool = False
        self.fit_results: dict = {}
        self.stats_cache: dict = {}
        self.series_meta: list = []  # [{selector_idx, col, group, ...}]
        self.visibility: dict = {}  # {(col, group): True/False}


class FittingPresenter:
    """
    MVP Presenter — View 与 Service 之间的协调器。

    所有方法供 View 层调用，所有结果通过 View 推送到界面。
    Presenter 不导入 tkinter / matplotlib.backends。
    """

    def __init__(
        self,
        view,  # AppViewProtocol
        data_service: Optional[DataService] = None,
        fitting_service: Optional[FittingService] = None,
        stats_service: Optional[StatsService] = None,
        plot_manager: Optional[PlotManager] = None,
        export_service: Optional[ExportService] = None,
    ):
        self._view = view
        self._data_service = data_service or DataService()
        self._fitting_service = fitting_service or FittingService()
        self._stats_service = stats_service or StatsService()
        self._plot_manager = plot_manager or PlotManager()
        self._export_service = export_service or ExportService()
        self._state = AppState()

    # ==================== 数据加载 ====================

    def load_file(self, path: str) -> None:
        """加载数据文件"""
        try:
            df = self._data_service.load_file(path)
            self._apply_data(df)
        except Exception as e:
            logger.error("加载文件失败: %s", e)
            self._view.show_error("加载错误", str(e))

    def load_dataframe(self, df: pd.DataFrame) -> None:
        """直接加载 DataFrame"""
        try:
            df = self._data_service.load_dataframe(df)
            self._apply_data(df)
        except Exception as e:
            logger.error("加载 DataFrame 失败: %s", e)
            self._view.show_error("加载错误", str(e))

    def generate_test_data(self) -> None:
        """生成并加载测试数据"""
        try:
            path = self._data_service.get_default_test_path()
            self._data_service.generate_test_data(path)
            self.load_file(path)
        except Exception as e:
            logger.error("生成测试数据失败: %s", e)
            self._view.show_error("生成错误", str(e))

    def _apply_data(self, df: pd.DataFrame) -> None:
        """应用 DataFrame 到内部状态"""
        if self._state.filter_shift_only:
            df = self._data_service.filter_shift_only(df)
        info = self._data_service.detect_structure(df)
        self._state.data = df
        self._state.original_data = df.copy()
        self._state.columns = info["columns"]
        self._state.group_column = info["group_column"]
        self._state.value_columns = info["value_columns"]
        self._state.fit_results.clear()
        self._state.stats_cache.clear()
        self._state.visibility.clear()
        self._state.series_meta.clear()
        self._view.update_series_columns(self._state.value_columns)
        logger.info(
            "数据加载: %d 行, %d 列, value_columns=%s, group_column=%s",
            len(df), len(df.columns), self._state.value_columns, self._state.group_column,
        )
        self.update_all()

    # ==================== 设置方法 ====================

    def set_model(self, model_key: str) -> None:
        self._state.current_model_key = model_key
        self.update_all()

    def set_transform(self, transform_key: str) -> None:
        self._state.current_transform_key = transform_key
        self.update_all()

    def set_cdf_estimator(self, key: str) -> None:
        self._state.current_cdf_estimator_key = key
        self.update_all()

    def set_outlier_detector(self, key: str) -> None:
        self._state.current_outlier_key = key

    def set_x_scale(self, scale: str) -> None:
        self._state.x_scale = scale
        self.update_all()

    def set_y_scale(self, scale: str) -> None:
        self._state.y_scale = scale
        self.update_all()

    def set_theme(self, theme: str) -> None:
        self._state.theme = theme
        self._plot_manager.apply_theme(theme)
        self.update_all()

    def set_axis_limits(self, x_limits: tuple, y_limits: tuple) -> None:
        self._state.x_limits = x_limits
        self._state.y_limits = y_limits
        self.update_all()

    def set_filter_shift_only(self, enabled: bool) -> None:
        self._state.filter_shift_only = enabled

    # ==================== 核心：update_all ====================

    def update_all(self) -> None:
        """
        核心方法 — 从 View 收集配置 → 拟合 → 绘图 → 推送 View。

        这是整个 MVP 数据流的中枢。
        """
        if self._state.data is None:
            return

        # 1. 从 View 收集配置
        selected_columns = self._view.get_selected_columns()       # [(idx, col_name), ...]
        series_styles = self._view.get_series_styles()             # [{marker, linestyle, limit}, ...]

        # 2. 确定分组
        groups = self._get_groups()

        # 3. 获取策略实例
        model = self._fitting_service.get_model(self._state.current_model_key)
        transform = self._fitting_service.get_transform(self._state.current_transform_key)

        # 4. 拟合 + 统计
        import matplotlib.pyplot as plt
        gcolors = {g: plt.cm.tab10(i % 10) for i, g in enumerate(groups)}

        all_fit_results = {}  # {(col, group): (model_name, params, r2, xs, cdf)}
        all_stats = {}
        series_plot_data_list = []
        self._state.series_meta = []

        for si, col_name in selected_columns:
            if not col_name or col_name not in self._state.data.columns:
                continue

            style = series_styles[si] if si < len(series_styles) else {}
            marker = style.get("marker", "o")
            linestyle = style.get("linestyle", "-")
            limit = style.get("limit", 0)

            if self._state.group_column:
                for g in groups:
                    sub = self._state.data.loc[
                        self._state.data[self._state.group_column] == g, col_name
                    ].dropna()
                    if len(sub) < 3:
                        continue
                    try:
                        fit_result = self._fitting_service.fit_single(
                            sub.values,
                            self._state.current_model_key,
                            cdf_estimator_key=self._state.current_cdf_estimator_key,
                            transform_key=self._state.current_transform_key,
                        )
                    except Exception as e:
                        logger.warning("拟合失败 %s[%s]: %s", col_name, g, e)
                        continue

                    # 存储拟合结果
                    key = (col_name, g)
                    all_fit_results[key] = (
                        fit_result.model_name, fit_result.params,
                        fit_result.r_squared, fit_result.xs, fit_result.cdf_raw,
                    )

                    # 统计量
                    stats = self._stats_service.compute_all(
                        sub.values,
                        model=model, params=fit_result.params, limit=limit,
                    )
                    all_stats[key] = stats

                    # 拟合曲线范围
                    xmin, xmax = transform.get_fit_curve_xrange(fit_result.xs, limit)
                    fit_x = np.linspace(xmin, xmax, 200)
                    fit_y_raw = model.cdf(fit_x, fit_result.params)
                    fit_y = transform.transform(fit_y_raw)

                    spd = SeriesPlotData(
                        col_name=col_name,
                        group=g,
                        marker=marker,
                        linestyle=linestyle,
                        color=gcolors[g],
                        xs=fit_result.xs,
                        ys=fit_result.y_transformed,
                        fit_x=fit_x,
                        fit_y=fit_y,
                        r_squared=fit_result.r_squared,
                        selector_idx=si,
                        samples=sub.values,
                    )
                    series_plot_data_list.append(spd)

                    self._state.series_meta.append({
                        "col": col_name, "group": g, "selector_idx": si,
                        "color": gcolors[g], "marker": marker, "linestyle": linestyle,
                    })
            else:
                sub = self._state.data[col_name].dropna()
                if len(sub) < 3:
                    continue
                try:
                    fit_result = self._fitting_service.fit_single(
                        sub.values,
                        self._state.current_model_key,
                        cdf_estimator_key=self._state.current_cdf_estimator_key,
                        transform_key=self._state.current_transform_key,
                    )
                except Exception as e:
                    logger.warning("拟合失败 %s: %s", col_name, e)
                    continue

                key = (col_name, "All")
                all_fit_results[key] = (
                    fit_result.model_name, fit_result.params,
                    fit_result.r_squared, fit_result.xs, fit_result.cdf_raw,
                )
                stats = self._stats_service.compute_all(
                    sub.values,
                    model=model, params=fit_result.params, limit=limit,
                )
                all_stats[key] = stats

                xmin, xmax = transform.get_fit_curve_xrange(fit_result.xs, limit)
                fit_x = np.linspace(xmin, xmax, 200)
                fit_y_raw = model.cdf(fit_x, fit_result.params)
                fit_y = transform.transform(fit_y_raw)

                spd = SeriesPlotData(
                    col_name=col_name,
                    group=None,
                    marker=marker,
                    linestyle=linestyle,
                    color=gcolors.get("All", "blue"),
                    xs=fit_result.xs,
                    ys=fit_result.y_transformed,
                    fit_x=fit_x,
                    fit_y=fit_y,
                    r_squared=fit_result.r_squared,
                    selector_idx=si,
                    samples=sub.values,
                )
                series_plot_data_list.append(spd)

                self._state.series_meta.append({
                    "col": col_name, "group": "All", "selector_idx": si,
                    "color": gcolors.get("All", "blue"), "marker": marker, "linestyle": linestyle,
                })

        self._state.fit_results = all_fit_results
        self._state.stats_cache = all_stats

        # 5. 构建 PlotSpec
        scale_map = {"线性": "linear", "对数": "log"}
        plot_spec = PlotSpec(
            title=f"{self._state.current_model_key} Distribution Fit",
            x_label="",
            y_label=transform.get_ylabel(),
            x_scale=scale_map.get(self._state.x_scale, self._state.x_scale),
            y_scale=scale_map.get(self._state.y_scale, self._state.y_scale),
            x_limits=self._state.x_limits,
            y_limits=self._state.y_limits,
            series_list=series_plot_data_list,
            groups=groups,
        )

        # 6. 构建 Figure
        figure = self._plot_manager.build_figure(plot_spec)

        # 7. 推送到 View
        self._view.display_plot(figure)
        self._view.display_formula(model.get_formula())
        self._view.display_stats(self._build_stats_tree_data(all_fit_results, all_stats))

    def _get_groups(self) -> list[str]:
        if self._state.data is None:
            return ["All"]
        if self._state.group_column:
            raw = self._state.data[self._state.group_column].dropna().unique()
            return sorted(raw)
        return ["All"]

    def _build_stats_tree_data(self, fit_results, stats_cache) -> list:
        """构建统计树数据（供 View 渲染）"""
        data = []
        try:
            model = self._fitting_service.get_model(self._state.current_model_key)
        except Exception:
            return data

        for (col, grp), (mn, params, r2, xs, cdf) in sorted(fit_results.items()):
            stats = stats_cache.get((col, grp), {})
            vis = self._state.visibility.get((col, grp), True)
            item = {
                "col": col,
                "group": grp,
                "model_name": mn,
                "visible": vis,
                "params": list(zip(model.get_param_names(), params)),
                "r_squared": r2,
                "stats": stats,
            }
            data.append(item)
        return data

    # ==================== 离群点操作 ====================

    def auto_remove_outliers(self, selector_idx: int, col: str) -> int:
        """
        自动检测并去除离群点。

        Returns
        -------
        int
            去除的离群点数量
        """
        if self._state.data is None:
            return 0
        if self._state.original_data is None:
            self._state.original_data = self._state.data.copy()

        cnt = 0
        for meta in self._state.series_meta:
            if meta["selector_idx"] != selector_idx or meta.get("col") != col:
                continue
            key = (col, meta.get("group", "All"))
            if not self._state.visibility.get(key, True):
                continue

            samples = self._state.data.loc[
                self._state.data[self._state.group_column] == meta["group"], col
            ].dropna() if self._state.group_column and meta.get("group") else self._state.data[col].dropna()

            try:
                mask = self._fitting_service.detect_outliers(
                    samples.values,
                    self._state.current_model_key,
                    outlier_key=self._state.current_outlier_key,
                    cdf_estimator_key=self._state.current_cdf_estimator_key,
                )
                if mask.any():
                    drop_indices = samples.index[mask]
                    self._state.data.loc[drop_indices, col] = np.nan
                    cnt += int(mask.sum())
            except Exception as e:
                logger.debug("自动去除拟合失败: %s", e)
                continue

        if cnt > 0:
            self._state.fit_results.clear()
            self._state.stats_cache.clear()
            self.update_all()
        return cnt

    def manual_remove_points(self, points: list[dict]) -> None:
        """手动去除选中的数据点"""
        if self._state.data is None:
            return
        if self._state.original_data is None:
            self._state.original_data = self._state.data.copy()

        for pt in points:
            df_idx = pt.get("df_idx")
            col = pt.get("col")
            if df_idx is not None and col:
                self._state.data.loc[df_idx, col] = np.nan

        self._state.fit_results.clear()
        self._state.stats_cache.clear()
        self.update_all()

    def restore_data(self) -> None:
        """恢复原始数据"""
        if self._state.original_data is not None:
            self._state.data = self._state.original_data.copy()
            self._state.original_data = None
            self._state.fit_results.clear()
            self._state.stats_cache.clear()
            self.update_all()

    # ==================== 导出 ====================

    def export_image(self, path: str, **kwargs) -> None:
        fig = self._plot_manager._current_figure
        if fig is None:
            self._view.show_error("导出", "没有可导出的图表")
            return
        try:
            self._export_service.export_figure(fig, path, **kwargs)
            self._view.show_info("导出", f"图表已保存至：\n{path}")
        except Exception as e:
            self._view.show_error("导出错误", str(e))

    def export_parameters(self, path: str) -> None:
        if not self._state.fit_results:
            self._view.show_error("导出", "没有可导出的拟合结果")
            return
        try:
            models = self._fitting_service.get_available_models()
            self._export_service.export_parameters(
                path, self._state.fit_results, models, self._state.stats_cache,
            )
            self._view.show_info("导出", f"参数已保存至：\n{path}")
        except Exception as e:
            self._view.show_error("导出错误", str(e))

    # ==================== 可见性 ====================

    def toggle_visibility(self, col: str, group: str) -> None:
        key = (col, group)
        vis = not self._state.visibility.get(key, True)
        self._state.visibility[key] = vis
        self.update_all()

    def toggle_column_visibility(self, col: str) -> None:
        # 收集该列所有分组
        keys = [k for k in self._state.visibility if k[0] == col]
        if not keys:
            return
        all_vis = all(self._state.visibility.get(k, True) for k in keys)
        new_vis = not all_vis
        for k in keys:
            self._state.visibility[k] = new_vis
        self.update_all()

    # ==================== 查询方法 ====================

    def get_formula(self) -> str:
        try:
            model = self._fitting_service.get_model(self._state.current_model_key)
            return model.get_formula()
        except Exception:
            return ""

    def get_dataframe(self) -> Optional[pd.DataFrame]:
        return self._state.data

    def get_fit_results(self) -> dict:
        return dict(self._state.fit_results)

    def get_series_meta(self) -> list:
        return list(self._state.series_meta)

    def get_visibility(self, col: str, group: str) -> bool:
        return self._state.visibility.get((col, group), True)

    def get_available_models(self) -> list[str]:
        return self._fitting_service.get_model_keys()

    def get_available_transforms(self) -> dict:
        return self._fitting_service.get_available_transforms()

    def get_available_outlier_detectors(self) -> dict:
        from services.outlier_registry import OUTLIER_REGISTRY
        return dict(OUTLIER_REGISTRY)
