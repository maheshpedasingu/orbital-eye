import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.scheduler import (
    CHANGE_MIN_MINUTES, FIRMS_MIN_MINUTES, LOCK_PATH, TLE_MIN_MINUTES,
    VEGETATION_MIN_MINUTES,
)
from app.storage.db import connect
from app.task_log import TASK_ORDER, ensure_task_table, last_attempt, last_success

router = APIRouter()

EXPECTED_MINUTES = {
    "firms": FIRMS_MIN_MINUTES,
    "alerts": FIRMS_MIN_MINUTES,   # runs on every pass of the scheduler loop
    "tle": TLE_MIN_MINUTES,
    "vegetation": VEGETATION_MIN_MINUTES,
    "change": CHANGE_MIN_MINUTES,
}
OVERDUE_FACTOR = 3.0
SCHEDULER_ALIVE_S = 180.0   # the loop touches its lock at least once a minute


def is_overdue(last_success_utc, interval_min, now, factor=OVERDUE_FACTOR) -> bool:
    """True if there was never a success, or the last one is older than factor x interval."""
    if last_success_utc is None:
        return True
    age = now - datetime.fromisoformat(last_success_utc)
    return age > timedelta(minutes=interval_min * factor)


def scheduler_running() -> bool:
    try:
        age = time.time() - LOCK_PATH.stat().st_mtime
    except FileNotFoundError:
        return False
    return age < SCHEDULER_ALIVE_S


@router.get("/api/system/status")
def get_status():
    """Job history, overdue flags, scheduler state and data freshness."""
    now = datetime.now(timezone.utc)
    conn = connect()
    try:
        ensure_task_table(conn)
        tasks = []
        for name in TASK_ORDER:
            last = last_attempt(conn, name)
            ok = last_success(conn, name)
            ok_time = ok["started_utc"] if ok else None
            tasks.append({
                "task": name,
                "never_run": last is None,
                "status": last["status"] if last else None,
                "last_attempt_utc": last["started_utc"] if last else None,
                "message": last["message"] if last else None,
                "last_success_utc": ok_time,
                "expected_interval_minutes": EXPECTED_MINUTES[name],
                "overdue": is_overdue(ok_time, EXPECTED_MINUTES[name], now),
            })
        row = conn.execute(
            "SELECT COUNT(*), MAX(retrieved_utc) FROM fire_detections").fetchone()
    finally:
        conn.close()
    return {
        "generated_utc": now.isoformat(),
        "scheduler_running": scheduler_running(),
        "tasks": tasks,
        "fire_detections": {"count": row[0], "latest_retrieved_utc": row[1]},
    }