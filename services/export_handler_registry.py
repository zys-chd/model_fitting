"""
导出格式处理器 — ABC + 内置实现 + 注册表

新增参数导出格式：
    1. 继承 ExportHandler，实现 KEY / EXTENSIONS / FORMAT_NAME / export
    2. 在 EXPORT_REGISTRY 中注册
"""
from abc import ABC, abstractmethod
from typing import ClassVar
import pandas as pd


class ExportHandler(ABC):
    """拟合参数导出处理器抽象基类"""

    KEY: ClassVar[str] = ""
    EXTENSIONS: ClassVar[list[str]] = []
    FORMAT_NAME: ClassVar[str] = ""

    @abstractmethod
    def export(
        self,
        path: str,
        fit_results: dict,
        models: dict,
        stats_cache: dict,
        **kwargs,
    ) -> None:
        """
        将拟合结果导出到文件。

        Parameters
        ----------
        path : str
            输出文件路径
        fit_results : dict
            {(col, group): (model_name, params, r2, xs, cdf)}
        models : dict
            {model_key: DistributionModel}
        stats_cache : dict
            {(col, group): {metric_name: value}}
        """
        ...


def _build_rows(fit_results: dict, models: dict, stats_cache: dict, visible_stats=None) -> list[dict]:
    """构建导出用的行数据（Excel / CSV / JSON 共用）"""
    rows = []
    # 统计列名白名单 (None=全部)
    stat_filter = visible_stats if visible_stats else None

    for (col, grp), (mn, params, r2, xs, cdf) in sorted(fit_results.items()):
        model = models.get(mn)
        if model is None:
            continue
        st = stats_cache.get((col, grp), {})

        # 找到动态分位数键名
        q_keys = [k for k in st if "%分位数" in k]
        q_low = st.get(q_keys[0], 0) if len(q_keys) > 0 else 0
        q_high = st.get(q_keys[1], 0) if len(q_keys) > 1 else 0

        def _val(key, default=0):
            if stat_filter and key not in stat_filter:
                return None  # None = 不导出此列
            return st.get(key, default)

        row = {
            "Column": col,
            "Group": grp,
            "Model": mn,
            "R_squared": f"{r2:.6f}",
            "Sample_Count": len(xs),
        }
        def _add(k, v):
            if v is not None:
                row[k] = f"{v:.6g}"

        _add("Mean", _val("均值"))
        _add("Std", _val("标准差"))
        _add("Median", _val("中位数"))
        _add("Quantile_Low", _val(q_keys[0], q_low) if q_keys else None)
        _add("Quantile_High", _val(q_keys[1], q_high) if len(q_keys)>1 else None)
        _add("IQR", _val("分位数间距"))
        _add("Rel_IQR", _val("相对分位数间距"))
        _add("Min", _val("最小值"))
        _add("Max", _val("最大值"))
        _add("Skewness", _val("偏度"))
        _add("CV_pct", _val("变异系数(%)"))
        _add("F_at_limit", _val("limit处F值") if isinstance(st.get("limit处F值"), (int,float)) else None)

        for pn, pv in zip(model.get_param_names(), params):
            row[pn.replace(" ", "_")] = f"{pv:.6g}"
        rows.append(row)
    return rows


# ============================================================
# 内置实现
# ============================================================

class CSVExportHandler(ExportHandler):
    """CSV 导出"""

    KEY: ClassVar[str] = "csv"
    EXTENSIONS: ClassVar[list[str]] = [".csv"]
    FORMAT_NAME: ClassVar[str] = "CSV"

    def export(self, path, fit_results, models, stats_cache, **kwargs):
        vs = kwargs.pop("visible_stats", None)
        rows = _build_rows(fit_results, models, stats_cache, visible_stats=vs)
        pd.DataFrame(rows).to_csv(path, index=False, **kwargs)


class JSONExportHandler(ExportHandler):
    """JSON 导出"""

    KEY: ClassVar[str] = "json"
    EXTENSIONS: ClassVar[list[str]] = [".json"]
    FORMAT_NAME: ClassVar[str] = "JSON"

    def export(self, path, fit_results, models, stats_cache, **kwargs):
        vs = kwargs.pop("visible_stats", None)
        rows = _build_rows(fit_results, models, stats_cache, visible_stats=vs)
        pd.DataFrame(rows).to_json(
            path, orient="records", force_ascii=False, indent=2, **kwargs
        )


class ExcelExportHandler(ExportHandler):
    """Excel 导出"""

    KEY: ClassVar[str] = "excel"
    EXTENSIONS: ClassVar[list[str]] = [".xlsx"]
    FORMAT_NAME: ClassVar[str] = "Excel"

    def export(self, path, fit_results, models, stats_cache, **kwargs):
        vs = kwargs.pop("visible_stats", None)
        rows = _build_rows(fit_results, models, stats_cache, visible_stats=vs)
        pd.DataFrame(rows).to_excel(path, index=False, **kwargs)


# ============================================================
# 注册表
# ============================================================

EXPORT_REGISTRY: dict[str, ExportHandler] = {
    "csv": CSVExportHandler(),
    "json": JSONExportHandler(),
    "excel": ExcelExportHandler(),
}


def get_export_handler(key: str) -> ExportHandler:
    """通过 key 获取导出处理器"""
    if key not in EXPORT_REGISTRY:
        raise KeyError(f"未知导出格式: {key}，可用: {list(EXPORT_REGISTRY.keys())}")
    return EXPORT_REGISTRY[key]


def get_all_export_handlers() -> dict[str, ExportHandler]:
    """返回所有已注册的导出处理器"""
    return dict(EXPORT_REGISTRY)
