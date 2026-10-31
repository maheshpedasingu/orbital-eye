import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import change_api
from app.analysis.change import (
    change_summary, classify_change, load_change_config, ndvi_difference,
    render_change_png,
)
from app.analysis.change_job import run_change_job
from app.analysis.change_store import latest_change_any
from app.analysis.scene_cache import load_or_compute
from app.main import app
from app.storage.db import connect

BBOX = (80.5, 16.3, 80.8, 16.6)
BANDS = {k: {} for k in ("red", "nir", "scl")}
CUR = {"id": "CUR", "datetime": "2026-10-26T05:14:15Z", "cloud_cover": 10.0, "bands": BANDS}
REF = {"id": "REF", "datetime": "2026-10-06T05:14:15Z", "cloud_cover": 15.0, "bands": BANDS}
NEAR = {"id": "NEAR", "datetime": "2026-10-24T05:14:15Z", "cloud_cover": 5.0, "bands": BANDS}
CUR_VALUES = np.array([[0.7, 0.3], [np.nan, 0.5]])   # INVENTED test arrays
REF_VALUES = np.array([[0.3, 0.3], [0.6, np.nan]])


def make_computer(ref_values=REF_VALUES):
    def computer(summary, bbox, decimate):
        vals = CUR_VALUES if summary["id"] == "CUR" else ref_values
        return {"values": vals, "scl": np.full(vals.shape, 4),
                "bounds_lonlat": BBOX, "coverage": 1.0}
    return computer


def run(conn, tmp_path, lister, computer=None):
    return run_change_job(conn, finder=lambda *a: CUR, lister=lister,
                          computer=computer or make_computer(), out_dir=tmp_path)


def test_difference_is_nan_unless_both_dates_usable():
    d = ndvi_difference([0.7, np.nan, 0.5], [0.3, 0.4, np.nan])
    assert abs(d[0] - 0.4) < 1e-12 and np.isnan(d[1]) and np.isnan(d[2])


def test_difference_rejects_different_grids():
    with pytest.raises(ValueError):
        ndvi_difference(np.zeros((2, 2)), np.zeros((3, 3)))


def test_classification_boundaries():
    cfg = load_change_config()
    diff = np.array([-0.2, -0.19, 0.0, 0.19, 0.2, np.nan])
    assert classify_change(diff, cfg).tolist() == [0, 1, 1, 1, 2, -1]


def test_config_thresholds_must_straddle_zero(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"decrease_threshold": 0.1, "increase_threshold": 0.2,'
                 '"min_usable_fraction": 0.4, "min_gap_days": 14,'
                 '"max_reference_tries": 3,'
                 '"colors": {"decrease": "#000000", "stable": "#000000", "increase": "#000000"}}',
                 encoding="utf-8")
    with pytest.raises(ValueError):
        load_change_config(f)


def test_fractions_and_area():
    index = np.array([0, 0, 1, 2, -1])
    s = change_summary(index, np.array([-.3, -.3, 0.0, .3, np.nan]), 1000)
    assert s["overlap_fraction"] == 0.8
    assert s["class_fractions"] == {"decrease": 0.5, "stable": 0.25, "increase": 0.25}
    assert s["area_km2"]["decrease"] == 2.0


def test_render_marks_stable_faint_and_unusable_transparent():
    cfg = load_change_config()
    img = Image.open(io.BytesIO(render_change_png(np.array([[0, 1, 2, -1]]), cfg))).convert("RGBA")
    assert [img.getpixel((x, 0))[3] for x in range(4)] == [210, 70, 210, 0]


def test_scene_cache_avoids_recompute(tmp_path):
    calls = []

    def computer(summary, bbox, decimate):
        calls.append(1)
        return make_computer()(summary, bbox, decimate)

    a = load_or_compute(CUR, BBOX, 4, tmp_path, computer)
    b = load_or_compute(CUR, BBOX, 4, tmp_path, computer)
    assert len(calls) == 1
    assert np.allclose(a["values"], b["values"], equal_nan=True)
    assert b["bounds_lonlat"] == a["bounds_lonlat"]


def test_ok_run_compares_only_usable_pixels(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = run(conn, tmp_path, lambda *a: [REF])
    assert r["status"] == "ok"
    assert r["overlap_fraction"] == 0.5
    assert r["class_fractions"] == {"decrease": 0.0, "stable": 0.5, "increase": 0.5}
    assert r["days_between"] == 20.0
    assert (tmp_path / "change_CUR_vs_REF_d4.png").exists()


def test_reference_too_close_in_time_is_not_used(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert run(conn, tmp_path, lambda *a: [NEAR])["status"] == "no_reference"


def test_cloudy_overlap_is_rejected_not_forced(tmp_path):
    conn = connect(tmp_path / "t.db")
    all_masked = make_computer(np.full((2, 2), np.nan))
    r = run(conn, tmp_path, lambda *a: [REF], all_masked)
    assert r["status"] == "insufficient_overlap" and "REF" in r["error"]
    assert not list(tmp_path.glob("*.png"))


def test_mismatched_grids_are_recorded_as_failed(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = run(conn, tmp_path, lambda *a: [REF], make_computer(np.zeros((3, 3))))
    assert r["status"] == "failed"
    assert latest_change_any(conn)["status"] == "failed"


def test_api_reports_none_with_the_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(change_api, "connect", lambda: connect(tmp_path / "t.db"))
    client = TestClient(app)
    assert client.get("/api/vegetation/change/latest").json()["status"] == "none"
    assert client.get("/api/vegetation/change/latest.png").status_code == 404


def test_api_serves_change_with_credit_and_png(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    conn = connect(dbfile)
    run(conn, tmp_path, lambda *a: [REF])
    monkeypatch.setattr(change_api, "connect", lambda: connect(dbfile))
    client = TestClient(app)
    data = client.get("/api/vegetation/change/latest").json()
    assert data["status"] == "ok" and data["data_origin"] == "REAL_EXTERNAL"
    assert data["attribution"] == "Contains modified Copernicus Sentinel data 2026"
    assert client.get("/api/vegetation/change/latest.png").status_code == 200
