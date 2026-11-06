import sqlite3

from app.analysis.vegetation_store import ensure_table, list_ok, record_result
from app.vegetation_api import build_series


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_table(conn)
    return conn


def _meta(coverage, veg):
    return {"fraction_with_ndvi": coverage,
            "categories": [{"name": "vegetation", "fraction": veg}]}


def test_series_sorted_by_acquisition_time():
    conn = _conn()
    record_result(conn, "ok", "c", 4, "B", "2026-10-26T05:06:34Z", "b.png", _meta(0.9, 0.4))
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T05:05:16Z", "a.png", _meta(0.5, 0.3))
    pts = build_series(list_ok(conn, 4))
    assert [p["scene_id"] for p in pts] == ["A", "B"]
    assert pts[0]["metrics"]["fraction_with_ndvi"] == 0.5
    assert pts[1]["category_fractions"]["vegetation"] == 0.4


def test_rerun_of_same_scene_gives_one_point():
    conn = _conn()
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T05:05:16Z", "a.png", _meta(0.5, 0.3))
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T05:05:16Z", "a.png", _meta(0.6, 0.3))
    pts = build_series(list_ok(conn, 4))
    assert len(pts) == 1 and pts[0]["metrics"]["fraction_with_ndvi"] == 0.6


def test_failed_and_no_scene_rows_are_excluded():
    conn = _conn()
    record_result(conn, "failed", "c", 4, error="boom")
    record_result(conn, "no_scene", "c", 4, error="none")
    assert build_series(list_ok(conn, 4)) == []


def test_decimate_filter():
    conn = _conn()
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T00:00:00Z", "a.png", _meta(0.5, 0.3))
    record_result(conn, "ok", "c", 8, "A", "2026-10-01T00:00:00Z", "a8.png", _meta(0.5, 0.3))
    assert len(build_series(list_ok(conn, 4))) == 1
