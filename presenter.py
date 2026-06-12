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
from config import SHOW_FIT_CURVE_DEFAULT
from config import COLOR_PALETTES, CYCLE_MARKERS, CYCLE_LINESTYLES

logger = logging.getLogger(__name__)

_MISSING = object()  # sentinel for "not provided" in _apply_data


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
        self.series_meta: list = []  # [{selector_idx, col, group, df_indices, ...}]
        self.visibility: dict = {}  # {(col, group): {"scatter": bool, "curve": bool}}
        self.removed_points: dict = {}  # {col: [df_index, ...]} 显式跟踪去除点
        self.color_palette: str = "tab10"
        self.quantile_low: float = 5.0
        self.quantile_high: float = 95.0


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
        self._series_plot_data_list: list = []  # 保存最新 series plot data，供无重建可见性更新使用

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

    def _apply_data(self, df: pd.DataFrame, force_group_col=_MISSING) -> None:
        """应用 DataFrame 到内部状态
        force_group_col: _MISSING=auto-detect, None=无分组, str=指定列
        """
        # original_data：仅在首次加载时设置，shift 过滤不覆盖
        if self._state.original_data is None:
            self._state.original_data = df.copy()

        # 先检测结构，再对 value 列做 shift 过滤
        info = self._data_service.detect_structure(df)

        if self._state.filter_shift_only and info["value_columns"]:
            keep_cols = set(info.get("id_columns", []))
            if info["group_column"]:
                keep_cols.add(info["group_column"])
            shifted = [c for c in info["value_columns"] if c.endswith("_shift")]
            keep_cols.update(shifted)
            df = df[[c for c in df.columns if c in keep_cols]]
            info = self._data_service.detect_structure(df)

        # 将数值列强制转换为 numeric
        for c in info["value_columns"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        self._state.data = df
        self._state.columns = info["columns"]

        if force_group_col is not _MISSING:
            self._state.group_column = force_group_col
        else:
            self._state.group_column = info["group_column"]

        if self._state.group_column:
            self._state.value_columns = [c for c in info["value_columns"] if c != self._state.group_column]
        else:
            self._state.value_columns = info["value_columns"]

        self._state.fit_results.clear()
        self._state.stats_cache.clear()
        self._state.visibility.clear()
        self._state.removed_points.clear()
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

    def set_quantile_low(self, q: float) -> None:
        self._state.quantile_low = q
        self.update_all()

    def set_quantile_high(self, q: float) -> None:
        self._state.quantile_high = q
        self.update_all()

    def set_x_scale(self, scale: str) -> None:
        self._state.x_scale = scale
        self._apply_scale_limits()

    def set_y_scale(self, scale: str) -> None:
        self._state.y_scale = scale
        self._apply_scale_limits()

    def set_theme(self, theme: str) -> None:
        self._state.theme = theme
        self._plot_manager.apply_theme(theme)
        self.update_all()

    def set_axis_limits(self, x_limits: tuple, y_limits: tuple) -> None:
        self._state.x_limits = x_limits
        self._state.y_limits = y_limits
        self._apply_scale_limits()

    def set_filter_shift_only(self, enabled: bool) -> None:
        self._state.filter_shift_only = enabled
        if self._state.original_data is not None:
            self._apply_data(self._state.original_data.copy())

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
        # 获取调色板颜色
        pal_entry = COLOR_PALETTES.get(self._state.color_palette, COLOR_PALETTES["tab10"])
        pal_colors = pal_entry["colors"]
        gcolors = {g: pal_colors[i % len(pal_colors)] for i, g in enumerate(groups)}

        all_fit_results = {}  # {(col, group): (model_name, params, r2, xs, cdf)}
        all_stats = {}
        series_plot_data_list = []
        fit_errors: list[str] = []
        self._state.series_meta = []

        for si, col_name in selected_columns:
            if not col_name or col_name not in self._state.data.columns:
                if col_name:
                    fit_errors.append(f"列 '{col_name}' 不在数据中")
                continue

            style = series_styles[si] if si < len(series_styles) else {}
            marker = style.get("marker", "o")
            linestyle = style.get("linestyle", "-")
            limit = style.get("limit", 0)
            scatter_alpha = style.get("scatter_alpha", 1.0)
            curve_alpha = style.get("curve_alpha", 1.0)
            marker_size = style.get("marker_size", 6)
            line_width = style.get("line_width", 2)
            cycle_marker = style.get("cycle_marker", True)
            cycle_linestyle = style.get("cycle_linestyle", True)
            custom_color = style.get("custom_color", "")

            if self._state.group_column:
                col_has_data = False
                for gi, g in enumerate(groups):
                    sub = self._state.data.loc[
                        self._state.data[self._state.group_column] == g, col_name
                    ].dropna()
                    if len(sub) < 3:
                        continue
                    col_has_data = True
                    try:
                        fit_result = self._fitting_service.fit_single(
                            sub.values,
                            self._state.current_model_key,
                            cdf_estimator_key=self._state.current_cdf_estimator_key,
                            transform_key=self._state.current_transform_key,
                        )
                    except Exception as e:
                        fit_errors.append(f"拟合失败 {col_name}[{g}]: {e}")
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
                        quantile_low=self._state.quantile_low,
                        quantile_high=self._state.quantile_high,
                    )
                    all_stats[key] = stats

                    # 拟合曲线范围
                    xmin, xmax = transform.get_fit_curve_xrange(fit_result.xs, limit)
                    fit_x = np.linspace(xmin, xmax, 200)
                    fit_y_raw = model.cdf(fit_x, fit_result.params)
                    fit_y = transform.transform(fit_y_raw)

                    # 循环解析 + 自定义多色
                    gm = CYCLE_MARKERS[gi % len(CYCLE_MARKERS)] if cycle_marker else marker
                    gls = CYCLE_LINESTYLES[gi % len(CYCLE_LINESTYLES)] if cycle_linestyle else linestyle
                    # 自定义颜色：支持 pipe 分隔的多色、单 hex、或调色板 key
                    if custom_color:
                        if "|" in custom_color:
                            cols = [c.strip() for c in custom_color.split("|") if c.strip()]
                            gcolor = cols[gi % len(cols)] if cols else gcolors[g]
                        elif custom_color.startswith("#"):
                            gcolor = custom_color
                        else:
                            cust_pal = COLOR_PALETTES.get(custom_color)
                            gcolor = cust_pal["colors"][0] if cust_pal else gcolors[g]
                    else:
                        gcolor = gcolors[g]

                    vis_entry = self._state.visibility.get(key, {
                        "scatter": True,
                        "curve": SHOW_FIT_CURVE_DEFAULT,
                    })
                    spd = SeriesPlotData(
                        col_name=col_name,
                        group=g,
                        marker=gm,
                        linestyle=gls,
                        color=gcolor,
                        xs=fit_result.xs,
                        ys=fit_result.y_transformed,
                        fit_x=fit_x,
                        fit_y=fit_y,
                        r_squared=fit_result.r_squared,
                        selector_idx=si,
                        samples=sub.values,
                        scatter_visible=vis_entry.get("scatter", True),
                        curve_visible=vis_entry.get("curve", SHOW_FIT_CURVE_DEFAULT),
                        scatter_alpha=scatter_alpha,
                        curve_alpha=curve_alpha,
                        marker_size=marker_size,
                        line_width=line_width,
                        group_index=gi,
                    )
                    series_plot_data_list.append(spd)

                    self._state.series_meta.append({
                        "col": col_name, "group": g, "selector_idx": si,
                        "color": gcolor, "marker": gm, "linestyle": gls,
                        "df_indices": sub.index.values,
                    })
                if not col_has_data:
                    fit_errors.append(f"列 '{col_name}' 在所有分组中有效数据均不足（需≥3个非空值）")
            else:
                sub = self._state.data[col_name].dropna()
                if len(sub) < 3:
                    fit_errors.append(f"列 '{col_name}' 有效数据不足（需≥3个非空值）")
                    continue
                try:
                    fit_result = self._fitting_service.fit_single(
                        sub.values,
                        self._state.current_model_key,
                        cdf_estimator_key=self._state.current_cdf_estimator_key,
                        transform_key=self._state.current_transform_key,
                    )
                except Exception as e:
                    fit_errors.append(f"拟合失败 {col_name}: {e}")
                    continue

                key = (col_name, "All")
                all_fit_results[key] = (
                    fit_result.model_name, fit_result.params,
                    fit_result.r_squared, fit_result.xs, fit_result.cdf_raw,
                )
                stats = self._stats_service.compute_all(
                    sub.values,
                    model=model, params=fit_result.params, limit=limit,
                    quantile_low=self._state.quantile_low,
                    quantile_high=self._state.quantile_high,
                )
                all_stats[key] = stats

                xmin, xmax = transform.get_fit_curve_xrange(fit_result.xs, limit)
                fit_x = np.linspace(xmin, xmax, 200)
                fit_y_raw = model.cdf(fit_x, fit_result.params)
                fit_y = transform.transform(fit_y_raw)

                vis_entry = self._state.visibility.get(key, {
                    "scatter": True,
                    "curve": SHOW_FIT_CURVE_DEFAULT,
                })
                gcolor = custom_color if custom_color else gcolors.get("All", "blue")
                # 如果 custom_color 是 pipe 分隔的多色或 hex，解析为颜色值
                if custom_color:
                    if "|" in custom_color:
                        cols = [c.strip() for c in custom_color.split("|") if c.strip()]
                        gcolor = cols[0] if cols else gcolors.get("All", "blue")
                    elif not custom_color.startswith("#"):
                        cust_pal = COLOR_PALETTES.get(custom_color)
                        gcolor = cust_pal["colors"][0] if cust_pal else gcolors.get("All", "blue")
                spd = SeriesPlotData(
                    col_name=col_name,
                    group=None,
                    marker=marker,
                    linestyle=linestyle,
                    color=gcolor,
                    xs=fit_result.xs,
                    ys=fit_result.y_transformed,
                    fit_x=fit_x,
                    fit_y=fit_y,
                    r_squared=fit_result.r_squared,
                    selector_idx=si,
                    samples=sub.values,
                    scatter_visible=vis_entry.get("scatter", True),
                    curve_visible=vis_entry.get("curve", SHOW_FIT_CURVE_DEFAULT),
                    scatter_alpha=scatter_alpha,
                    curve_alpha=curve_alpha,
                    marker_size=marker_size,
                    line_width=line_width,
                )
                series_plot_data_list.append(spd)

                self._state.series_meta.append({
                    "col": col_name, "group": "All", "selector_idx": si,
                    "color": gcolor, "marker": marker, "linestyle": linestyle,
                    "df_indices": sub.index.values,
                })

        self._state.fit_results = all_fit_results
        self._state.stats_cache = all_stats

        # 报告拟合异常（一次弹窗汇总所有错误）
        if fit_errors:
            self._view.show_fit_errors(fit_errors)

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
        self._series_plot_data_list = series_plot_data_list
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
            return sorted(str(v) for v in raw)
        return ["All"]

    def _build_stats_tree_data(self, fit_results, stats_cache) -> list:
        """构建统计树数据（供 View 渲染），含散点/曲线分离可见性"""
        data = []
        try:
            model = self._fitting_service.get_model(self._state.current_model_key)
        except Exception:
            return data

        for (col, grp), (mn, params, r2, xs, cdf) in sorted(fit_results.items()):
            stats = stats_cache.get((col, grp), {})
            vis_entry = self._state.visibility.get((col, grp), {
                "scatter": True,
                "curve": SHOW_FIT_CURVE_DEFAULT,
            })
            item = {
                "col": col,
                "group": grp,
                "model_name": mn,
                "scatter_visible": vis_entry.get("scatter", True),
                "curve_visible": vis_entry.get("curve", SHOW_FIT_CURVE_DEFAULT),
                "visible": vis_entry.get("scatter", True) and vis_entry.get("curve", SHOW_FIT_CURVE_DEFAULT),
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
            vis_entry = self._state.visibility.get(key, {"scatter": True, "curve": True})
            if not vis_entry.get("scatter", True) and not vis_entry.get("curve", True):
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
                    for idx in drop_indices:
                        self._state.removed_points.setdefault(col, []).append(idx)
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
                self._state.removed_points.setdefault(col, []).append(df_idx)

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
            self._state.removed_points.clear()
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

    def _apply_scale_limits(self) -> None:
        """仅更新轴刻度和范围，不重建画布"""
        figure = self._plot_manager._current_figure
        if figure is None:
            return
        self._plot_manager.apply_scale_limits(
            figure, self._state.x_scale, self._state.y_scale,
            self._state.x_limits, self._state.y_limits,
        )

    def apply_visibility(self) -> None:
        """仅更新可见性和图例，不重建画布、不重新拟合"""
        # 先同步 _series_plot_data_list 中的 visible 标记到最新 _state.visibility
        self._update_series_plot_data_visibility()
        figure = self._plot_manager._current_figure
        if figure is None or not self._series_plot_data_list:
            return
        self._plot_manager.apply_visibility(figure, self._series_plot_data_list)
        # 重建 stats tree（也需要反映可见性变化）
        self._view.display_stats(self._build_stats_tree_data(
            self._state.fit_results, self._state.stats_cache))

    def apply_series_styles(self) -> None:
        """轻量样式更新：就地修改 artist 属性，不重新拟合

        适用于 marker/线型/透明度/大小/线宽 的变更。
        如果 limit 变了（影响统计），调用方应改用 update_all()。
        """
        # 1. 从 View 读最新样式
        series_styles = self._view.get_series_styles()
        # 构建 selector_idx → style 映射
        style_by_si = {si: s for si, s in enumerate(series_styles)}
        # 2. 更新 _series_plot_data_list 中的样式字段（用 selector_idx + group_index 匹配）
        for spd in self._series_plot_data_list:
            style = style_by_si.get(spd.selector_idx, {})
            gi = spd.group_index

            # 循环解析
            if style.get("cycle_marker", True):
                spd.marker = CYCLE_MARKERS[gi % len(CYCLE_MARKERS)]
            else:
                spd.marker = style.get("marker", spd.marker)
            if style.get("cycle_linestyle", True):
                spd.linestyle = CYCLE_LINESTYLES[gi % len(CYCLE_LINESTYLES)]
            else:
                spd.linestyle = style.get("linestyle", spd.linestyle)

            spd.scatter_alpha = style.get("scatter_alpha", spd.scatter_alpha)
            spd.curve_alpha = style.get("curve_alpha", spd.curve_alpha)
            spd.marker_size = style.get("marker_size", spd.marker_size)
            spd.line_width = style.get("line_width", spd.line_width)

            # 颜色
            custom_color = style.get("custom_color", "")
            if custom_color:
                if "|" in custom_color:
                    cols = [c.strip() for c in custom_color.split("|") if c.strip()]
                    if cols:
                        spd.color = cols[spd.group_index % len(cols)]
                elif custom_color.startswith("#"):
                    spd.color = custom_color
                else:
                    cust_pal = COLOR_PALETTES.get(custom_color)
                    if cust_pal:
                        spd.color = cust_pal["colors"][0]
        # 3. 就地更新 artist
        figure = self._plot_manager._current_figure
        if figure is None:
            return
        self._plot_manager.apply_styles(figure, self._series_plot_data_list)

    def toggle_visibility(self, col: str, group: str) -> None:
        """切换整体可见性（散点 + 曲线同步）"""
        key = (col, group)
        entry = dict(self._state.visibility.get(key, {
            "scatter": True,
            "curve": SHOW_FIT_CURVE_DEFAULT,
        }))
        new_vis = not (entry.get("scatter", True) and entry.get("curve", SHOW_FIT_CURVE_DEFAULT))
        entry["scatter"] = new_vis
        entry["curve"] = new_vis
        self._state.visibility[key] = entry
        self.apply_visibility()

    def toggle_column_visibility(self, col: str) -> None:
        """切换整列可见性"""
        # 从 _series_plot_data_list 收集该列的所有 (col, group) key
        # 这样即使 _state.visibility 还未初始化（首次加载），也能正确获取应有 key 集合
        keys = list(set(
            (spd.col_name, spd.group or "All")
            for spd in self._series_plot_data_list
            if spd.col_name == col
        ))
        # 兜底：如果 _series_plot_data_list 为空，从 _state.visibility 中取
        if not keys:
            keys = [k for k in self._state.visibility if k[0] == col]
        if not keys:
            return
        all_scat = all(self._state.visibility.get(k, {}).get("scatter", True) for k in keys)
        all_curv = all(self._state.visibility.get(k, {}).get("curve", SHOW_FIT_CURVE_DEFAULT) for k in keys)
        new_vis = not (all_scat and all_curv)
        for k in keys:
            self._state.visibility[k] = {"scatter": new_vis, "curve": new_vis}
        self.apply_visibility()

    def toggle_scatter_visibility(self, col: str, group: str) -> None:
        """切换散点可见性"""
        key = (col, group)
        entry = dict(self._state.visibility.get(key, {
            "scatter": True,
            "curve": SHOW_FIT_CURVE_DEFAULT,
        }))
        entry["scatter"] = not entry.get("scatter", True)
        # 如果关闭散点且曲线也关闭，保持数据一致
        if not entry["scatter"] and not entry["curve"]:
            pass
        self._state.visibility[key] = entry
        self._update_series_plot_data_visibility()
        self.apply_visibility()

    def toggle_curve_visibility(self, col: str, group: str) -> None:
        """切换拟合曲线可见性"""
        key = (col, group)
        entry = dict(self._state.visibility.get(key, {
            "scatter": True,
            "curve": SHOW_FIT_CURVE_DEFAULT,
        }))
        entry["curve"] = not entry.get("curve", SHOW_FIT_CURVE_DEFAULT)
        self._state.visibility[key] = entry
        self._update_series_plot_data_visibility()
        self.apply_visibility()

    def _update_series_plot_data_visibility(self) -> None:
        """同步 series_plot_data_list 中的 visible 标记到最新 state"""
        for spd in self._series_plot_data_list:
            key = (spd.col_name, spd.group or "All")
            entry = self._state.visibility.get(key, {})
            spd.scatter_visible = entry.get("scatter", True)
            spd.curve_visible = entry.get("curve", SHOW_FIT_CURVE_DEFAULT)

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

    def get_visibility(self, col: str, group: str) -> dict:
        """返回 {scatter: bool, curve: bool}"""
        return dict(self._state.visibility.get((col, group), {
            "scatter": True,
            "curve": SHOW_FIT_CURVE_DEFAULT,
        }))

    def get_available_models(self) -> list[str]:
        return self._fitting_service.get_model_keys()

    def get_available_transforms(self) -> dict:
        return self._fitting_service.get_available_transforms()

    def get_available_outlier_detectors(self) -> dict:
        from services.outlier_registry import OUTLIER_REGISTRY
        return dict(OUTLIER_REGISTRY)

    # ==================== 会话保存/加载 ====================

    def save_session(self, path: str) -> None:
        """保存当前会话到 .rda 文件"""
        if self._state.data is None:
            self._view.show_error("保存失败", "没有可保存的数据")
            return
        from services.session_service import SessionService

        # 收集 View 层配置（系列选择、样式）
        series_config = self._view.get_series_config()

        # 收集 Presenter 状态
        state = {
            "model_key": self._state.current_model_key,
            "transform_key": self._state.current_transform_key,
            "cdf_estimator_key": self._state.current_cdf_estimator_key,
            "outlier_key": self._state.current_outlier_key,
            "x_scale": self._state.x_scale,
            "y_scale": self._state.y_scale,
            "theme": self._state.theme,
            "x_limits": list(self._state.x_limits),
            "y_limits": list(self._state.y_limits),
            "filter_shift_only": self._state.filter_shift_only,
            "visibility": {str(k): v for k, v in self._state.visibility.items()},
            "series_config": series_config,
        }

        try:
            SessionService.save(
                path,
                original_df=self._state.original_data if self._state.original_data is not None else self._state.data,
                state=state,
                removed_points=self._state.removed_points,
            )
            self._view.show_info("保存成功", f"会话已保存至：\n{path}")
        except Exception as e:
            self._view.show_error("保存失败", str(e))

    def load_session(self, path: str) -> None:
        """加载 .rda 会话文件"""
        from services.session_service import SessionService

        try:
            result = SessionService.load(path)
        except Exception as e:
            self._view.show_error("加载失败", str(e))
            return

        df = result["dataframe"]
        state = result.get("state", {})

        # 恢复配置
        self._state.current_model_key = state.get("model_key", "Weibull")
        self._state.current_transform_key = state.get("transform_key", "cdf")
        self._state.current_cdf_estimator_key = state.get("cdf_estimator_key", "median_rank")
        self._state.current_outlier_key = state.get("outlier_key", "mad")
        self._state.x_scale = state.get("x_scale", "线性")
        self._state.y_scale = state.get("y_scale", "线性")
        self._state.theme = state.get("theme", "default")
        xl = state.get("x_limits", [None, None])
        yl = state.get("y_limits", [None, None])
        self._state.x_limits = (xl[0] if xl else None, xl[1] if len(xl) > 1 else None)
        self._state.y_limits = (yl[0] if yl else None, yl[1] if len(yl) > 1 else None)
        self._state.filter_shift_only = state.get("filter_shift_only", False)

        # 恢复 theme PlotManager
        self._plot_manager.apply_theme(self._state.theme)

        # 恢复去除点
        removed = result.get("removed_points", {})
        for col, indices in removed.items():
            if col in df.columns:
                for idx in indices:
                    if idx in df.index:
                        df.loc[idx, col] = np.nan
        self._state.removed_points = removed

        # 应用数据（会清除 visibility/series_meta/fit_results）
        self._state.original_data = df.copy()
        self._apply_data(df)

        # ---- 以下恢复必须在 _apply_data 之后（因为 _apply_data 会清除状态） ----

        # 恢复可见性
        vis_raw = state.get("visibility", {})
        for k_str, v in vis_raw.items():
            try:
                key = eval(k_str)
                self._state.visibility[key] = v
            except Exception:
                pass

        # 恢复系列配置（View 层：选择器数量、列选择、样式）
        series_config = state.get("series_config", [])
        if series_config:
            self._view.restore_series_config(series_config)

        # 同步 View 控件
        self._view.sync_controls_from_state(state)

        # 使用恢复后的选择器 + 可见性重新绘图
        self.update_all()

    # ==================== 附加数据 + 自定义导入 ====================

    def append_file(self, path: str) -> None:
        """附加数据文件到当前数据集"""
        if self._state.data is None:
            self._view.show_error("错误", "请先加载主数据文件")
            return
        try:
            combined = self._data_service.append_file(self._state.data, path)
            self._apply_data(combined)
        except Exception as e:
            logger.error("附加文件失败: %s", e)
            self._view.show_error("附加错误", str(e))

    def import_custom_data(self, path: str) -> None:
        """自定义读取：弹出导入对话框，用户配置后加载"""
        try:
            raw_df = self._data_service.load_raw(path)
        except Exception as e:
            self._view.show_error("读取错误", str(e))
            return

        from ui.widgets.import_dialog import ImportDialog
        parent = self._view if hasattr(self._view, 'winfo_toplevel') else None
        dlg = ImportDialog(parent, raw_df, path)
        if parent:
            parent.wait_window(dlg)
        else:
            dlg.wait_window()

        if dlg.result_df is not None:
            self._apply_data(dlg.result_df,
                             force_group_col=getattr(dlg, '_result_group_col', _MISSING))

    def append_custom_data(self, path: str) -> None:
        """自定义附加：弹导入对话框配置后，拼接到现有数据"""
        if self._state.data is None:
            self._view.show_error("错误", "请先加载主数据文件")
            return
        try:
            raw_df = self._data_service.load_raw(path)
        except Exception as e:
            self._view.show_error("读取错误", str(e))
            return

        from ui.widgets.import_dialog import ImportDialog
        parent = self._view if hasattr(self._view, 'winfo_toplevel') else None
        dlg = ImportDialog(parent, raw_df, path)
        if parent:
            parent.wait_window(dlg)
        else:
            dlg.wait_window()

        if dlg.result_df is not None:
            # 列取并集，缺失填 NaN，纵向拼接
            existing = self._state.data
            all_cols = list(existing.columns) + [c for c in dlg.result_df.columns if c not in existing.columns]
            combined = pd.concat(
                [existing.reindex(columns=all_cols), dlg.result_df.reindex(columns=all_cols)],
                ignore_index=True,
            )
            self._apply_data(combined,
                             force_group_col=getattr(dlg, '_result_group_col', _MISSING))
