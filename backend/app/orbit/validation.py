import argparse
from datetime import datetime, timedelta, timezone

from app.geo_utils import haversine_km
from app.ingestion.tle_store import ensure_tle_tables, latest_tle
from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.geodetic import ecef_to_geodetic
from app.orbit.propagate import propagate_tle
from app.storage.db import connect


def closest_approach(line1, line2, lat_deg, lon_deg, around_utc,
                     window_s=300.0, step_s=1.0) -> dict:
    """Find when the sub-satellite point is closest to a target, within a window.

    Units: distances in km, offsets in seconds, angles in degrees.
    """
    if step_s <= 0 or window_s < 0:
        raise ValueError("step_s must be > 0 and window_s must be >= 0")
    best = None
    for k in range(int(2 * window_s / step_s) + 1):
        when = around_utc + timedelta(seconds=-window_s + k * step_s)
        r, _ = propagate_tle(line1, line2, when)
        s_lat, s_lon, s_h = ecef_to_geodetic(*teme_to_ecef_km(r, gmst_rad(when)))
        dist = haversine_km(lat_deg, lon_deg, s_lat, s_lon)
        if best is None or dist < best["min_distance_km"]:
            solar_h = (when.hour + when.minute / 60 + when.second / 3600 + s_lon / 15.0) % 24
            best = {
                "tca_utc": when.isoformat(),
                "offset_s": (when - around_utc).total_seconds(),
                "min_distance_km": dist,
                "sat_lat_deg": s_lat,
                "sat_lon_deg": s_lon,
                "sat_altitude_km": s_h,
                "local_solar_time_h": solar_h,
            }
    return best


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catnr", type=int, required=True)
    parser.add_argument("--time", required=True, help="observed time, UTC, ISO 8601")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--max-distance-km", type=float, required=True)
    parser.add_argument("--max-offset-s", type=float, required=True)
    args = parser.parse_args()

    conn = connect()
    ensure_tle_tables(conn)
    row = latest_tle(conn, args.catnr)
    if row is None:
        print("No stored element set. Run: python -m app.ingestion.run_celestrak")
        return 2

    observed = _parse_time(args.time)
    epoch = datetime.fromisoformat(row["epoch_utc"])
    span_days = (observed - epoch).total_seconds() / 86400
    res = closest_approach(row["line1"], row["line2"], args.lat, args.lon, observed)

    print(f"Satellite: {row['name']} ({args.catnr})")
    print(f"Element set epoch: {row['epoch_utc']}  (retrieved {row['retrieved_utc']})")
    print(f"Observed time: {observed.isoformat()}  ({span_days:+.2f} days from the epoch)")
    print(f"Target: {args.lat:.4f} N, {args.lon:.4f} E")
    print("Closest approach of the sub-satellite point:")
    print(f"  time   {res['tca_utc']}  (offset {res['offset_s']:+.0f} s from observed)")
    print(f"  distance from ground track {res['min_distance_km']:.1f} km")
    print(f"  satellite then at {res['sat_lat_deg']:.3f} N, {res['sat_lon_deg']:.3f} E, "
          f"altitude {res['sat_altitude_km']:.0f} km")
    hh = int(res["local_solar_time_h"])
    mm = int((res["local_solar_time_h"] - hh) * 60)
    print(f"  mean local solar time at the sub-satellite point: {hh:02d}:{mm:02d}")

    ok_dist = res["min_distance_km"] <= args.max_distance_km
    ok_time = abs(res["offset_s"]) <= args.max_offset_s
    print(f"Distance criterion (<= {args.max_distance_km:g} km): {'PASS' if ok_dist else 'FAIL'}")
    print(f"Timing criterion (<= {args.max_offset_s:g} s):   {'PASS' if ok_time else 'FAIL'}")
    return 0 if (ok_dist and ok_time) else 1


if __name__ == "__main__":
    raise SystemExit(main())