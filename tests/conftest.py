# tests conftest — 共享 fixtures
import os
import sys
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

TEST_CSV = os.path.join(_project_root, "test_weibull.csv")


@pytest.fixture(scope="session")
def sample_df():
    """从项目自带测试 CSV 加载 DataFrame"""
    if os.path.exists(TEST_CSV):
        return pd.read_csv(TEST_CSV)
    # 如果没有 CSV，生成一个最小 DataFrame
    rng = np.random.default_rng(42)
    n = 60
    return pd.DataFrame({
        "PART_ID": [f"P{i:03d}" for i in range(n)],
        "group": ["A"] * 20 + ["B"] * 20 + ["C"] * 20,
        "IDSS1": rng.weibull(1.5, size=n) * 50,
        "IDSS2": rng.weibull(2.0, size=n) * 30,
        "VTH1": rng.normal(1.0, 0.1, size=n),
    })


@pytest.fixture
def weibull_samples():
    """已知参数的 Weibull 分布样本（用于拟合验证）"""
    rng = np.random.default_rng(12345)
    return rng.weibull(1.5, size=100) * 50


@pytest.fixture
def mock_view():
    """Mock 的 AppViewProtocol 实现"""
    from unittest.mock import MagicMock

    view = MagicMock()
    # 默认返回值
    view.get_selected_columns.return_value = [(0, "IDSS1")]
    view.get_series_styles.return_value = [{"marker": "o", "linestyle": "-", "limit": 0.1}]
    view.get_model_selection.return_value = "Weibull"
    view.get_transform_selection.return_value = "cdf"
    view.get_x_scale.return_value = "线性"
    view.get_y_scale.return_value = "线性"
    view.get_theme.return_value = "default"
    view.get_x_limits.return_value = (None, None)
    view.get_y_limits.return_value = (None, None)
    view.get_max_series.return_value = 4
    view.get_series_count.return_value = 1
    view.ask_yes_no.return_value = True
    view.ask_save_path.return_value = None
    view.ask_open_path.return_value = None
    return view
