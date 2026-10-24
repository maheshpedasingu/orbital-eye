
import math


OMEGA_EARTH_RAD_S = 7.2921159e-5   # Earth's rotation rate, rad/s
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


def eci_to_ecef_km(
    x: float, y: float, z: float, t_s: float
) -> tuple[float, float, float]:
    """Rotate an inertial position (km) into the Earth-fixed frame,
    t_s seconds after t = 0."""
    angle = OMEGA_EARTH_RAD_S * t_s            # how far Earth has turned, rad

    x_ecef = x * math.cos(angle) + y * math.sin(angle)
    y_ecef = -x * math.sin(angle) + y * math.cos(angle)
    z_ecef = z                                  # rotation is about the z-axis

    return (x_ecef, y_ecef, z_ecef)


def ecef_to_lat_lon_deg(x: float, y: float, z: float) -> tuple[float, float]:
    """Spherical-Earth latitude and longitude, in degrees."""
    r = math.sqrt(x * x + y * y + z * z)        # distance from Earth's center, km

    lat = math.degrees(math.asin(z / r))        # angle above/below the equator
    lon = math.degrees(math.atan2(y, x))        # angle east/west of the x-axis

    return (lat, lon)