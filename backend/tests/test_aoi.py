from app.aoi import load_aoi


def test_aoi_polygon_is_closed_and_contains_city_centre():
    feature = load_aoi()["features"][0]
    ring = feature["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    c = feature["properties"]
    assert min(lons) < c["centre_lon_deg"] < max(lons)
    assert min(lats) < c["centre_lat_deg"] < max(lats)


def test_aoi_is_in_india_longitude_latitude_order():
    ring = load_aoi()["features"][0]["geometry"]["coordinates"][0]
    for lon, lat in ring:
        assert 68.0 < lon < 98.0   # India spans roughly 68E to 98E
        assert 6.0 < lat < 36.0    # and roughly 6N to 36N
