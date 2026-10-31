import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import vegetation_api
from app.analysis.categories import (
    category_fractions, classify_ndvi, load_categories, render_png,
)
from app.analysis.vegetation_job import run_vegetation_job
from app.analysis.vegetation_store import latest_any
from app.main import app
from app.storage.db import connect

SCENE = {"id": "TEST_SCENE", "datetime": "2026-10-26T05:14:15Z",
         "cloud_cover": 10.0, "bands": {}}


def fake_finder(collection, bbox, days, max_cloud):
    return SCENE


def fake_compute(summary, bbox, decimate):
    # INVENTED TEST FIXTURE, NOT Sentinel data
    return {"values": np.array([[0.1, 0.7], [np.nan, 0.5]]),
            "scl": np.array([[5, 4], [10, 4]]),
            "bounds_lonlat": (80.5, 16.3, 80.8, 16.6), "coverage": 1.0}


def test_category_boundaries():
    cats = load_categories()
    values = np.array([-1.0, 0.1999, 0.2, 0.4, 0.6, 1.0, np.nan])
    assert classify_ndvi(values, cats).tolist() == [0, 0, 1, 2, 3, 3, -1]


def test_fractions_ignore_unusable_pixels_and_sum_to_one():
    cats = load_categories()
    fr = category_fractions(np.array([0, 0, 1, 3, -1]), cats)
    assert abs(sum(v for v in fr.values()) - 1.0) < 1e-9
    assert fr[cats[0]["name"]] == 0.5


def test_gap_between_categories_is_rejected(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(
        '{"categories":[{"name":"a","min":-1,"max":0.2,"color":"#000000"},'
        '{"name":"b","min":0.3,"max":1,"color":"#ffffff"}]}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_categories(f)


def test_default_config_covers_minus_one_to_one():
    cats = load_categories()
    assert cats[0]["min"] == -1.0 and cats[-1]["max"] == 1.0


def test_render_png_makes_unusable_pixels_transparent():
    cats = load_categories()
    img = Image.open(io.BytesIO(render_png(np.array([[0, -1]]), cats))).convert("RGBA")
    assert img.size == (2, 1)
    assert img.getpixel((0, 0))[3] == 200 and img.getpixel((1, 0))[3] == 0
    expected = tuple(int(cats[0]["color"][k:k + 2], 16) for k in (1, 3, 5))
    assert img.getpixel((0, 0))[:3] == expected


def test_no_scene_is_recorded_not_faked(tmp_path):
    conn = connect(tmp_path / "t.db")
    result = run_vegetation_job(conn, finder=lambda *a: None,
                                computer=fake_compute, out_dir=tmp_path)
    assert result["status"] == "no_scene"
    assert not list(tmp_path.glob("*.png"))


def test_ok_run_writes_png_and_second_run_is_cached(tmp_path):
    conn = connect(tmp_path / "t.db")
    kw = dict(finder=fake_finder, computer=fake_compute, out_dir=tmp_path)
    assert run_vegetation_job(conn, **kw)["status"] == "ok"
    assert run_vegetation_job(conn, **kw)["status"] == "cached"
    assert (tmp_path / "TEST_SCENE_d4.png").exists()


def test_failed_compute_is_recorded_with_its_error(tmp_path):
    conn = connect(tmp_path / "t.db")

    def broken(summary, bbox, decimate):
        raise RuntimeError("network down")

    result = run_vegetation_job(conn, finder=fake_finder, computer=broken,
                                out_dir=tmp_path)
    assert result["status"] == "failed" and "network down" in result["error"]
    assert latest_any(conn)["status"] == "failed"


def test_api_reports_none_before_any_result(tmp_path, monkeypatch):
    monkeypatch.setattr(vegetation_api, "connect", lambda: connect(tmp_path / "t.db"))
    client = TestClient(app)
    assert client.get("/api/vegetation/latest").json()["status"] == "none"
    assert client.get("/api/vegetation/latest.png").status_code == 404


def test_api_serves_result_with_credit_and_png(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    conn = connect(dbfile)
    run_vegetation_job(conn, finder=fake_finder, computer=fake_compute, out_dir=tmp_path)
    monkeypatch.setattr(vegetation_api, "connect", lambda: connect(dbfile))
    client = TestClient(app)
    data = client.get("/api/vegetation/latest").json()
    assert data["status"] == "ok" and data["data_origin"] == "REAL_EXTERNAL"
    assert data["attribution"] == "Contains modified Copernicus Sentinel data 2026"
    png = client.get("/api/vegetation/latest.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
