"""测试 stat_registry"""
import numpy as np
from services.stat_registry import (
    StatCalculator, BasicStatsCalculator, FitAtLimitCalculator,
    CompositeStatsCalculator, STAT_REGISTRY, get_calculator,
)


class TestBasicStatsCalculator:
    def test_standard_stats(self):
        calc = BasicStatsCalculator()
        samples = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calc.compute(samples)

        assert result["样本数"] == 5
        assert abs(result["均值"] - 3.0) < 1e-9
        assert abs(result["中位数"] - 3.0) < 1e-9
        assert result["最小值"] == 1.0
        assert result["最大值"] == 5.0

    def test_single_sample(self):
        calc = BasicStatsCalculator()
        samples = np.array([42.0])
        result = calc.compute(samples)
        assert result["样本数"] == 1
        assert result["均值"] == 42.0

    def test_empty(self):
        calc = BasicStatsCalculator()
        result = calc.compute(np.array([]))
        assert result == {}

    def test_registered(self):
        assert "basic" in STAT_REGISTRY
        assert isinstance(STAT_REGISTRY["basic"], BasicStatsCalculator)


class TestFitAtLimitCalculator:
    def test_no_context_returns_empty(self):
        calc = FitAtLimitCalculator()
        result = calc.compute(np.array([1, 2, 3]))
        assert result == {}

    def test_with_context(self):
        from unittest.mock import MagicMock
        calc = FitAtLimitCalculator()
        model = MagicMock()
        model.cdf.return_value = 0.632
        result = calc.compute(
            np.array([1, 2, 3]),
            model=model, params=(1.5, 50.0), limit=50.0,
        )
        assert "limit处F值" in result
        assert result["limit处F值"] == 0.632


class TestCompositeStatsCalculator:
    def test_compute_all(self):
        composite = CompositeStatsCalculator([
            BasicStatsCalculator(),
        ])
        samples = np.array([1.0, 2.0, 3.0])
        result = composite.compute_all(samples)
        assert "样本数" in result
        assert "均值" in result

    def test_default_uses_registry(self):
        composite = CompositeStatsCalculator()
        samples = np.array([1.0, 2.0, 3.0])
        result = composite.compute_all(samples)
        # 应该包含 basic 的统计量
        assert "样本数" in result
        assert "均值" in result


class TestRegistry:
    def test_get_calculator_valid(self):
        calc = get_calculator("basic")
        assert isinstance(calc, StatCalculator)

    def test_get_calculator_invalid(self):
        import pytest
        with pytest.raises(KeyError):
            get_calculator("nonexistent")
