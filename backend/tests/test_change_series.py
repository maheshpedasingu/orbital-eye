import sqlite3

import numpy as np

from app.analysis.change import load_change_config
from app.analysis.change_series import (
    compare_pair, consecutive_pairs, ensure_series_table, list_series, run_change_series,
)
from app.analysis.vegetation_store import ensure_table, record_result

B = (80.0, 16.0, 80.3, 16.3)


def _s(sid, dt):
    return {"id": sid, "datetime": dt}


def _loader(comps):
    return lambda scene, bbox, dec, cache, comp: comps[scene["id"]]


def _comp(v):
    return {"values": np.array(v, dtype=float), "bounds_lonlat": B}


def test_consecutive_pairs_sorted_and_deduped():
    sc = [_s("C", "2026-10-20T00:00:00Z"), _s("A", "2026-10-01T00:00:00Z"),
          _s("B", "2026-10-10T00:00:00Z"), _s("B", "2026-10-10T00:00:00Z")]
    pairs = consecutive_pairs(sc)
    assert [(r["id"], c["id"]) for r, c in pairs] == [("A", "B"), ("B", "C")]


def test_compare_pair_detects_increase():
    comps = {"A": _comp([[0.2, 0.2], [0.2, 0.2]]), "B": _comp([[0.6, 0.6], [0.6, 0.6]])}
    res = compare_pair(_s("A", "2026-10-01T00:00:00Z"), _s("B", "2026-10-11T00:00:00Z"),
                       None, 4, None, load_change_config(), _loader(comps), None)
    assert res["status"] == "ok"
    assert res["meta"]["class_fractions"]["increase"] == 1.0
    assert res["meta"]["days_between"] == 10.0


def test_low_overlap_is_flagged():
    nan = float("nan")
    comps = {"A": _comp([[0.2, nan], [nan, nan]]), "B": _comp([[0.6, 0.6], [0.6, 0.6]])}
    res = compare_pair(_s("A", "2026-10-01T00:00:00Z"), _s("B", "2026-10-11T00:00:00Z"),
                       None, 4, None, load_change_config(), _loader(comps), None)
    assert res["status"] == "insufficient_overlap"


def test_run_stores_once_and_skips_unstored_scenes(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_table(conn)
    record_result(conn, "ok", "c", 4, "A", "2026-10-01T00:00:00Z", "a.png", {})
    record_result(conn, "ok", "c", 4, "B", "2026-10-11T00:00:00Z", "b.png", {})
    comps = {"A": _comp([[0.2, 0.2]]), "B": _comp([[0.6, 0.6]]), "C": _comp([[0.1, 0.1]])}
    calls = []

    def loader(scene, *a):
        calls.append(scene["id"])
        return comps[scene["id"]]

    lister = lambda c, b, d: [_s("A", "2026-10-01T00:00:00Z"),
                              _s("B", "2026-10-11T00:00:00Z"),
                              _s("C", "2026-10-21T00:00:00Z")]
    first = run_change_series(conn, lister=lister, loader=loader, out_dir=tmp_path)
    assert [r["status"] for r in first] == ["ok"]
    n = len(calls)
    second = run_change_series(conn, lister=lister, loader=loader, out_dir=tmp_path)
    assert second[0]["status"] == "cached" and len(calls) == n
    assert len(list_series(conn, 4)) == 1
