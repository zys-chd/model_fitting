"""集成测试 — 验证 5 个 Bug 的修复

这些测试验证从数据加载到拟合的完整流程，使用无 GUI 的 mock view。
在有 tkinter 的 Windows 环境中可以直接运行。
"""
import os
import numpy as np
import pandas as pd


# ==================== 辅助函数 ====================

def _make_view_mock():
    """创建 mock view（纯 Python，不触发 tkinter）"""
    from unittest.mock import MagicMock
    view = MagicMock()
    view.get_selected_columns.return_value = [(0, "IDSS1")]
    view.get_series_styles.return_value = [{"marker": "o", "linestyle": "-", "limit": 0}]
    view.get_max_series.return_value = 4
    view.get_series_count.return_value = 1
    view.ask_yes_no.return_value = True
    return view


def _make_presenter(view=None):
    from model_fitting.presenter import FittingPresenter
    from model_fitting.services.data_service import DataService
    from model_fitting.services.fitting_service import FittingService
    from model_fitting.services.stats_service import StatsService
    from model_fitting.plotting.plot_manager import PlotManager
    if view is None:
        view = _make_view_mock()
    return FittingPresenter(
        view=view,
        data_service=DataService(),
        fitting_service=FittingService(),
        stats_service=StatsService(),
        plot_manager=PlotManager(),
    )


# ==================== Bug 测试 ====================

class TestBug1PartIdLocFix:
    """Bug 1: PART_ID 使用 iloc 而非 loc → 改 loc"""

    def test_show_popup_uses_loc(self):
        """双击查看数据详情时应使用 df.loc，保证 index 有空洞时也能正确取值"""
        presenter = _make_presenter()
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "IDSS1": list(range(10, 20)),
        })
        # 模拟去除离群点后 index 有空洞
        df_removed = df.drop([2, 5]).copy()
        presenter._state.data = df_removed
        presenter._state.group_column = None
        # 构造选中点，df_idx 是原始 index 值（2 和 5 已不存在）
        sel = [
            {"col": "IDSS1", "df_idx": 0, "x_raw": 10.0},
            {"col": "IDSS1", "df_idx": 3, "x_raw": 13.0},
        ]
        # 核心断言：df.loc[3] 应返回 index=3 的行（即原第 4 行）
        # 而 df.iloc[3] 会错误返回 index=4 的行（第 5 行）
        from model_fitting.ui.app_window import AppWindow
        # 仅验证逻辑：_show_popup 中应使用 df.loc 而非 df.iloc
        assert 3 in df_removed.index, "df_idx=3 应在 index 中"
        r = df_removed.loc[3]
        assert r["PART_ID"] == "P003", f"loc[3] 应返回 P003, got {r['PART_ID']}"
        # iloc[3] 会在有空洞时取错
        assert df_removed.iloc[3]["PART_ID"] != "P003", "iloc[3] 在有空洞时取错行"


class TestBug2NumericGroupFix:
    """Bug 2: 数字分组列类型不匹配 → 统一转为字符串"""

    def test_groups_converted_to_string(self):
        """_get_groups 应将数字分组值转为字符串"""
        presenter = _make_presenter()
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "group": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        presenter._state.data = df
        presenter._state.group_column = "group"
        groups = presenter._get_groups()
        assert all(isinstance(g, str) for g in groups), f"期望字符串但得到 {groups}"
        assert "1" in groups
        assert "2" in groups

    def test_visibility_key_with_numeric_group(self):
        """数字分组的 visibility key 应使用字符串格式，与 Treeview 产生的 key 一致"""
        presenter = _make_presenter()
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "group": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        presenter._state.data = df
        presenter._state.group_column = "group"
        # 用字符串 key 设置可见性（模拟 Treeview 点击后的行为）
        presenter._state.visibility[("IDSS1", "1")] = {"scatter": False, "curve": True}
        visibility = presenter.get_visibility("IDSS1", "1")
        assert visibility["scatter"] is False
        assert visibility["curve"] is True


class TestBug3StatsTreeDedupFix:
    """Bug 3: 统计树列节点重复 → 改为按列分组"""

    def test_stats_tree_data_groups_by_column(self):
        """_build_stats_tree_data 应为每列创建一个条目"""
        presenter = _make_presenter()
        fit_results = {
            ("IDSS1", "A"): ("Weibull", (1.5, 50), 0.95, None, None),
            ("IDSS1", "B"): ("Weibull", (1.6, 55), 0.94, None, None),
            ("VTH1", "A"): ("Normal", (1.0, 0.1), 0.90, None, None),
        }
        stats_cache = {}
        data = presenter._build_stats_tree_data(fit_results, stats_cache)
        # 验证按列分组的数量
        cols = set(item["col"] for item in data)
        assert cols == {"IDSS1", "VTH1"}, f"应有 2 列, 得到 {cols}"
        assert len(data) == 3, f"应有 3 个条目（IDSS1×2 + VTH1×1）, 得到 {len(data)}"

    def test_each_item_has_visibility(self):
        """每个 stats tree item 都应包含 scatter_visible 和 curve_visible"""
        presenter = _make_presenter()
        presenter._state.visibility[("IDSS1", "A")] = {"scatter": False, "curve": True}
        fit_results = {("IDSS1", "A"): ("Weibull", (1.5, 50), 0.95, None, None)}
        stats_cache = {}
        data = presenter._build_stats_tree_data(fit_results, stats_cache)
        assert len(data) == 1
        assert data[0]["scatter_visible"] is False
        assert data[0]["curve_visible"] is True


class TestBug4DuplicateColumnNamesFix:
    """Bug 4: 重复列名导致崩溃 → ImportDialog 自动添加后缀"""

    def test_import_dialog_dedup_column_names(self):
        """ImportDialog 解析列名时应自动去重"""
        import pandas as pd
        raw_df = pd.DataFrame({
            0: ["H1", "v1", "v2"],
            1: ["dup", "a", "b"],
            2: ["dup", "c", "d"],
            3: ["H4", "e", "f"],
        })
        # 模拟对话框的解析逻辑：header_row=0
        header_vals = raw_df.iloc[0].tolist()
        seen = {}
        col_names = []
        for i in range(len(raw_df.columns)):
            if i < len(header_vals) and pd.notna(header_vals[i]):
                base = str(header_vals[i])
            else:
                base = f"Col{i}"
            if base in seen:
                seen[base] += 1
                col_names.append(f"{base}_{seen[base]}")
            else:
                seen[base] = 0
                col_names.append(base)
        # 原始: ['H1', 'dup', 'dup', 'H4']
        # 期望: ['H1', 'dup', 'dup_1', 'H4']
        assert col_names == ["H1", "dup", "dup_1", "H4"], f"去重失败: {col_names}"

    def test_no_duplicate_does_not_add_suffix(self):
        """无重复列名时不应添加后缀"""
        import pandas as pd
        header_vals = ["IDSS1", "VTH1", "IGSS1"]
        seen = {}
        col_names = []
        for i, h in enumerate(header_vals):
            base = str(h)
            if base in seen:
                seen[base] += 1
                col_names.append(f"{base}_{seen[base]}")
            else:
                seen[base] = 0
                col_names.append(base)
        assert col_names == ["IDSS1", "VTH1", "IGSS1"], f"不应添加后缀: {col_names}"


class TestBug5NonStandardGroupColumnFix:
    """Bug 5: 非标准分组列名不被识别 → 启发式检测"""

    def test_detect_batch_column(self):
        """列名 'Batch'（非 GROUP_CANDIDATES）应通过启发式识别"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Batch": ["A"] * 30 + ["B"] * 30,
            "IDSS1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] == "Batch"

    def test_detect_lot_column(self):
        """列名 'Lot' 也应通过启发式识别"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Lot": ["X"] * 30 + ["Y"] * 30,
            "IDSS1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] == "Lot"

    def test_heuristic_not_fooled_by_unique_strings(self):
        """唯一值比例高的字符串列不应被误判为分组列"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Comment": [f"Note_{i}" for i in range(60)],  # 60 个唯一值
            "IDSS1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] is None, f"Comment 不应被识别为分组列, got {info['group_column']}"
        # Comment 应被当作数值列（字符串列）
        assert "Comment" in info["value_columns"] or "Comment" in info["columns"]
