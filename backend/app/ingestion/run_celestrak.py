import argparse
from datetime import datetime, timedelta, timezone

from app.ingestion.celestrak import (
    GP_URL, MIN_FETCH_INTERVAL_HOURS, fetch_3le, parse_3le,
)
from app.ingestion.tle_store import (
    ensure_tle_tables, last_attempt, latest_tle, record_attempt, save_tle,
)
from app.storage.db import connect

# Catalogue numbers are from memory: the printed name is the real check.
DEFAULT_SATELLITES = {37849: "SUOMI", 42063: "SENTINEL-2B"}


def refresh_tle(conn, catnr, force=False, fetcher=fetch_3le, now=None,
                min_hours=MIN_FETCH_INTERVAL_HOURS) -> dict:
    """Fetch and store the current element set, at most once per interval."""
    ensure_tle_tables(conn)
    now = now or datetime.now(timezone.utc)
    last = last_attempt(conn, catnr)
    if not force and last is not None and now - last < timedelta(hours=min_hours):
        return {"status": "throttled", "catnr": catnr,
                "last_attempt_utc": last.isoformat()}
    try:
        tle = parse_3le(fetcher(catnr), catnr)
    except Exception as exc:
        record_attempt(conn, catnr, now, "failed", str(exc))
        return {"status": "failed", "catnr": catnr, "error": str(exc)}
    record_attempt(conn, catnr, now, "ok", None)
    is_new = save_tle(conn, tle, now, f"{GP_URL}?CATNR={catnr}&FORMAT=3LE")
    return {"status": "ok" if is_new else "unchanged", **tle}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catnr", type=int, action="append",
                        help="NORAD catalogue number (repeatable)")
    parser.add_argument("--force", action="store_true",
                        help="ignore the 12-hour minimum interval (use sparingly)")
    args = parser.parse_args()
    catnrs = args.catnr or list(DEFAULT_SATELLITES)

    conn = connect()
    for catnr in catnrs:
        result = refresh_tle(conn, catnr, force=args.force)
        print(result["status"].upper(), catnr, result.get("name", ""))
        if result["status"] in ("ok", "unchanged"):
            epoch = datetime.fromisoformat(result["epoch_utc"])
            age_days = (datetime.now(timezone.utc) - epoch).total_seconds() / 86400
            print(f"  epoch {result['epoch_utc']}  ({age_days:.1f} days old)")
            if age_days > 14:
                print("  WARNING: element set is older than 14 days; predictions degrade.")
            expected = DEFAULT_SATELLITES.get(catnr)
            if expected and expected not in result["name"].upper():
                print(f"  WARNING: expected a name containing {expected}; "
                      "check the catalogue number before trusting this.")
        elif result["status"] == "throttled":
            row = latest_tle(conn, catnr)
            print("  not fetched (last attempt", result["last_attempt_utc"] + ").")
            if row:
                print("  stored:", row["name"], "epoch", row["epoch_utc"])
        else:
            print("  error:", result["error"])