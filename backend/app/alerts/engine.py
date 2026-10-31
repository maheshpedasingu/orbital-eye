from datetime import datetime, timedelta, timezone

from app.alerts.rules import SEVERITY_RANK, classify, load_rules
from app.aoi import aoi_bbox, load_aoi
from app.geo_utils import haversine_km

ALERT_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    data_origin TEXT NOT NULL CHECK (data_origin IN ('REAL_EXTERNAL', 'SIMULATED')),
    detection_id INTEGER REFERENCES fire_detections(id),
    latitude_deg REAL NOT NULL,
    longitude_deg REAL NOT NULL,
    acquired_utc TEXT NOT NULL,
    last_seen_utc TEXT NOT NULL,
    zone TEXT NOT NULL,
    distance_km REAL NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    duplicate_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alert_evaluations (
    detection_id INTEGER PRIMARY KEY REFERENCES fire_detections(id),
    evaluated_utc TEXT NOT NULL,
    outcome TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_seen ON alerts(last_seen_utc);
"""

OUTCOMES = ("ALERTED", "SUPPRESSED", "BELOW_THRESHOLD", "OUT_OF_RANGE", "TOO_OLD")


def ensure_alert_tables(conn) -> None:
    conn.executescript(ALERT_SCHEMA)
    conn.commit()


def _find_matches(conn, det: dict, rules: dict) -> list:
    acquired = datetime.fromisoformat(det["acquired_utc"])
    earliest = (acquired - timedelta(hours=rules["dedupe_window_hours"])).isoformat()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE data_origin = ? AND last_seen_utc >= ?",
        (det["data_origin"], earliest),
    ).fetchall()
    return [
        r for r in rows
        if haversine_km(r["latitude_deg"], r["longitude_deg"],
                        det["latitude_deg"], det["longitude_deg"])
        <= rules["dedupe_radius_km"]
    ]


def _create_alert(conn, det, severity, zone, distance_km, now) -> None:
    prefix = "[SIMULATED TEST EVENT] " if det["data_origin"] == "SIMULATED" else ""
    title = f"{prefix}{severity}: thermal anomaly, {zone} zone, {distance_km:.0f} km from AOI centre"
    message = (
        f"{prefix}Satellite-reported thermal anomaly ({zone} zone), "
        f"{distance_km:.1f} km from the AOI centre. Source {det['source']}, "
        f"confidence {det['confidence_raw']}, acquired {det['acquired_utc']}. "
        "UNCONFIRMED: a thermal anomaly is not a verified wildfire."
    )
    conn.execute(
        "INSERT INTO alerts (created_utc, severity, data_origin, detection_id,"
        " latitude_deg, longitude_deg, acquired_utc, last_seen_utc, zone,"
        " distance_km, title, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now.isoformat(), severity, det["data_origin"], det["id"],
         det["latitude_deg"], det["longitude_deg"], det["acquired_utc"],
         det["acquired_utc"], zone, round(distance_km, 1), title, message),
    )


def evaluate_new_detections(conn, rules=None, now=None) -> dict:
    """Evaluate each stored detection exactly once. Returns outcome counts."""
    ensure_alert_tables(conn)
    rules = rules or load_rules()
    now = now or datetime.now(timezone.utc)
    centre = load_aoi()["features"][0]["properties"]
    west, south, east, north = aoi_bbox(0.0)

    pending = conn.execute(
        "SELECT * FROM fire_detections WHERE id NOT IN"
        " (SELECT detection_id FROM alert_evaluations) ORDER BY acquired_utc ASC"
    ).fetchall()

    counts = {name: 0 for name in OUTCOMES}
    for row in pending:
        det = dict(row)
        lat, lon = det["latitude_deg"], det["longitude_deg"]
        inside = south <= lat <= north and west <= lon <= east
        distance = haversine_km(centre["centre_lat_deg"], centre["centre_lon_deg"], lat, lon)
        result = classify(det["acquired_utc"], det["confidence_raw"], distance, inside, rules, now)
        outcome = result["outcome"]

        if outcome == "OK":
            severity = result["severity"]
            matches = _find_matches(conn, det, rules)
            top = max(matches, key=lambda m: SEVERITY_RANK[m["severity"]]) if matches else None
            if top is not None and SEVERITY_RANK[severity] <= SEVERITY_RANK[top["severity"]]:
                conn.execute(
                    "UPDATE alerts SET duplicate_count = duplicate_count + 1,"
                    " last_seen_utc = MAX(last_seen_utc, ?) WHERE id = ?",
                    (det["acquired_utc"], top["id"]),
                )
                outcome = "SUPPRESSED"
            else:
                _create_alert(conn, det, severity, result["zone"], distance, now)
                outcome = "ALERTED"

        conn.execute(
            "INSERT INTO alert_evaluations (detection_id, evaluated_utc, outcome)"
            " VALUES (?, ?, ?)",
            (det["id"], now.isoformat(), outcome),
        )
        counts[outcome] += 1
    conn.commit()
    return counts
