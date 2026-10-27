from datetime import datetime, timedelta

from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.kepler import ecef_to_lat_lon_deg
from app.orbit.propagate import propagate_tle


def tle_ground_track(
    line1: str, line2: str, start_utc: datetime, duration_s: float, step_s: float
) -> list[dict]:
    """Sub-satellite points from SGP4. Units: degrees, km, seconds.

    Latitude is spherical-Earth (see SCIENCE_AND_ASSUMPTIONS).
    """
    if step_s <= 0 or duration_s < 0:
        raise ValueError("step_s must be > 0 and duration_s must be >= 0")
    points = []
    for k in range(int(duration_s // step_s) + 1):
        t = k * step_s
        when = start_utc + timedelta(seconds=t)
        r, _ = propagate_tle(line1, line2, when)
        x, y, z = teme_to_ecef_km(r, gmst_rad(when))
        lat, lon = ecef_to_lat_lon_deg(x, y, z)
        radius = (x * x + y * y + z * z) ** 0.5
        points.append({
            "t_s": t,
            "time_utc": when.isoformat(),
            "lat_deg": lat,
            "lon_deg": lon,
            "alt_km": radius - 6378.137,
        })
    return points
