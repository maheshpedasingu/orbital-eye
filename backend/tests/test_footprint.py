from app.orbit.footprint import footprint_radius_km


def test_looking_straight_up_gives_zero_radius():
    assert abs(footprint_radius_km(700.0, 90.0)) < 1e-6


def test_horizon_radius_at_700km_is_plausible():
    assert 2700.0 < footprint_radius_km(700.0, 0.0) < 3000.0


def test_higher_orbit_or_lower_elevation_gives_bigger_footprint():
    assert footprint_radius_km(1000.0, 0.0) > footprint_radius_km(500.0, 0.0)
    assert footprint_radius_km(500.0, 0.0) > footprint_radius_km(500.0, 10.0)
