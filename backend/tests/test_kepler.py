from app.orbit.kepler import orbital_period_s


def test_period_at_700km_is_about_98_6_minutes():
    period_min = orbital_period_s(700.0) / 60.0
    assert abs(period_min - 98.8) < 0.5


def test_higher_orbit_has_longer_period():
    assert orbital_period_s(1000.0) > orbital_period_s(500.0)


def test_geostationary_altitude_gives_one_sidereal_day():
    # 35786 km altitude should give ~86164 s (one sidereal day)
    assert abs(orbital_period_s(35786.0) - 86164.0) < 60.0