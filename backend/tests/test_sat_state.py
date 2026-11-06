from datetime import datetime, timedelta, timezone

import pytest

from app.orbit.sat_state import argument_of_latitude_deg, ground_track, satellite_state
from app.satellites_api import build_state, build_track
from app.ingestion.tle_store import ensure_tle_tables, save_tle
from app.storage.db import connect

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
SAT = [{"catnr": 1, "name": "X", "instrument": "i", "purpose": "p",
        "half_swath_km": 10, "daylight_only": False}]


def fake_prop(l1, l2, when):
    return (7000.0, 0.0, 0.0), (0.0, 0.0, 7.5)


def _save(conn, age_days):
    ensure_tle_tables(conn)
    epoch = (NOW - timedelta(days=age_days)).isoformat()
    save_tle(conn, {"catnr": 1, "name": "X", "line1": "l1", "line2": "l2",
                    "epoch_utc": epoch}, NOW, "test")


def test_argument_of_latitude_quadrants():
    v = (0.0, 0.0, 7.5)
    assert argument_of_latitude_deg((7000, 0, 0), v) == pytest.approx(0.0)
    assert argument_of_latitude_deg((0, 0, 7000), (-7.5, 0, 0)) == pytest.approx(90.0)
    assert argument_of_latitude_deg((-7000, 0, 0), (0, 0, -7.5)) == pytest.approx(180.0)
    assert argument_of_latitude_deg((0, 0, -7000), (7.5, 0, 0)) == pytest.approx(270.0)


def test_state_from_vectors():
    s = satellite_state("l1", "l2", NOW, propagate=fake_prop)
    assert s["lat_deg"] == pytest.approx(0.0, abs=0.01)
    assert s["alt_km"] == pytest.approx(7000.0 - 6378.137, abs=1.0)
    assert s["speed_km_s"] == pytest.approx(7.5)
    assert s["ascending"] is True


def test_ground_track_points():
    pts = ground_track("l1", "l2", NOW, minutes=5, step_s=60, propagate=fake_prop)
    assert [p["t_s"] for p in pts] == [0, 60, 120, 180, 240, 300]


def test_track_rejects_bad_args():
    with pytest.raises(ValueError):
        ground_track("l1", "l2", NOW, minutes=0, step_s=60, propagate=fake_prop)


def test_no_element_set(tmp_path):
    conn = connect(tmp_path / "t.db")
    out = build_state(conn, NOW, SAT)
    assert out["satellites"][0]["status"] == "no_element_set"
    assert "state" not in out["satellites"][0]


def test_stale_element_set_gives_no_position(tmp_path):
    conn = connect(tmp_path / "t.db")
    _save(conn, 30)

    def boom(*a):
        raise AssertionError("must not propagate a stale element set")

    out = build_state(conn, NOW, SAT, state_fn=boom)
    assert out["satellites"][0]["status"] == "stale_element_set"
    assert "state" not in out["satellites"][0]


def test_fresh_element_set_gives_state_and_age(tmp_path):
    conn = connect(tmp_path / "t.db")
    _save(conn, 1)
    out = build_state(conn, NOW, SAT, state_fn=lambda a, b, c: {"lat_deg": 1.0})
    e = out["satellites"][0]
    assert e["status"] == "ok" and e["tle_age_days"] == 1.0
    assert e["state"] == {"lat_deg": 1.0}
    assert out["data_origin"] == "PROPAGATED_FROM_REAL_TLE"


def test_unknown_catalogue_number_gives_none(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert build_track(conn, 999, NOW, satellites=SAT) is None
