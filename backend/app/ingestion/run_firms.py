from app.aoi import aoi_bbox
from app.config import get_firms_key
from app.ingestion.firms import fetch_area_csv, parse_detections, redact
from app.storage.db import connect, finish_run, save_detections, start_run


def ingest_firms(conn, key, source, bbox, day_range=2, fetcher=fetch_area_csv) -> dict:
    """Fetch, validate and store detections. Failures are logged, never hidden."""
    run_id = start_run(conn, source, bbox, day_range)
    header = None
    try:
        text = fetcher(key, source, bbox, day_range)
        lines = text.strip().splitlines()
        header = lines[0][:200] if lines else ""
        valid, rejected = parse_detections(text, bbox)
        new = save_detections(conn, run_id, source, valid)
        finish_run(conn, run_id, "ok", len(valid), len(rejected), new, None)
        return {"run_id": run_id, "status": "ok", "rows_valid": len(valid),
                "rows_rejected": len(rejected), "rows_new": new,
                "csv_header": header, "error": None}
    except Exception as exc:
        message = redact(str(exc), key)
        finish_run(conn, run_id, "failed", 0, 0, 0, message)
        return {"run_id": run_id, "status": "failed", "rows_valid": 0,
                "rows_rejected": 0, "rows_new": 0, "csv_header": header,
                "error": message}


if __name__ == "__main__":
    key = get_firms_key()
    if not key:
        raise SystemExit("FIRMS_MAP_KEY is not set (see .env.example)")
    conn = connect()
    result = ingest_firms(conn, key, "VIIRS_SNPP_NRT", aoi_bbox(pad_deg=0.5), day_range=2)
    print(result)
    for row in conn.execute(
        "SELECT acquired_utc, latitude_deg, longitude_deg, confidence_raw, frp_mw"
        " FROM fire_detections ORDER BY acquired_utc DESC LIMIT 5"
    ):
        print(tuple(row))
