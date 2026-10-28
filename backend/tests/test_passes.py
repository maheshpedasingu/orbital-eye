import math
from datetime import datetime, timezone

from app.orbit.passes import elevation_deg, find_passes, observer_ecef_km

LAT, LON = 16.506, 80.648
LINE1 = "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991"
LINE2 = "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482"
START = datetime(2019, 12, 9, 0, 0, 0, tzinfo=timezone.utc)


def test_satellite_straight_overhead_is_90_degrees():
    ox, oy, oz = observer_ecef_km(LAT, LON)
    lat, lon = math.radians(LAT), math.radians(LON)
    up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
    sat = (ox + 500 * up[0], oy + 500 * up[1], oz + 500 * up[2])
    assert abs(elevation_deg(sat, LAT, LON) - 90.0) < 1e-6


def test_satellite_on_far_side_of_earth_is_below_horizon():
    ox, oy, oz = observer_ecef_km(LAT, LON)
    sat = (-1.1 * ox, -1.1 * oy, -1.1 * oz)
    assert elevation_deg(sat, LAT, LON) < 0.0


def test_passes_are_well_formed():
    passes = find_passes(LINE1, LINE2, START, 86400.0, LAT, LON, 0.0)
    assert len(passes) >= 1
    for p in passes:
        assert p["start_utc"] <= p["max_time_utc"] <= p["end_utc"]
        assert 0.0 <= p["max_elevation_deg"] <= 90.0
