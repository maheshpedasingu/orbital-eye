import argparse
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.storage.db import DB_PATH, connect
from app.task_log import ensure_task_table, is_due, record_task

LOG_DIR = DB_PATH.parent / "logs"
LOCK_PATH = DB_PATH.parent / "scheduler.lock"

# Minimum minutes between attempts. Gentle on purpose: FIRMS limits were not verified.
FIRMS_MIN_MINUTES = 60
TLE_MIN_MINUTES = 60          # the TLE client also enforces its own 12 hour limit
VEGETATION_MIN_MINUTES = 360
CHANGE_MIN_MINUTES = 360

log = logging.getLogger("orbital_eye")


class AlreadyRunning(Exception):
    pass


def acquire_lock(path: Path, stale_s: float = 3600.0) -> None:
    """Create the lock file, or raise AlreadyRunning. A lock older than stale_s is replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age < stale_s:
                raise AlreadyRunning(f"another scheduler holds {path}") from None
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return
    raise AlreadyRunning(f"could not take {path}")


def touch_lock(path: Path) -> None:
    try:
        os.utime(str(path), None)
    except FileNotFoundError:
        pass


def release_lock(path: Path) -> None:
    Path(path).unlink(missing_ok=True)


def setup_logging(log_dir: Path = LOG_DIR) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s UTC %(levelname)s %(message)s")
    fmt.converter = time.gmtime
    file_handler = RotatingFileHandler(
        log_dir / "orbital_eye.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    for handler in (file_handler, logging.StreamHandler()):
        handler.setFormatter(fmt)
        log.addHandler(handler)


# ---- tasks: each returns (status, message); status is ok, failed or skipped ----

def task_firms(conn):
    from app.aoi import aoi_bbox
    from app.config import get_firms_key
    from app.ingestion.run_firms import ingest_firms

    key = get_firms_key()
    if not key:
        return "skipped", "FIRMS_MAP_KEY is not set"
    r = ingest_firms(conn, key, "VIIRS_SNPP_NRT", aoi_bbox(pad_deg=0.5), day_range=2)
    if r["status"] != "ok":
        return "failed", r["error"]
    return "ok", f"valid={r['rows_valid']} rejected={r['rows_rejected']} new={r['rows_new']}"


def task_alerts(conn):
    from app.alerts.engine import evaluate_new_detections

    return "ok", str(evaluate_new_detections(conn))


def task_tle(conn):
    from app.ingestion.run_celestrak import refresh_tle
    from app.orbit.pass_predictor import load_satellites

    results = [refresh_tle(conn, s["catnr"], expected_name=s.get("expected_name")) for s in load_satellites()]
    summary = ", ".join(f"{r['catnr']}:{r['status']}" for r in results)
    if any(r["status"] == "failed" for r in results):
        errors = "; ".join(r["error"] for r in results if r["status"] == "failed")
        return "failed", f"{summary} ({errors})"
    return "ok", summary


def task_vegetation(conn):
    from app.analysis.vegetation_job import run_vegetation_job

    r = run_vegetation_job(conn)
    if r["status"] == "failed":
        return "failed", r["error"]
    return "ok", r["status"] + (f" ({r['error']})" if r.get("error") else "")


def task_change(conn):
    from app.analysis.change_job import run_change_job

    r = run_change_job(conn)
    if r["status"] == "failed":
        return "failed", r["error"]
    return "ok", r["status"] + (f" ({r['error']})" if r.get("error") else "")


def task_firms_all(conn):
    from app.aoi import aoi_bbox
    from app.config import get_firms_key
    from app.ingestion.run_firms import ingest_firms
    from app.orbit.pass_predictor import load_satellites

    key = get_firms_key()
    if not key:
        return "skipped", "FIRMS_MAP_KEY is not set"
    sources = sorted({s["firms_source"] for s in load_satellites() if s.get("firms_source")})
    if not sources:
        return "skipped", "no firms_source configured"
    parts, errors = [], []
    for source in sources:
        r = ingest_firms(conn, key, source, aoi_bbox(pad_deg=0.5), day_range=2)
        if r["status"] == "ok":
            parts.append(f"{source}: valid={r['rows_valid']} new={r['rows_new']}")
        else:
            errors.append(f"{source}: {r['error']}")
    summary = "; ".join(parts + errors)
    return ("failed", summary) if errors else ("ok", summary)


TASKS = [
    ("firms", FIRMS_MIN_MINUTES, task_firms_all),
    ("alerts", 0, task_alerts),
    ("tle", TLE_MIN_MINUTES, task_tle),
    ("vegetation", VEGETATION_MIN_MINUTES, task_vegetation),
    ("change", CHANGE_MIN_MINUTES, task_change),
]


def run_once(conn, now=None, tasks=None, force=False) -> list[dict]:
    """Run every due task once. A crashing task never stops the others."""
    ensure_task_table(conn)
    now = now or datetime.now(timezone.utc)
    results = []
    for name, min_minutes, func in (tasks if tasks is not None else TASKS):
        if not force and not is_due(conn, name, min_minutes, now):
            results.append({"task": name, "status": "not_due"})
            continue
        try:
            status, message = func(conn)
        except Exception as exc:
            log.exception("task %s crashed", name)
            status, message = "failed", f"{type(exc).__name__}: {exc}"
        record_task(conn, name, now, datetime.now(timezone.utc), status, message)
        log.info("task %s: %s - %s", name, status, message)
        results.append({"task": name, "status": status, "message": message})
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop-minutes", type=float, default=0.0,
                        help="repeat every N minutes (0 = run once)")
    parser.add_argument("--force", action="store_true",
                        help="run every task now, ignoring the minimum intervals")
    args = parser.parse_args()
    if args.loop_minutes < 0 or 0 < args.loop_minutes < 5:
        raise SystemExit("--loop-minutes must be 0 (run once) or at least 5")

    setup_logging()
    try:
        acquire_lock(LOCK_PATH)
    except AlreadyRunning as exc:
        log.error("not starting: %s", exc)
        return 1
    try:
        conn = connect()
        force = args.force
        while True:
            run_once(conn, force=force)
            force = False
            if args.loop_minutes == 0:
                break
            deadline = time.time() + args.loop_minutes * 60.0
            while time.time() < deadline:
                touch_lock(LOCK_PATH)
                time.sleep(min(60.0, max(0.0, deadline - time.time())))
    except KeyboardInterrupt:
        log.info("stopped by user")
    finally:
        release_lock(LOCK_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())