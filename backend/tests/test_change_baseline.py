import sqlite3

from app.analysis.change_baseline import (
    choose_baseline, list_baseline, run_change_baseline,
)
from app.analysis.vegetation_store import ensure_table, record_result


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_table(conn)
    return conn


def test_baseline_is_best_coverage_scene():
    conn = _conn()
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T00:00:00Z", "a", {"fraction_with_ndvi": 0.5})
    record_result(conn, "ok", "c", 4, "B", "2026-10-05T00:00:00Z", "b", {"fraction_with_ndvi": 0.9})
    record_result(conn, "ok", "c", 4, "C", "2026-10-09T00:00:00Z", "c", {"fraction_with_ndvi": 0.7})
    rows = conn.execute("SELECT * FROM vegetation_results").fetchall()
    assert choose_baseline(rows)["id"] == "B"


def test_no_scenes_gives_no_baseline():
    assert choose_baseline([]) is None
    assert run_change_baseline(_conn()) == []


def test_each_scene_compared_once_against_baseline():
    import numpy as np
    conn = _conn()
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T00:00:00Z", "a", {"fraction_with_ndvi": 0.5})
    record_result(conn, "ok", "c", 4, "B", "2026-10-05T00:00:00Z", "b", {"fraction_with_ndvi": 0.9})
    record_result(conn, "ok", "c", 4, "C", "2026-10-09T00:00:00Z", "c", {"fraction_with_ndvi": 0.7})
    b = (80.0, 16.0, 80.3, 16.3)
    comps = {k: {"values": np.array([[v, v]]), "bounds_lonlat": b}
             for k, v in (("A", 0.2), ("B", 0.5), ("C", 0.8))}
    loader = lambda scene, *a: comps[scene["id"]]
    first = run_change_baseline(conn, loader=loader)
    assert sorted(r["current"] for r in first) == ["A", "C"]
    second = run_change_baseline(conn, loader=loader)
    assert all(r["status"] == "cached" for r in second)
    assert len(list_baseline(conn, 4)) == 2
