import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.aoi import load_aoi
from app.geo_utils import haversine_km
from app.ingestion.tle_store import ensure_tle_tables, latest_tle
from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.geodetic import ecef_to_geodetic
from app.orbit.propagate import propagate_tle

SATELLITES_PATH = Path(__file__).resolve().parents[3] / "config" / "satellites.json"
MAX_TLE_AGE_DAYS = 14.0
DAY_START_H = 6.0
DAY_END_H = 18.0


def load_satellites(path: Path = SATELLITES_PATH) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        sats = json.load(f)["satellites"]
    for s in sats:
        if not isinstance(s["catnr"], int) or s["half_swath_km"] <= 0:
            raise ValueError(f"bad satellite entry: {s.get('name')!r}")
    return sats


def local_solar_hour(when: datetime, lon_deg: float) -> float:
    """Mean local solar time (hours, 0 to 24) from UTC and longitude."""
    return (when.hour + when.minute / 60.0 + when.second / 3600.0 + lon_deg / 15.0) % 24.0


def is_daytime(hour: float) -> bool:
    return DAY_START_H <= hour < DAY_END_H


def choose_step_s(half_swath_km: float) -> float:
    """Narrow swaths need a fine step so an edge-grazing pass is not missed."""
    return 5.0 if half_swath_km < 400.0 else 30.0


def find_opportunities(line1, line2, start_utc, hours, lat_deg, lon_deg,
                       half_swath_km, daylight_only=False, step_s=None) -> list[dict]:
    """Windows when the sub-satellite point is within half_swath_km of a target.

    Units: distances km, times UTC. min_distance_km is the nearest SAMPLE, so it
    can exceed the true minimum by a few km (more for a coarse step).
    """
    if hours <= 0:
        raise ValueError("hours must be > 0")
    step = step_s if step_s is not None else choose_step_s(half_swath_km)
    if step <= 0:
        raise ValueError("step_s must be > 0")
    n = int(hours * 3600.0 // step) + 1
    last_when = start_utc + timedelta(seconds=(n - 1) * step)

    windows, cur = [], None
    for k in range(n):
        when = start_utc + timedelta(seconds=k * step)
        r, _ = propagate_tle(line1, line2, when)
        s_lat, s_lon, _ = ecef_to_geodetic(*teme_to_ecef_km(r, gmst_rad(when)))
        d = haversine_km(lat_deg, lon_deg, s_lat, s_lon)
        if d <= half_swath_km:
            if cur is None:
                cur = {"start": when, "end": when, "tca": when, "min_d": d}
            cur["end"] = when
            if d < cur["min_d"]:
                cur["tca"], cur["min_d"] = when, d
        elif cur is not None:
            windows.append(cur)
            cur = None
    if cur is not None:
        windows.append(cur)

    out = []
    for w in windows:
        hour = local_solar_hour(w["tca"], lon_deg)
        daytime = is_daytime(hour)
        if daylight_only and not daytime:
            continue
        out.append({
            "start_utc": w["start"].isoformat(),
            "end_utc": w["end"].isoformat(),
            "tca_utc": w["tca"].isoformat(),
            "min_distance_km": round(w["min_d"], 1),
            "local_solar_hour_at_aoi": round(hour, 2),
            "daytime": daytime,
            "partial": w["start"] == start_utc or w["end"] == last_when,
        })
    return out


def predict_all(conn, now=None, hours=72.0, limit=5, finder=find_opportunities,
                satellites=None) -> dict:
    """Opportunities over the AOI centre for every configured satellite."""
    ensure_tle_tables(conn)
    now = now or datetime.now(timezone.utc)
    props = load_aoi()["features"][0]["properties"]
    lat, lon = props["centre_lat_deg"], props["centre_lon_deg"]

    results = []
    for sat in (satellites if satellites is not None else load_satellites()):
        entry = {k: sat[k] for k in
                 ("catnr", "name", "instrument", "purpose", "half_swath_km", "daylight_only")
                 if k in sat}
        row = latest_tle(conn, sat["catnr"])
        if row is None:
            entry.update(
                status="no_element_set", opportunities=[],
                message="No element set stored. Run: python -m app.ingestion.run_celestrak")
        else:
            age = (now - datetime.fromisoformat(row["epoch_utc"])).total_seconds() / 86400.0
            entry.update(tle_name=row["name"], tle_epoch_utc=row["epoch_utc"],
                         tle_retrieved_utc=row["retrieved_utc"], tle_age_days=round(age, 2))
            if age > MAX_TLE_AGE_DAYS:
                entry.update(
                    status="stale_element_set", opportunities=[],
                    message=f"Element set is {age:.1f} days old (limit {MAX_TLE_AGE_DAYS:g}); "
                            "no prediction is made. Refresh it.")
            else:
                opps = finder(row["line1"], row["line2"], now, hours, lat, lon,
                              sat["half_swath_km"], sat.get("daylight_only", False))
                entry.update(status="ok", opportunities=opps[:limit])
        results.append(entry)

    return {
        "data_origin": "PROPAGATED_FROM_REAL_TLE",
        "generated_utc": now.isoformat(),
        "hours": hours,
        "target": {"name": props["name"], "lat_deg": lat, "lon_deg": lon},
        "note": "Geometric opportunities from real orbital elements: the ground track passes "
                "within half a swath of the AOI centre. Not a guarantee of data. "
                "Daytime is a crude 06:00 to 18:00 mean local solar time proxy.",
        "satellites": results,
    }