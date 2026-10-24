
import math

MU_EARTH_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137

def orbital_period_s(altitude_km: float) -> float:
    """Calculate the time taken for one complete orbit."""

    semi_major_axis = EARTH_RADIUS_KM + altitude_km

    period = 2 * math.pi * math.sqrt(
        semi_major_axis**3 / MU_EARTH_KM3_S2
    )

    return period
