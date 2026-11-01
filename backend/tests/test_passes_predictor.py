from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import passes_api
from app.ingestion.tle_store import ensure_tle_tables, save_tle
from app.main import app
from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.geodetic import ecef_to_geodetic
from app.orbit.pass_predictor import (
    choose_step_s, find_opportunities, is_daytime, local_solar_hour, predict_all,
)
from app.orbit.propagate import propagate_tle
from app.storage.db import connect

# FIXTURE from the python-sgp4 docs (Dec 2019). NOT a current orbit.
L1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
L2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
T = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SAT = {"catnr": 11111, "name": "Test", "instrument": "x", "purpose": "p",
       "half_swath_km": 145, "daylight_only": False}


def subpoint(t):
    r, _ = propagate_tle(L1, L2, t)
    lat, lon, _ = ecef_to_geodetic(*teme_to_ecef_km(r, gmst_rad(t)))
    return lat, lon


def store(conn, epoch):
    ensure_tle_tables(conn)
    save_tle(conn, {"catnr": 11111, "name": "TEST SAT", "line1": L1, "line2": L2,
                    "epoch_utc": epoch.isoformat()}, NOW, "test")


def test_local_solar_hour_of_the_sentinel_scene_time():
    when = datetime(2026, 10, 26, 5, 14, 15, tzinfo=timezone.utc)
    assert abs(local_solar_hour(when, 80.648) - 10.614) < 0.01   # 5.2375 h + 5.3765 h


def test_daytime_boundaries():
    assert is_daytime(6.0) and not is_daytime(5.99) and not is_daytime(18.0)


def test_time_step_is_fine_for_narrow_swaths():
    assert choose_step_s(145) == 5.0 and choose_step_s(1520) == 30.0


def test_window_is_found_over_a_point_the_satellite_really_passes():
    lat, lon = subpoint(T)
    wins = find_opportunities(L1, L2, T - timedelta(minutes=10), 0.3, lat, lon, 50.0, step_s=1.0)
    assert len(wins) == 1
    w = wins[0]
    assert abs((datetime.fromisoformat(w["tca_utc"]) - T).total_seconds()) <= 1.0
    assert w["min_distance_km"] < 8.0
    assert not w["partial"]


def test_window_that_is_already_open_at_the_start_is_flagged_partial():
    lat, lon = subpoint(T)
    wins = find_opportunities(L1, L2, T, 0.1, lat, lon, 50.0, step_s=1.0)
    assert wins and wins[0]["partial"]


def test_daylight_filter_keeps_only_daytime_windows():
    lat, lon = subpoint(T)
    kw = dict(step_s=1.0)
    start = T - timedelta(minutes=10)
    every = find_opportunities(L1, L2, start, 0.3, lat, lon, 50.0, daylight_only=False, **kw)
    day = find_opportunities(L1, L2, start, 0.3, lat, lon, 50.0, daylight_only=True, **kw)
    assert len(day) == sum(1 for w in every if w["daytime"])
    assert all(w["daytime"] for w in day)


def test_missing_element_set_is_reported(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = predict_all(conn, now=NOW, satellites=[SAT], finder=lambda *a, **k: [])
    assert r["satellites"][0]["status"] == "no_element_set"
    assert r["data_origin"] == "PROPAGATED_FROM_REAL_TLE"


def test_stale_element_set_is_refused_not_predicted(tmp_path):
    conn = connect(tmp_path / "t.db")
    store(conn, NOW - timedelta(days=20))

    def never(*a, **k):
        raise AssertionError("must not predict from a stale element set")

    s = predict_all(conn, now=NOW, satellites=[SAT], finder=never)["satellites"][0]
    assert s["status"] == "stale_element_set" and s["opportunities"] == []


def test_fresh_element_set_is_used_and_results_are_limited(tmp_path):
    conn = connect(tmp_path / "t.db")
    store(conn, NOW - timedelta(days=1))
    calls = []

    def fake(*a, **k):
        calls.append(a)
        return [{"n": i} for i in range(7)]

    s = predict_all(conn, now=NOW, hours=48.0, limit=3, satellites=[SAT],
                    finder=fake)["satellites"][0]
    assert s["status"] == "ok" and len(s["opportunities"]) == 3
    assert abs(s["tle_age_days"] - 1.0) < 1e-9
    assert calls[0][3] == 48.0


def test_api_carries_the_prediction_label_and_the_target(tmp_path, monkeypatch):
    monkeypatch.setattr(passes_api, "connect", lambda: connect(tmp_path / "t.db"))
    data = TestClient(app).get("/api/passes/next").json()
    assert data["data_origin"] == "PROPAGATED_FROM_REAL_TLE"
    assert abs(data["target"]["lat_deg"] - 16.506) < 1e-9
    assert all(s["status"] == "no_element_set" for s in data["satellites"])