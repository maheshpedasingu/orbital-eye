import math
from datetime import datetime, timedelta

from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.propagate import propagate_tle

A_KM = 6378.137                 # WGS-84 equatorial radius, km
F = 1.0 / 298.257223563         # WGS-84 flattening
E2 = F * (2.0 - F)              # first eccentricity squared


def observer_ecef_km(
    lat_deg: float, lon_deg: float, height_km: float = 0.0
) -> tuple[float, float, float]:
    """Observer position in the Earth-fixed frame (km), WGS-84 geodetic input."""
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    n = A_KM / math.sqrt(1.0 - E2 * math.sin(lat) ** 2)
    x = (n + height_km) * math.cos(lat) * math.cos(lon)
    y = (n + height_km) * math.cos(lat) * math.sin(lon)
    z = (n * (1.0 - E2) + height_km) * math.sin(lat)
    return (x, y, z)


def elevation_deg(
    sat_ecef_km: tuple[float, float, float], lat_deg: float, lon_deg: float
) -> float:
    """Elevation of a satellite above the observer's local horizon, degrees."""
    ox, oy, oz = observer_ecef_km(lat_deg, lon_deg)
    rx, ry, rz = (
        sat_ecef_km[0] - ox, sat_ecef_km[1] - oy, sat_ecef_km[2] - oz
    )
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    up = (
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    )
    rng = math.sqrt(rx * rx + ry * ry + rz * rz)
    s = (rx * up[0] + ry * up[1] + rz * up[2]) / rng
    return math.degrees(math.asin(max(-1.0, min(1.0, s))))


def find_passes(
    line1: str,
    line2: str,
    start_utc: datetime,
    duration_s: float,
    lat_deg: float,
    lon_deg: float,
    min_elevation_deg: float = 0.0,
    step_s: float = 30.0,
) -> list[dict]:
    """Passes above min_elevation_deg. Times are accurate to step_s."""
    if step_s <= 0 or duration_s < 0:
        raise ValueError("step_s must be > 0 and duration_s must be >= 0")
    passes: list[dict] = []
    current = None
    for k in range(int(duration_s // step_s) + 1):
        when = start_utc + timedelta(seconds=k * step_s)
        r, _ = propagate_tle(line1, line2, when)
        el = elevation_deg(teme_to_ecef_km(r, gmst_rad(when)), lat_deg, lon_deg)
        if el >= min_elevation_deg:
            if current is None:
                current = {"start_utc": when, "end_utc": when,
                           "max_elevation_deg": el, "max_time_utc": when}
            current["end_utc"] = when
            if el > current["max_elevation_deg"]:
                current["max_elevation_deg"] = el
                current["max_time_utc"] = when
        elif current is not None:
            passes.append(current)
            current = None
    if current is not None:
        passes.append(current)
    return [
        {
            "start_utc": p["start_utc"].isoformat(),
            "end_utc": p["end_utc"].isoformat(),
            "max_elevation_deg": p["max_elevation_deg"],
            "max_time_utc": p["max_time_utc"].isoformat(),
        }
        for p in passes
    ]
