from fastapi import APIRouter, Query

from app.alerts.engine import ensure_alert_tables
from app.alerts.simulate import SIM_DB_PATH
from app.storage.db import connect

router = APIRouter()


@router.get("/api/alerts")
def get_alerts(
    limit: int = Query(50, ge=1, le=500),
    origin: str = Query("real", pattern="^(real|simulated)$"),
):
    """Alert history, newest first. origin=real reads the real database;
    origin=simulated reads the separate simulation database (test events only)."""
    rows = []
    if origin == "simulated":
        conn = connect(SIM_DB_PATH) if SIM_DB_PATH.exists() else None
    else:
        conn = connect()
    if conn is not None:
        try:
            ensure_alert_tables(conn)
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_utc DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    return {
        "origin": origin,
        "note": "Alerts are based on satellite-reported thermal anomalies. "
                "They are not confirmed wildfires.",
        "count": len(rows),
        "alerts": [dict(r) for r in rows],
    }
