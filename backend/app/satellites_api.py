import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.ingestion.tle_store import ensure_tle_tables, latest_tle
from app.orbit.pass_predictor import MAX_TLE_AGE_DAYS, load_satellites
from app.orbit.sat_state import ground_track, satellite_state
from app.storage.db import connect

router = APIRouter()
DATA_ORIGIN = "PROPAGATED_FROM_REAL_TLE"


def _entry(sat, row, now):
    """Satellite description plus element-set status. Returns (entry, usable)."""
    entry = {k: sat[k] for k in ("catnr", "name", "instrument", "purpose") if k in sat}
    if row is None:
        entry.update(status="no_element_set",
                     message="No element set stored. Run: python -m app.ingestion.run_celestrak")
        return entry, False
    age = (now - datetime.fromisoformat(row["epoch_utc"])).total_seconds() / 86400.0
    entry.update(tle_name=row["name"], tle_epoch_utc=row["epoch_utc"],
                 tle_retrieved_utc=row["retrieved_utc"], tle_age_days=round(age, 2))
    if age > MAX_TLE_AGE_DAYS:
        entry.update(status="stale_element_set",
                     message=f"Element set is {age:.1f} days old (limit {MAX_TLE_AGE_DAYS:g}); "
                             "no position is given. Refresh it.")
        return entry, False
    entry["status"] = "ok"
    return entry, True


def build_state(conn, now=None, satellites=None, state_fn=satellite_state) -> dict:
    ensure_tle_tables(conn)
    now = now or datetime.now(timezone.utc)
    out = []
    for sat in (satellites if satellites is not None else load_satellites()):
        row = latest_tle(conn, sat["catnr"])
        entry, usable = _entry(sat, row, now)
        if usable:
            entry["state"] = state_fn(row["line1"], row["line2"], now)
        out.append(entry)
    return {
        "data_origin": DATA_ORIGIN,
        "generated_utc": now.isoformat(),
        "note": "Computed with SGP4 from real CelesTrak element sets. Accuracy "
                "degrades with element-set age. speed_km_s is inertial (TEME), "
                "not ground speed.",
        "satellites": out,
    }


def build_track(conn, catnr, now=None, minutes=95.0, step_s=60.0, satellites=None,
                track_fn=ground_track):
    """Ground track for one satellite, or None if the catalogue number is unknown."""
    ensure_tle_tables(conn)
    now = now or datetime.now(timezone.utc)
    sat = next((s for s in (satellites if satellites is not None else load_satellites())
                if s["catnr"] == catnr), None)
    if sat is None:
        return None
    row = latest_tle(conn, catnr)
    entry, usable = _entry(sat, row, now)
    entry.update(data_origin=DATA_ORIGIN, generated_utc=now.isoformat(),
                 minutes=minutes, step_s=step_s, points=[])
    if usable:
        entry["points"] = track_fn(row["line1"], row["line2"], now, minutes, step_s)
    return entry


_CACHE: dict = {}
CACHE_SECONDS = 5.0


@router.get("/api/satellites/state")
def get_state():
    """Current real-satellite state, propagated from stored element sets."""
    hit = _CACHE.get("state")
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    conn = connect()
    try:
        result = build_state(conn)
    finally:
        conn.close()
    _CACHE["state"] = (time.time(), result)
    return result


@router.get("/api/satellites/{catnr}/track")
def get_track(catnr: int, minutes: float = Query(95.0, gt=0, le=360),
              step_s: float = Query(60.0, ge=10, le=600)):
    """Ground track from now for one satellite. Split lines where longitude wraps."""
    conn = connect()
    try:
        result = build_track(conn, catnr, minutes=minutes, step_s=step_s)
    finally:
        conn.close()
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown satellite catalogue number")
    return result
