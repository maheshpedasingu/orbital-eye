
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

def position_eci_km(
    altitude_km: float, inclination_deg: float, t_s: float
) -> tuple[float, float, float]:
    """Position (x, y, z) in km in an inertial frame."""

    a = EARTH_RADIUS_KM + altitude_km
    theta = 2 * math.pi * t_s / orbital_period_s(altitude_km)
    i = math.radians(inclination_deg)

    x_plane = a * math.cos(theta)
    y_plane = a * math.sin(theta)

    x = x_plane
    y = y_plane * math.cos(i)
    z = y_plane * math.sin(i)

    return (x, y, z)