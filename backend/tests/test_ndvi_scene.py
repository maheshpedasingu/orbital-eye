import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from app.analysis.ndvi_scene import (
    VALID_SCL, choose_scene, scale_offset, window_for_lonlat,
)


def make_dataset():
    # 100 x 100 pixels, 0.01 degree each, top-left corner at lon 80.0, lat 17.0
    mem = MemoryFile()
    with mem.open(driver="GTiff", height=100, width=100, count=1, dtype="uint16",
                  crs="EPSG:4326", transform=from_origin(80.0, 17.0, 0.01, 0.01)) as ds:
        ds.write(np.ones((1, 100, 100), dtype="uint16"))
    return mem


def test_window_inside_raster_matches_hand_calculation():
    with make_dataset().open() as ds:
        win, cov = window_for_lonlat(ds, (80.2, 16.2, 80.4, 16.4))
    assert (win.col_off, win.row_off, win.width, win.height) == (20, 60, 20, 20)
    assert cov == 1.0


def test_partly_outside_raster_reports_half_coverage():
    with make_dataset().open() as ds:
        win, cov = window_for_lonlat(ds, (79.9, 16.2, 80.1, 16.4))
    assert win.col_off == 0 and win.width == 10
    assert abs(cov - 0.5) < 1e-6


def test_box_outside_raster_raises():
    with make_dataset().open() as ds:
        with pytest.raises(ValueError):
            window_for_lonlat(ds, (82.0, 16.2, 82.2, 16.4))


def _summary(cloud, keys=("red", "nir", "scl")):
    return {"id": f"s{cloud}", "cloud_cover": cloud, "bands": {k: {} for k in keys}}


def test_choose_scene_picks_lowest_cloud_under_limit():
    best = choose_scene([_summary(50), _summary(10), _summary(25)], 40)
    assert best["cloud_cover"] == 10


def test_choose_scene_returns_none_if_all_too_cloudy():
    assert choose_scene([_summary(80), _summary(95)], 40) is None


def test_choose_scene_needs_all_three_bands():
    assert choose_scene([_summary(5, keys=("red", "nir"))], 40) is None


def test_missing_scale_or_offset_refuses_to_guess():
    with pytest.raises(ValueError):
        scale_offset({"scale": None, "offset": None})
    assert scale_offset({"scale": 0.0001, "offset": -0.1}) == (0.0001, -0.1)


def test_cloud_and_shadow_classes_are_never_valid():
    for code in (0, 1, 2, 3, 7, 8, 9, 10, 11):
        assert code not in VALID_SCL
