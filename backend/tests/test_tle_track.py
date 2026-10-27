from datetime import datetime, timezone

from app.orbit.tle_track import tle_ground_track

LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
START = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_point_count():
    assert len(tle_ground_track(LINE1, LINE2, START, 600.0, 60.0)) == 11


def test_latitude_bounded_by_inclination():
    pts = tle_ground_track(LINE1, LINE2, START, 5600.0, 60.0)
    assert max(abs(p["lat_deg"]) for p in pts) <= 51.65 + 0.3


def test_altitude_is_plausible_for_iss():
    pts = tle_ground_track(LINE1, LINE2, START, 600.0, 60.0)
    assert all(380.0 < p["alt_km"] < 450.0 for p in pts)
