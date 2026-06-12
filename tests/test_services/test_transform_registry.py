"""测试 transform_registry"""
import numpy as np
from services.transform_registry import (
    TransformStrategy, CDFTransform, LnLnTransform,
    TRANSFORM_REGISTRY, get_transform,
)


class TestCDFTransform:
    def test_key_and_name(self):
        t = CDFTransform()
        assert t.KEY == "cdf"
        assert "CDF" in t.DISPLAY_NAME

    def test_identity(self):
        t = CDFTransform()
        cdf = np.array([0.1, 0.5, 0.9])
        result = t.transform(cdf)
        np.testing.assert_array_almost_equal(result, cdf)

    def test_ylabel(self):
        assert "CDF" in CDFTransform().get_ylabel()

    def test_xrange(self):
        t = CDFTransform()
        xs = np.array([1.0, 5.0, 10.0])
        xmin, xmax = t.get_fit_curve_xrange(xs)
        assert xmin < xs.min()
        assert xmax > xs.max()


class TestLnLnTransform:
    def test_key_and_name(self):
        t = LnLnTransform()
        assert t.KEY == "lnln"

    def test_transform_monotonic(self):
        t = LnLnTransform()
        cdf = np.linspace(0.01, 0.99, 20)
        result = t.transform(cdf)
        # ln(-ln(1-CDF)) 应严格单调增
        assert np.all(np.diff(result) > 0)

    def test_transform_no_nan(self):
        t = LnLnTransform()
        cdf = np.array([0.001, 0.5, 0.999])
        result = t.transform(cdf)
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))

    def test_ylabel(self):
        assert "ln(" in LnLnTransform().get_ylabel()


class TestRegistry:
    def test_get_transform_valid(self):
        t = get_transform("cdf")
        assert isinstance(t, TransformStrategy)
        assert t.KEY == "cdf"

    def test_get_transform_invalid(self):
        import pytest
        with pytest.raises(KeyError):
            get_transform("nonexistent")

    def test_all_transforms_registered(self):
        for key in ["cdf", "lnln"]:
            assert key in TRANSFORM_REGISTRY
