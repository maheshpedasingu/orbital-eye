from datetime import datetime, timedelta, timezone

from app.alerts.engine import evaluate_new_detections
from app.alerts.rules import classify
from app.alerts.simulate import insert_simulated_detection
from app.storage.db import connect

RULES = {
    "max_age_hours": 24, "near_km": 30, "regional_km": 100,
    "dedupe_radius_km": 1.0, "dedupe_window_hours": 12,
    "severity_matrix": {
        "inside": {"h": "CRITICAL", "n": "WARNING", "l": "INFO"},
        "near": {"h": "WARNING", "n": "INFO", "l": "INFO"},
        "regional": {"h": "INFO", "n": "INFO", "l": None},
    },
}
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def hours_ago(h):
    return NOW - timedelta(hours=h)


def test_inside_high_confidence_is_critical():
    r = classify(hours_ago(1).isoformat(), "h", 0.0, True, RULES, NOW)
    assert r["outcome"] == "OK" and r["severity"] == "CRITICAL" and r["zone"] == "inside"


def test_regional_low_confidence_is_below_threshold():
    r = classify(hours_ago(1).isoformat(), "l", 50.0, False, RULES, NOW)
    assert r["outcome"] == "BELOW_THRESHOLD"


def test_old_detection_is_ignored():
    r = classify(hours_ago(30).isoformat(), "h", 0.0, True, RULES, NOW)
    assert r["outcome"] == "TOO_OLD"


def test_far_detection_is_out_of_range():
    r = classify(hours_ago(1).isoformat(), "h", 500.0, False, RULES, NOW)
    assert r["outcome"] == "OUT_OF_RANGE"


def test_nearby_repeat_is_suppressed_and_counted(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_simulated_detection(conn, 16.506, 80.648, "h", hours_ago(3))
    insert_simulated_detection(conn, 16.5085, 80.648, "n", hours_ago(2))
    counts = evaluate_new_detections(conn, RULES, NOW)
    assert counts["ALERTED"] == 1 and counts["SUPPRESSED"] == 1
    row = conn.execute("SELECT COUNT(*) AS n, MAX(duplicate_count) AS d FROM alerts").fetchone()
    assert row["n"] == 1 and row["d"] == 1


def test_more_severe_repeat_escalates_to_a_new_alert(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_simulated_detection(conn, 16.506, 80.648, "n", hours_ago(3))
    insert_simulated_detection(conn, 16.5085, 80.648, "h", hours_ago(2))
    evaluate_new_detections(conn, RULES, NOW)
    severities = [r["severity"] for r in conn.execute("SELECT severity FROM alerts ORDER BY id")]
    assert severities == ["WARNING", "CRITICAL"]


def test_each_detection_is_evaluated_only_once(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_simulated_detection(conn, 16.506, 80.648, "h", hours_ago(3))
    insert_simulated_detection(conn, 16.5085, 80.648, "n", hours_ago(2))
    evaluate_new_detections(conn, RULES, NOW)
    second = evaluate_new_detections(conn, RULES, NOW)
    assert sum(second.values()) == 0
    assert conn.execute("SELECT MAX(duplicate_count) FROM alerts").fetchone()[0] == 1


def test_simulated_detections_produce_simulated_alerts(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_simulated_detection(conn, 16.506, 80.648, "h", hours_ago(1))
    evaluate_new_detections(conn, RULES, NOW)
    row = conn.execute("SELECT data_origin, message FROM alerts").fetchone()
    assert row["data_origin"] == "SIMULATED"
    assert "SIMULATED TEST EVENT" in row["message"]
    assert "UNCONFIRMED" in row["message"]
