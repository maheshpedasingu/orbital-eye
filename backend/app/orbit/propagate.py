from datetime import datetime

from sgp4.api import Satrec, jday


def propagate_tle(
    line1: str, line2: str, when_utc: datetime
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Propagate a TLE to a UTC time with SGP4.

    Returns (position_km, velocity_km_s) in the TEME frame.
    """
    sat = Satrec.twoline2rv(line1, line2)
    seconds = when_utc.second + when_utc.microsecond / 1e6
    jd, fr = jday(
        when_utc.year, when_utc.month, when_utc.day,
        when_utc.hour, when_utc.minute, seconds,
    )
    error_code, r, v = sat.sgp4(jd, fr)
    if error_code != 0:
        raise ValueError(f"SGP4 failed with error code {error_code}")
    return r, v
