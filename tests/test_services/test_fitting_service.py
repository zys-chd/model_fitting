"""测试拟合服务"""
import numpy as np
from services.fitting_service import FittingService, FitResult
from services.transform_registry import TransformStrategy


class TestFittingService:
    def test_create_service(self):
        svc = FittingService()
        assert svc is not None
        assert len(svc.get_model_keys()) >= 9

    def test_get_model(self):
        svc = FittingService()
        model = svc.get_model("Weibull")
        assert model.KEY == "Weibull"

    def test_fit_single_weibull(self, weibull_samples):
        svc = FittingService()
        result = svc.fit_single(weibull_samples, "Weibull")
        assert isinstance(result, FitResult)
        assert result.model_name == "Weibull"
        assert result.r_squared > 0.8  # Weibull 样本拟合 Weibull 应有高 R²
        assert len(result.params) == 2  # Weibull-2P
        assert len(result.xs) > 0
        assert len(result.cdf_raw) > 0

    def test_fit_with_transform(self, weibull_samples):
        svc = FittingService()
        result_cdf = svc.fit_single(weibull_samples, "Weibull", transform_key="cdf")
        result_lnln = svc.fit_single(weibull_samples, "Weibull", transform_key="lnln")

        # CDF 变换：值应在 [0, 1]
        assert np.all(result_cdf.y_transformed >= 0) and np.all(result_cdf.y_transformed <= 1)
        # lnln 变换：值在合理范围
        assert not np.any(np.isnan(result_lnln.y_transformed))

    def test_fit_single_invalid_model(self, weibull_samples):
        import pytest
        svc = FittingService()
        with pytest.raises(KeyError):
            svc.fit_single(weibull_samples, "NonExistentModel")

    def test_get_transform(self):
        svc = FittingService()
        t = svc.get_transform("cdf")
        assert isinstance(t, TransformStrategy)

    def test_get_outlier_detector(self):
        svc = FittingService()
        detector = svc.get_outlier_detector("mad")
        assert detector.KEY == "mad"
