import os
from datetime import datetime, timedelta, timezone

from app.alerts.engine import evaluate_new_detections
from app.storage.db import DB_PATH, connect, finish_run, save_detections, start_run

# Simulated events live in their OWN database so they can never mix with real data.
SIM_DB_PATH = DB_PATH.parent / "simulation.db"


def insert_simulated_detection(conn, lat, lon, confidence, acquired, frp_mw=10.0) -> int:
    """Insert a clearly labelled SIMULATED detection. Returns its id."""
    run_id = start_run(conn, "SIMULATED", (lon, lat, lon, lat), 0)
    det = {
        "latitude_deg": lat, "longitude_deg": lon,
        "acquired_utc": acquired.isoformat(),
        "satellite": "SIM", "instrument": "SIMULATED",
        "confidence_raw": confidence, "frp_mw": frp_mw,
        "brightness_k": None, "daynight": None,
    }
    save_detections(conn, run_id, "SIMULATED", [det], data_origin="SIMULATED")
    finish_run(conn, run_id, "ok", 1, 0, 1, None)
    return conn.execute(
        "SELECT id FROM fire_detections WHERE run_id = ?", (run_id,)
    ).fetchone()[0]


if __name__ == "__main__":
    if SIM_DB_PATH.exists():
        os.remove(SIM_DB_PATH)  # start the demo from a clean simulation database
    conn = connect(SIM_DB_PATH)
    now = datetime.now(timezone.utc)
    ago = lambda h: now - timedelta(hours=h)

    insert_simulated_detection(conn, 16.906, 80.648, "n", ago(6))    # ~44 km north, nominal
    insert_simulated_detection(conn, 16.950, 80.648, "l", ago(5))    # ~49 km north, low
    insert_simulated_detection(conn, 16.506, 80.648, "h", ago(3))    # AOI centre, high
    insert_simulated_detection(conn, 16.5085, 80.648, "n", ago(2))   # ~280 m from the one above
    insert_simulated_detection(conn, 20.000, 80.600, "h", ago(1))    # ~390 km away

    print("outcomes:", evaluate_new_detections(conn, now=now))
    for row in conn.execute(
        "SELECT severity, data_origin, zone, distance_km, duplicate_count FROM alerts"
        " ORDER BY id"
    ):
        print(tuple(row))
