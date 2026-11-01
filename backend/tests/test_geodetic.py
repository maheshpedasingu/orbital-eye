import math
from datetime import datetime, timedelta, timezone

import pytest

from app.orbit.frames import gmst_rad, teme_to_ecef_km
from app.orbit.geodetic import ecef_to_geodetic
from app.orbit.passes import A_KM, F, observer_ecef_km
from app.orbit.propagate import propagate_tle
from app.orbit.validation import closest_approach

# FIXTURE from the python-sgp4 docs (Dec 2019). NOT a current orbit.
L1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
L2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"


@pytest.mark.parametrize("lat,lon,h", [
    (16.506, 80.648, 0.0), (-33.9, 151.2, 0.1), (78.0, -100.0, 700.0), (0.0, 179.9, 35786.0),
])
def test_geodetic_conversion_round_trips_the_observer_formula(lat, lon, h):
    got = ecef_to_geodetic(*observer_ecef_km(lat, lon, h))
    assert abs(got[0] - lat) < 1e-8 and abs(got[1] - lon) < 1e-8 and abs(got[2] - h) < 1e-6


def test_known_points_equator_and_pole():
    lat, lon, h = ecef_to_geodetic(A_KM + 500.0, 0.0, 0.0)
    assert abs(lat) < 1e-9 and abs(h - 500.0) < 1e-9
    lat, _, h = ecef_to_geodetic(0.0, 0.0, A_KM * (1.0 - F))
    assert abs(lat - 90.0) < 1e-9 and abs(h) < 1e-6


def test_geocentric_latitude_is_lower_than_geodetic_by_about_0_19_degrees_at_45():
    x, y, z = observer_ecef_km(45.0, 0.0, 0.0)
    geocentric = math.degrees(math.atan2(z, math.hypot(x, y)))
    assert 44.80 < geocentric < 44.82


def test_closest_approach_finds_a_point_the_satellite_really_passes_over():
    t = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)
    r, _ = propagate_tle(L1, L2, t)
    lat, lon, _ = ecef_to_geodetic(*teme_to_ecef_km(r, gmst_rad(t)))
    res = closest_approach(L1, L2, lat, lon, t + timedelta(seconds=30),
                           window_s=120.0, step_s=1.0)
    assert res["min_distance_km"] < 0.01
    assert res["offset_s"] == -30.0