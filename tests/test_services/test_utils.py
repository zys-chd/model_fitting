"""测试工具函数：detect_columns, filter_columns_keep_shift_only"""
import numpy as np
import pandas as pd


class TestDetectColumns:
    """测试 detect_columns 列检测函数（含 Bug 5 修复验证）"""

    def test_standard_group_column(self):
        """标准分组列名 'group' 应被识别"""
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "group": ["A"] * 5 + ["B"] * 5,
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        from model_fitting.utils import detect_columns
        info = detect_columns(df)
        assert info["group_column"] == "group"
        assert "PART_ID" in info["id_columns"]
        assert "IDSS1" in info["value_columns"]

    def test_variant_group_names_exact_match(self):
        """GROUP_CANDIDATES 中的变体名（'Group', '组', '分组'）应被识别"""
        from model_fitting.utils import detect_columns
        for name in ["Group", "GROUP", "组", "分组"]:
            df = pd.DataFrame({
                "PART_ID": [f"P{i:03d}" for i in range(10)],
                name: ["A"] * 5 + ["B"] * 5,
                "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
            })
            info = detect_columns(df)
            assert info["group_column"] == name, f"未识别分组列名: {name}"

    def test_non_standard_group_name_heuristic(self):
        """非标准分组列名 'Batch' 应通过启发式检测识别（Bug 5 修复）"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Batch": ["A"] * 30 + ["B"] * 30,  # 非标准名，非数值，唯一值少
            "IDSS1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] == "Batch", f"启发式检测未识别 Batch, got {info['group_column']}"

    def test_lot_column_heuristic(self):
        """'Lot' 列也应通过启发式检测识别"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Lot": ["LotA"] * 30 + ["LotB"] * 30,
            "VTH1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] == "Lot", f"启发式检测未识别 Lot, got {info['group_column']}"

    def test_numeric_like_string_group_no_heuristic(self):
        """全数字字符串列但有大量唯一值不应误判为分组列"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(60)],
            "Code": [f"X{i}" for i in range(60)],  # 60个全不同
            "IDSS1": np.random.default_rng(42).weibull(1.5, 60) * 50,
        })
        info = detect_columns(df)
        # Code 的唯一值比例 = 60/60 = 1.0 > 0.5，不应被检测为分组列
        assert info["group_column"] is None, f"不应检测 Code 为分组列, got {info['group_column']}"

    def test_no_group_column(self):
        """无分组列时应返回 None"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
            "VTH1": np.random.default_rng(42).weibull(2.0, 10) * 80,
        })
        info = detect_columns(df)
        assert info["group_column"] is None
        assert "IDSS1" in info["value_columns"]
        assert "VTH1" in info["value_columns"]

    def test_only_id_and_values(self):
        """仅包含 ID 列和数值列"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] is None
        assert "PART_ID" in info["id_columns"]
        assert "IDSS1" in info["value_columns"]

    def test_numeric_group_exact_match(self):
        """数字类型的分组列通过精确匹配应被识别"""
        from model_fitting.utils import detect_columns
        df = pd.DataFrame({
            "PART_ID": [f"P{i:03d}" for i in range(10)],
            "group": [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],  # 数字但列名匹配
            "IDSS1": np.random.default_rng(42).weibull(1.5, 10) * 50,
        })
        info = detect_columns(df)
        assert info["group_column"] == "group"


class TestFilterColumnsKeepShiftOnly:
    """测试列名后缀过滤"""

    def test_basic_filter(self):
        from model_fitting.utils import filter_columns_keep_shift_only
        cols = ["IDSS1_T0", "IDSS1_After", "IDSS1_shift", "VTH1"]
        result = filter_columns_keep_shift_only(cols)
        assert result == ["IDSS1_shift"], f"应仅保留 _shift 列, got {result}"

    def test_no_shift_columns(self):
        from model_fitting.utils import filter_columns_keep_shift_only
        cols = ["IDSS1_T0", "IDSS1_After", "VTH1"]
        result = filter_columns_keep_shift_only(cols)
        assert result == [], f"无 _shift 列应返回空列表, got {result}"

    def test_mixed_case(self):
        from model_fitting.utils import filter_columns_keep_shift_only
        cols = ["IGSS1_shift", "VTH2", "BVDSS1", "IDSS1_shift"]
        result = filter_columns_keep_shift_only(cols)
        assert result == ["IGSS1_shift", "IDSS1_shift"]
