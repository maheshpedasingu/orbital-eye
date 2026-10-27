import math
from datetime import datetime, timezone

from app.orbit.propagate import propagate_tle

# Test fixture from the python-sgp4 documentation. Epoch Dec 2019: NOT current.
LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
WHEN = datetime(2019, 12, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_radius_is_a_low_earth_orbit():
    r, _ = propagate_tle(LINE1, LINE2, WHEN)
    radius = math.sqrt(sum(c * c for c in r))
    assert 6700.0 < radius < 6900.0


def test_speed_is_about_7_6_km_s():
    _, v = propagate_tle(LINE1, LINE2, WHEN)
    speed = math.sqrt(sum(c * c for c in v))
    assert 7.5 < speed < 7.8
