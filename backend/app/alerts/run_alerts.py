from app.alerts.engine import ensure_alert_tables, evaluate_new_detections
from app.storage.db import connect

if __name__ == "__main__":
    conn = connect()  # the REAL database
    ensure_alert_tables(conn)
    print("outcomes:", evaluate_new_detections(conn))
    for row in conn.execute(
        "SELECT severity, data_origin, zone, distance_km, duplicate_count, acquired_utc"
        " FROM alerts ORDER BY id DESC LIMIT 10"
    ):
        print(tuple(row))
