import math

from app.orbit.passes import A_KM, E2


def ecef_to_geodetic(x_km: float, y_km: float, z_km: float) -> tuple[float, float, float]:
    """WGS-84 geodetic (latitude deg, longitude deg, height km) from an Earth-fixed position (km)."""
    lon = math.atan2(y_km, x_km)
    p = math.hypot(x_km, y_km)
    lat = math.atan2(z_km, p * (1.0 - E2))
    for _ in range(20):
        sin_lat = math.sin(lat)
        n = A_KM / math.sqrt(1.0 - E2 * sin_lat * sin_lat)
        h = (p * math.cos(lat) + z_km * sin_lat
             - A_KM * math.sqrt(1.0 - E2 * sin_lat * sin_lat))
        new_lat = math.atan2(z_km, p * (1.0 - E2 * n / (n + h)))
        converged = abs(new_lat - lat) < 1e-13
        lat = new_lat
        if converged:
            break
    sin_lat = math.sin(lat)
    h = (p * math.cos(lat) + z_km * sin_lat
         - A_KM * math.sqrt(1.0 - E2 * sin_lat * sin_lat))
    return math.degrees(lat), math.degrees(lon), h