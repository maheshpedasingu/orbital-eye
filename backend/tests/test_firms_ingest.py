import pytest

from app.ingestion.firms import parse_detections
from app.ingestion.run_firms import ingest_firms
from app.storage.db import connect

BBOX = (80.0, 16.0, 81.0, 17.0)
HEADER = "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight"
# PARSER TEST FIXTURE: invented rows, NOT NASA data.
GOOD = "16.50,80.60,330.1,0.4,0.4,2026-01-01,0930,N,VIIRS,n,2.0NRT,290.2,5.5,D"
OUTSIDE = "30.00,80.60,330.1,0.4,0.4,2026-01-01,0930,N,VIIRS,n,2.0NRT,290.2,5.5,D"
BAD_LAT = "abc,80.60,330.1,0.4,0.4,2026-01-01,0930,N,VIIRS,n,2.0NRT,290.2,5.5,D"
BAD_TIME = "16.50,80.60,330.1,0.4,0.4,2026-01-01,2561,N,VIIRS,n,2.0NRT,290.2,5.5,D"


def test_valid_row_is_parsed_with_utc_time():
    valid, rejected = parse_detections(HEADER + "\n" + GOOD, BBOX)
    assert rejected == []
    assert valid[0]["acquired_utc"] == "2026-01-01T09:30:00+00:00"
    assert valid[0]["frp_mw"] == 5.5


def test_bad_rows_are_rejected_with_reasons():
    text = "\n".join([HEADER, GOOD, OUTSIDE, BAD_LAT, BAD_TIME])
    valid, rejected = parse_detections(text, BBOX)
    assert len(valid) == 1
    assert len(rejected) == 3


def test_non_csv_response_raises():
    with pytest.raises(ValueError):
        parse_detections("Invalid MAP_KEY.", BBOX)


def test_header_only_means_no_detections():
    valid, rejected = parse_detections(HEADER, BBOX)
    assert valid == [] and rejected == []


def test_second_ingest_of_same_data_adds_no_new_rows(tmp_path):
    conn = connect(tmp_path / "t.db")
    fake = lambda key, source, bbox, days: HEADER + "\n" + GOOD
    first = ingest_firms(conn, "KEY", "VIIRS_SNPP_NRT", BBOX, 1, fetcher=fake)
    second = ingest_firms(conn, "KEY", "VIIRS_SNPP_NRT", BBOX, 1, fetcher=fake)
    assert first["rows_new"] == 1
    assert second["rows_new"] == 0


def test_failed_fetch_is_logged_and_stores_nothing(tmp_path):
    conn = connect(tmp_path / "t.db")

    def broken(key, source, bbox, days):
        raise RuntimeError("network down, key=SECRET")

    result = ingest_firms(conn, "SECRET", "VIIRS_SNPP_NRT", BBOX, 1, fetcher=broken)
    assert result["status"] == "failed"
    assert "SECRET" not in result["error"]
    assert conn.execute("SELECT COUNT(*) FROM fire_detections").fetchone()[0] == 0
