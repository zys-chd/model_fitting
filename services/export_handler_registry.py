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


def _build_rows(fit_results: dict, models: dict, stats_cache: dict) -> list[dict]:
    """构建导出用的行数据（Excel / CSV / JSON 共用）"""
    rows = []
    for (col, grp), (mn, params, r2, xs, cdf) in sorted(fit_results.items()):
        model = models.get(mn)
        if model is None:
            continue
        st = stats_cache.get((col, grp), {})

        # 找到动态分位数键名
        q_keys = [k for k in st if "%分位数" in k]
        q_low = st.get(q_keys[0], 0) if len(q_keys) > 0 else 0
        q_high = st.get(q_keys[1], 0) if len(q_keys) > 1 else 0

        row = {
            "Column": col,
            "Group": grp,
            "Model": mn,
            "R_squared": f"{r2:.6f}",
            "Sample_Count": len(xs),
            "Mean": f'{st.get("均值", 0):.6g}',
            "Std": f'{st.get("标准差", 0):.6g}',
            "Median": f'{st.get("中位数", 0):.6g}',
            "Quantile_Low": f'{q_low:.6g}',
            "Quantile_High": f'{q_high:.6g}',
            "Skewness": f'{st.get("偏度", 0):.6g}',
            "CV_pct": f'{st.get("变异系数(%)", 0):.6g}',
            "F_at_limit": f'{v:.6g}'
            if isinstance((v := st.get("limit处F值")), (int, float))
            else "",
        }
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
        rows = _build_rows(fit_results, models, stats_cache)
        pd.DataFrame(rows).to_csv(path, index=False, **kwargs)


class JSONExportHandler(ExportHandler):
    """JSON 导出"""

    KEY: ClassVar[str] = "json"
    EXTENSIONS: ClassVar[list[str]] = [".json"]
    FORMAT_NAME: ClassVar[str] = "JSON"

    def export(self, path, fit_results, models, stats_cache, **kwargs):
        rows = _build_rows(fit_results, models, stats_cache)
        pd.DataFrame(rows).to_json(
            path, orient="records", force_ascii=False, indent=2, **kwargs
        )


class ExcelExportHandler(ExportHandler):
    """Excel 导出"""

    KEY: ClassVar[str] = "excel"
    EXTENSIONS: ClassVar[list[str]] = [".xlsx"]
    FORMAT_NAME: ClassVar[str] = "Excel"

    def export(self, path, fit_results, models, stats_cache, **kwargs):
        rows = _build_rows(fit_results, models, stats_cache)
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
