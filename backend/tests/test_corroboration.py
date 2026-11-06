from app.corroboration import corroborate


def _d(i, sat, lat, lon, t, origin="REAL_EXTERNAL"):
    return {"id": i, "satellite": sat, "latitude_deg": lat, "longitude_deg": lon,
            "acquired_utc": t, "data_origin": origin}


def test_two_satellites_close_in_space_and_time_are_corroborated():
    dets = [_d(1, "N20", 16.500, 80.600, "2026-11-05T20:00:00+00:00"),
            _d(2, "N21", 16.504, 80.601, "2026-11-05T20:50:00+00:00")]
    out = corroborate(dets)
    assert len(out) == 1
    assert out[0]["satellites"] == ["N20", "N21"]
    assert out[0]["span_minutes"] == 50.0


def test_same_satellite_twice_is_not_corroboration():
    dets = [_d(1, "N20", 16.500, 80.600, "2026-11-05T20:00:00+00:00"),
            _d(2, "N20", 16.501, 80.600, "2026-11-05T20:10:00+00:00")]
    assert corroborate(dets) == []


def test_far_apart_is_not_corroborated():
    dets = [_d(1, "N20", 16.50, 80.60, "2026-11-05T20:00:00+00:00"),
            _d(2, "N21", 16.60, 80.60, "2026-11-05T20:10:00+00:00")]
    assert corroborate(dets) == []


def test_outside_time_window_is_not_corroborated():
    dets = [_d(1, "N20", 16.500, 80.600, "2026-11-05T10:00:00+00:00"),
            _d(2, "N21", 16.501, 80.600, "2026-11-05T20:00:00+00:00")]
    assert corroborate(dets) == []


def test_simulated_and_real_are_never_mixed():
    dets = [_d(1, "N20", 16.500, 80.600, "2026-11-05T20:00:00+00:00"),
            _d(2, "N21", 16.501, 80.600, "2026-11-05T20:10:00+00:00", "SIMULATED")]
    assert corroborate(dets) == []


def test_three_satellites_form_one_cluster():
    dets = [_d(1, "N", 16.500, 80.600, "2026-11-05T19:00:00+00:00"),
            _d(2, "N20", 16.501, 80.600, "2026-11-05T19:50:00+00:00"),
            _d(3, "N21", 16.502, 80.601, "2026-11-05T20:40:00+00:00")]
    out = corroborate(dets, window_minutes=120)
    assert len(out) == 1 and out[0]["n_detections"] == 3
    assert out[0]["satellites"] == ["N", "N20", "N21"]
