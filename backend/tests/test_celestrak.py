from datetime import datetime, timedelta, timezone

import pytest

from app.ingestion.celestrak import parse_3le, parse_epoch, tle_checksum_ok
from app.ingestion.run_celestrak import refresh_tle
from app.ingestion.tle_store import latest_tle
from app.storage.db import connect

# FIXTURE from the python-sgp4 docs (Dec 2019). NOT a current orbit.
NAME = "ISS (ZARYA)"
L1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
L2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
GOOD = f"{NAME}\n{L1}\n{L2}\n"
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_checksums_of_the_fixture_are_valid_and_a_changed_digit_is_caught():
    assert tle_checksum_ok(L1) and tle_checksum_ok(L2)
    assert not tle_checksum_ok(L1.replace("19343", "19344"))


def test_epoch_of_the_fixture_matches_a_hand_calculation():
    # day 343.69339541 of 2019 = 9 Dec 2019, 16:38:29.36 UTC
    expected = datetime(2019, 12, 9, 16, 38, 29, 360000, tzinfo=timezone.utc)
    assert abs((parse_epoch(L1) - expected).total_seconds()) < 1.0


def test_two_digit_year_pivot_follows_the_tle_convention():
    assert parse_epoch("x" * 18 + "57001.00000000").year == 1957
    assert parse_epoch("x" * 18 + "56001.00000000").year == 2056


def test_good_response_is_parsed():
    tle = parse_3le(GOOD, 25544)
    assert tle["name"] == NAME and tle["catnr"] == 25544
    assert tle["epoch_utc"].startswith("2019-12-09T16:38:29")


def test_wrong_catalogue_number_is_rejected():
    with pytest.raises(ValueError, match="asked for"):
        parse_3le(GOOD, 99999)


def test_no_data_text_is_rejected_not_parsed():
    with pytest.raises(ValueError):
        parse_3le("No GP data found", 25544)


def test_checksum_failure_is_rejected():
    bad = GOOD.replace("19343.69339541", "19344.69339541")
    with pytest.raises(ValueError, match="checksum"):
        parse_3le(bad, 25544)


def test_refresh_stores_a_new_element_set(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0)
    assert r["status"] == "ok"
    assert latest_tle(conn, 25544)["name"] == NAME


def test_second_request_inside_the_interval_does_not_call_the_server(tmp_path):
    conn = connect(tmp_path / "t.db")
    calls = []

    def fetcher(catnr):
        calls.append(catnr)
        return GOOD

    refresh_tle(conn, 25544, fetcher=fetcher, now=T0)
    r = refresh_tle(conn, 25544, fetcher=fetcher, now=T0 + timedelta(hours=1))
    assert r["status"] == "throttled" and len(calls) == 1


def test_after_the_interval_an_unchanged_epoch_is_reported_unchanged(tmp_path):
    conn = connect(tmp_path / "t.db")
    refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0)
    r = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0 + timedelta(hours=13))
    assert r["status"] == "unchanged"
    assert conn.execute("SELECT COUNT(*) FROM tle_sets").fetchone()[0] == 1


def test_failures_are_logged_and_also_throttle_retries(tmp_path):
    conn = connect(tmp_path / "t.db")

    def broken(catnr):
        raise RuntimeError("network down")

    r = refresh_tle(conn, 25544, fetcher=broken, now=T0)
    assert r["status"] == "failed" and "network down" in r["error"]
    again = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0 + timedelta(hours=1))
    assert again["status"] == "throttled"
    assert latest_tle(conn, 25544) is None


def test_force_bypasses_the_interval(tmp_path):
    conn = connect(tmp_path / "t.db")
    refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0)
    r = refresh_tle(conn, 25544, fetcher=lambda c: GOOD, now=T0 + timedelta(minutes=5),
                    force=True)
    assert r["status"] == "unchanged"