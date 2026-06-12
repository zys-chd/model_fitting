"""测试 DataService — 数据加载与列检测"""
import os
import tempfile
import numpy as np
import pandas as pd


def _make_test_csv(tmpdir, content: str, name: str = "test.csv") -> str:
    path = os.path.join(str(tmpdir), name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestDataService:
    def test_create_service(self):
        from model_fitting.services.data_service import DataService
        svc = DataService()
        assert svc is not None

    def test_load_csv(self, tmpdir):
        from model_fitting.services.data_service import DataService
        path = _make_test_csv(tmpdir, "A,B\n1,2\n3,4\n")
        df = DataService().load_file(path)
        assert len(df) == 2
        assert list(df.columns) == ["A", "B"]

    def test_detect_structure_with_group(self, tmpdir):
        from model_fitting.services.data_service import DataService
        path = _make_test_csv(tmpdir, "PART_ID,group,IDSS1,VTH1\nP001,A,1.2,3.4\nP002,A,2.3,4.5\nP003,B,3.4,5.6\n")
        df = DataService().load_file(path)
        info = DataService.detect_structure(df)
        assert info["group_column"] == "group"
        assert "IDSS1" in info["value_columns"]
        assert "VTH1" in info["value_columns"]

    def test_detect_structure_no_group(self, tmpdir):
        from model_fitting.services.data_service import DataService
        path = _make_test_csv(tmpdir, "IDSS1,VTH1\n1.2,3.4\n2.3,4.5\n")
        df = DataService().load_file(path)
        info = DataService.detect_structure(df)
        assert info["group_column"] is None
        assert "IDSS1" in info["value_columns"]

    def test_filter_shift_only(self):
        from model_fitting.services.data_service import DataService
        df = pd.DataFrame({
            "IDSS1_T0": [1, 2],
            "IDSS1_After": [3, 4],
            "IDSS1_shift": [5, 6],
            "VTH1": [7, 8],
        })
        result = DataService.filter_shift_only(df)
        assert list(result.columns) == ["IDSS1_shift"]

    def test_append_file(self, tmpdir):
        from model_fitting.services.data_service import DataService
        path1 = _make_test_csv(tmpdir, "A,B\n1,2\n3,4\n", name="f1.csv")
        path2 = _make_test_csv(tmpdir, "A,B\n5,6\n", name="f2.csv")
        svc = DataService()
        df1 = svc.load_file(path1)
        combined = svc.append_file(df1, path2)
        assert len(combined) == 3
        assert list(combined["A"]) == [1, 3, 5]

    def test_append_file_different_cols(self, tmpdir):
        """附加不同列的 CSV，应取并集，缺失填 NaN"""
        from model_fitting.services.data_service import DataService
        path1 = _make_test_csv(tmpdir, "A,B\n1,2\n", name="f1.csv")
        path2 = _make_test_csv(tmpdir, "A,C\n3,4\n", name="f2.csv")
        svc = DataService()
        df1 = svc.load_file(path1)
        combined = svc.append_file(df1, path2)
        assert len(combined) == 2
        assert "A" in combined.columns
        assert "B" in combined.columns
        assert "C" in combined.columns
        assert pd.isna(combined.loc[1, "B"])
