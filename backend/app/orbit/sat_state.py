import math
from datetime import datetime, timedelta

from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.geodetic import ecef_to_geodetic
from app.orbit.propagate import propagate_tle


def argument_of_latitude_deg(r, v):
    """Orbital phase: angle from the ascending node to the satellite, 0 to 360.

    0 = ascending node, 90 = northernmost point, 180 = descending node,
    270 = southernmost point. Returns None for an equatorial orbit (no node).
    """
    hx = r[1] * v[2] - r[2] * v[1]
    hy = r[2] * v[0] - r[0] * v[2]
    nx, ny = -hy, hx                      # node vector = z-axis x h
    nn = math.hypot(nx, ny)
    rn = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
    if nn < 1e-9 or rn == 0:
        return None
    c = (nx * r[0] + ny * r[1]) / (nn * rn)
    u = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    return u if r[2] >= 0 else 360.0 - u


def satellite_state(line1, line2, when: datetime, propagate=propagate_tle) -> dict:
    """Position, altitude, speed and orbital phase at one instant (SGP4)."""
    r, v = propagate(line1, line2, when)
    lat, lon, alt = ecef_to_geodetic(*teme_to_ecef_km(r, gmst_rad(when)))
    return {
        "time_utc": when.isoformat(),
        "lat_deg": lat,
        "lon_deg": lon,
        "alt_km": alt,
        "speed_km_s": math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2),
        "argument_of_latitude_deg": argument_of_latitude_deg(r, v),
        "ascending": v[2] > 0,
    }


def ground_track(line1, line2, start_utc: datetime, minutes: float, step_s: float,
                 propagate=propagate_tle) -> list[dict]:
    """Sub-satellite points from start_utc for the given number of minutes."""
    if minutes <= 0 or step_s <= 0:
        raise ValueError("minutes and step_s must be > 0")
    duration = minutes * 60.0
    points = []
    for k in range(int(duration // step_s) + 1):
        t = k * step_s
        p = satellite_state(line1, line2, start_utc + timedelta(seconds=t), propagate)
        p["t_s"] = t
        points.append(p)
    return points
