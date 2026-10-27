import math
from datetime import datetime

from sgp4.api import jday


def gmst_rad(when_utc: datetime) -> float:
    """Greenwich Mean Sidereal Time in radians (UT1 approximated by UTC)."""
    seconds = when_utc.second + when_utc.microsecond / 1e6
    jd, fr = jday(
        when_utc.year, when_utc.month, when_utc.day,
        when_utc.hour, when_utc.minute, seconds,
    )
    t = ((jd - 2451545.0) + fr) / 36525.0  # Julian centuries since J2000
    gmst_s = (
        67310.54841
        + (876600.0 * 3600.0 + 8640184.812866) * t
        + 0.093104 * t * t
        - 6.2e-6 * t ** 3
    )
    return math.radians((gmst_s / 240.0) % 360.0)  # 240 s of time = 1 degree


def teme_to_ecef_km(
    r_km: tuple[float, float, float], theta_rad: float
) -> tuple[float, float, float]:
    """Rotate a position about the z-axis by the sidereal angle (km)."""
    x, y, z = r_km
    c, s = math.cos(theta_rad), math.sin(theta_rad)
    return (x * c + y * s, -x * s + y * c, z)
