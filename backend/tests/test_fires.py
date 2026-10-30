from app.fires_api import row_to_feature
from app.geo_utils import haversine_km

BOX = (80.498, 16.356, 80.798, 16.656)


def test_one_degree_of_longitude_on_the_equator_is_about_111_km():
    assert abs(haversine_km(0.0, 0.0, 0.0, 1.0) - 111.195) < 0.05


def test_distance_to_same_point_is_zero():
    assert haversine_km(16.5, 80.6, 16.5, 80.6) == 0.0


def test_point_at_aoi_centre_is_inside_with_zero_distance():
    row = {"latitude_deg": 16.506, "longitude_deg": 80.648, "data_origin": "REAL_EXTERNAL",
           "source": "TEST", "satellite": "N", "acquired_utc": "x", "retrieved_utc": "y",
           "confidence_raw": "n", "frp_mw": 1.0, "daynight": "N"}
    p = row_to_feature(row, 16.506, 80.648, BOX)["properties"]
    assert p["inside_aoi_box"] is True
    assert p["distance_to_aoi_centre_km"] == 0.0
    assert p["status"] == "UNCONFIRMED_THERMAL_ANOMALY"


def test_point_far_outside_is_flagged_outside():
    row = {"latitude_deg": 16.870, "longitude_deg": 80.023, "data_origin": "REAL_EXTERNAL",
           "source": "TEST", "satellite": "N", "acquired_utc": "x", "retrieved_utc": "y",
           "confidence_raw": "n", "frp_mw": 1.0, "daynight": "N"}
    p = row_to_feature(row, 16.506, 80.648, BOX)["properties"]
    assert p["inside_aoi_box"] is False
    assert 70.0 < p["distance_to_aoi_centre_km"] < 85.0
