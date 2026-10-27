import math
from datetime import datetime, timezone

from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.kepler import ecef_to_lat_lon_deg
from app.orbit.propagate import propagate_tle

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


def test_gmst_matches_vallado_example():
    # Vallado, Fundamentals of Astrodynamics, Example 3-5:
    # 1992-08-20 12:14:00 UT1 -> GMST = 152.578787810 deg
    when = datetime(1992, 8, 20, 12, 14, 0, tzinfo=timezone.utc)
    assert abs(math.degrees(gmst_rad(when)) - 152.578787810) < 1e-4


def test_rotation_preserves_distance():
    r = (4000.0, 3000.0, 5000.0)
    x, y, z = teme_to_ecef_km(r, 1.234)
    assert abs(math.sqrt(x * x + y * y + z * z) - math.sqrt(sum(c * c for c in r))) < 1e-9


def test_iss_latitude_within_inclination():
    when = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    r, _ = propagate_tle(LINE1, LINE2, when)
    lat, lon = ecef_to_lat_lon_deg(*teme_to_ecef_km(r, gmst_rad(when)))
    assert abs(lat) <= 51.65 + 0.3
    assert -180.0 <= lon <= 180.0
