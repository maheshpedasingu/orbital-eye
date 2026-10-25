import math


from app.orbit.kepler import (
    ecef_to_lat_lon_deg,
    eci_to_ecef_km,
    ground_track,
    orbital_period_s,
    position_eci_km,
)

from app.orbit.kepler import orbital_period_s, position_eci_km


def test_period_at_700km_is_about_98_6_minutes():
    period_min = orbital_period_s(700.0) / 60.0
    assert abs(period_min - 98.8) < 0.5


def test_higher_orbit_has_longer_period():
    assert orbital_period_s(1000.0) > orbital_period_s(500.0)


def test_geostationary_altitude_gives_one_sidereal_day():
    # 35786 km altitude should give ~86164 s (one sidereal day)
    assert abs(orbital_period_s(35786.0) - 86164.0) < 60.0


def test_start_is_at_x_axis():
    x, y, z = position_eci_km(700.0, 98.0, 0.0)
    assert abs(x - (6378.137 + 700.0)) < 1e-6
    assert abs(y) < 1e-6 and abs(z) < 1e-6


def test_distance_from_center_is_constant():
    a = 6378.137 + 700.0
    for t in (0, 500, 1234, 3000, 5000):
        x, y, z = position_eci_km(700.0, 98.0, t)
        assert abs(math.sqrt(x * x + y * y + z * z) - a) < 1e-6


def test_returns_to_start_after_one_period():
    period = orbital_period_s(700.0)
    x, y, z = position_eci_km(700.0, 98.0, period)
    assert abs(x - (6378.137 + 700.0)) < 1e-6


def test_equator_point_has_zero_latitude():
    lat, lon = ecef_to_lat_lon_deg(7000.0, 0.0, 0.0)
    assert abs(lat) < 1e-9 and abs(lon) < 1e-9


def test_north_pole_is_90_degrees():
    lat, _ = ecef_to_lat_lon_deg(0.0, 0.0, 7000.0)
    assert abs(lat - 90.0) < 1e-9


def test_no_rotation_at_t0():
    assert eci_to_ecef_km(1.0, 2.0, 3.0, 0.0) == (1.0, 2.0, 3.0)


def test_one_sidereal_day_returns_to_same_point():
    x, y, z = eci_to_ecef_km(7000.0, 0.0, 0.0, 86164.0905)
    assert abs(x - 7000.0) < 1.0 and abs(y) < 1.0


def test_ground_track_point_count():
    points = ground_track(700.0, 98.0, 600.0, 60.0)
    assert len(points) == 11


def test_ground_track_latitude_never_exceeds_limit():
    # Max latitude of an orbit with inclination 98 deg is 180 - 98 = 82 deg
    points = ground_track(700.0, 98.0, 6000.0, 30.0)
    assert max(abs(p["lat_deg"]) for p in points) <= 82.0 + 1e-6


def test_ground_track_point_count():
    points = ground_track(700.0, 98.0, 600.0, 60.0)
    assert len(points) == 11


def test_ground_track_latitude_never_exceeds_limit():
    # Max latitude of an orbit with inclination 98 deg is 180 - 98 = 82 deg
    points = ground_track(700.0, 98.0, 6000.0, 30.0)
    assert max(abs(p["lat_deg"]) for p in points) <= 82.0 + 1e-6
