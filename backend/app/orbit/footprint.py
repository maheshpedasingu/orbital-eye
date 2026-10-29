import math

EARTH_RADIUS_KM = 6378.137


def footprint_radius_km(altitude_km: float, min_elevation_deg: float = 0.0) -> float:
    """Ground radius (km) of the visibility circle, spherical Earth.

    Units: altitude in km, elevation in degrees.
    """
    if altitude_km <= 0:
        raise ValueError("altitude_km must be > 0")
    if not 0.0 <= min_elevation_deg <= 90.0:
        raise ValueError("min_elevation_deg must be between 0 and 90")
    eps = math.radians(min_elevation_deg)
    r = EARTH_RADIUS_KM
    lam = math.acos(r * math.cos(eps) / (r + altitude_km)) - eps
    return r * lam
