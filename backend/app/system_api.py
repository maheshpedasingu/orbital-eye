from datetime import datetime, timezone

from fastapi import APIRouter

from app.storage.db import connect
from app.task_log import TASK_ORDER, ensure_task_table, last_attempt, last_success

router = APIRouter()


@router.get("/api/system/status")
def get_status():
    """When each refresh job last ran and last succeeded, plus stored fire detections."""
    conn = connect()
    try:
        ensure_task_table(conn)
        tasks = []
        for name in TASK_ORDER:
            last = last_attempt(conn, name)
            ok = last_success(conn, name)
            tasks.append({
                "task": name,
                "never_run": last is None,
                "status": last["status"] if last else None,
                "last_attempt_utc": last["started_utc"] if last else None,
                "message": last["message"] if last else None,
                "last_success_utc": ok["started_utc"] if ok else None,
            })
        row = conn.execute(
            "SELECT COUNT(*), MAX(retrieved_utc) FROM fire_detections").fetchone()
    finally:
        conn.close()
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": tasks,
        "fire_detections": {"count": row[0], "latest_retrieved_utc": row[1]},
    }