from fastapi import APIRouter, Query

from app.alerts.engine import ensure_alert_tables
from app.storage.db import connect

router = APIRouter()


@router.get("/api/alerts")
def get_alerts(limit: int = Query(50, ge=1, le=500)):
    """Alert history, newest first. Each alert carries its own data_origin."""
    conn = connect()
    try:
        ensure_alert_tables(conn)
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_utc DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        conn.close()
    return {
        "note": "Alerts are based on satellite-reported thermal anomalies. "
                "They are not confirmed wildfires.",
        "count": len(rows),
        "alerts": [dict(r) for r in rows],
    }
