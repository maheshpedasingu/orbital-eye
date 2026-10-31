import numpy as np
import pytest

from app.analysis.ndvi import ndvi
from app.ingestion.stac import summarize_item


def test_known_value():
    assert abs(ndvi([0.1], [0.5])[0] - (0.4 / 0.6)) < 1e-12


def test_equal_bands_give_zero():
    assert ndvi([0.3], [0.3])[0] == 0.0


def test_zero_denominator_is_nan_without_warnings():
    with np.errstate(all="raise"):
        assert np.isnan(ndvi([0.0], [0.0])[0])


def test_valid_mask_hides_pixels():
    out = ndvi([0.1, 0.1], [0.5, 0.5], valid=[True, False])
    assert not np.isnan(out[0]) and np.isnan(out[1])


def test_non_finite_and_negative_inputs_are_nan():
    out = ndvi([np.nan, -0.1, 0.1], [0.5, 0.5, np.inf])
    assert np.isnan(out).all()


def test_result_is_within_minus_one_and_one():
    rng = np.random.default_rng(0)
    out = ndvi(rng.random(1000), rng.random(1000))
    ok = out[~np.isnan(out)]
    assert ok.min() >= -1.0 and ok.max() <= 1.0


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        ndvi([0.1, 0.2], [0.5])


def test_summarize_item_extracts_bands():
    # INVENTED TEST FIXTURE, NOT real Earth Search data.
    item = {
        "id": "TEST_ITEM",
        "properties": {"datetime": "2026-01-01T05:00:00Z", "eo:cloud_cover": 12.5,
                       "platform": "sentinel-2x"},
        "assets": {
            "red": {"href": "https://example.invalid/red.tif", "type": "image/tiff",
                    "raster:bands": [{"scale": 0.0001, "offset": -0.1, "nodata": 0}]},
            "nir": {"href": "https://example.invalid/nir.tif", "type": "image/tiff"},
            "visual": {"href": "https://example.invalid/v.tif"},
        },
    }
    s = summarize_item(item)
    assert s["cloud_cover"] == 12.5
    assert s["bands"]["red"]["scale"] == 0.0001
    assert s["bands"]["nir"]["scale"] is None
    assert "scl" not in s["bands"]
    assert s["asset_keys"] == ["nir", "red", "visual"]
