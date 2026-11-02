from fastapi.testclient import TestClient

from app import passes_api, scheduler
from app.ingestion.celestrak import name_matches
from app.ingestion.run_celestrak import refresh_tle
from app.ingestion.tle_store import latest_tle
from app.main import app
from app.orbit.pass_predictor import load_satellites
from app.storage.db import connect

# FIXTURE from the python-sgp4 docs (Dec 2019). NOT a current orbit.
GOOD = ("ISS (ZARYA)\n"
        "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991\n"
        "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482\n")
ALLOWED_SOURCES = {"VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"}


def test_config_is_consistent():
    sats = load_satellites()
    assert len(sats) == 6
    assert len({s["catnr"] for s in sats}) == len(sats)
    for s in sats:
        assert s["expected_name"] and s["half_swath_km"] > 0
        assert s.get("firms_source", "VIIRS_SNPP_NRT") in ALLOWED_SOURCES
    assert {s["firms_source"] for s in sats if "firms_source" in s} == ALLOWED_SOURCES


def test_name_matching_ignores_case_spaces_and_punctuation():
    assert name_matches("NOAA 20 (JPSS-1)", "NOAA-20")
    assert name_matches("SUOMI NPP", "Suomi NPP")
    assert name_matches("SENTINEL-2B", "SENTINEL-2B")
    assert not name_matches("SENTINEL-2A", "SENTINEL-2B")
    assert not name_matches("NOAA 21 (JPSS-2)", "NOAA-20")


def test_wrong_name_is_rejected_and_nothing_is_stored(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, expected_name="SENTINEL-2B")
    assert r["status"] == "failed" and "expected a name containing" in r["error"]
    assert latest_tle(conn, 25544) is None


def test_matching_name_is_accepted(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, expected_name="ISS")
    assert r["status"] == "ok"


def test_firms_task_ingests_each_configured_source_once(monkeypatch):
    monkeypatch.setattr("app.config.get_firms_key", lambda: "K")
    seen = []

    def fake_ingest(conn, key, source, bbox, day_range=2):
        seen.append(source)
        return {"status": "ok", "rows_valid": 1, "rows_new": 1, "rows_rejected": 0, "error": None}

    monkeypatch.setattr("app.ingestion.run_firms.ingest_firms", fake_ingest)
    status, message = scheduler.task_firms_all(None)
    assert status == "ok"
    assert sorted(seen) == sorted(ALLOWED_SOURCES)


def test_firms_task_reports_a_failing_source_by_name(monkeypatch):
    monkeypatch.setattr("app.config.get_firms_key", lambda: "K")

    def fake_ingest(conn, key, source, bbox, day_range=2):
        if source == "VIIRS_NOAA21_NRT":
            return {"status": "failed", "error": "HTTP 400"}
        return {"status": "ok", "rows_valid": 0, "rows_new": 0, "rows_rejected": 0, "error": None}

    monkeypatch.setattr("app.ingestion.run_firms.ingest_firms", fake_ingest)
    status, message = scheduler.task_firms_all(None)
    assert status == "failed" and "VIIRS_NOAA21_NRT: HTTP 400" in message


def test_second_passes_request_is_served_from_the_cache(tmp_path, monkeypatch):
    passes_api._CACHE.clear()
    calls = []

    def fake_connect():
        calls.append(1)
        return connect(tmp_path / "t.db")

    monkeypatch.setattr(passes_api, "connect", fake_connect)
    client = TestClient(app)
    a = client.get("/api/passes/next?hours=10&limit=2").json()
    b = client.get("/api/passes/next?hours=10&limit=2").json()
    assert a["generated_utc"] == b["generated_utc"] and len(calls) == 1
    passes_api._CACHE.clear()