from datetime import datetime, timedelta

TASK_ORDER = ["firms", "alerts", "tle", "vegetation", "change"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    started_utc TEXT NOT NULL,
    finished_utc TEXT,
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed', 'skipped')),
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_runs ON task_runs(task, id);
"""


def ensure_task_table(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record_task(conn, task, started, finished, status, message) -> None:
    conn.execute(
        "INSERT INTO task_runs (task, started_utc, finished_utc, status, message)"
        " VALUES (?, ?, ?, ?, ?)",
        (task, started.isoformat(), finished.isoformat(), status, message),
    )
    conn.commit()


def last_attempt(conn, task):
    return conn.execute(
        "SELECT * FROM task_runs WHERE task = ? ORDER BY id DESC LIMIT 1", (task,)
    ).fetchone()


def last_success(conn, task):
    return conn.execute(
        "SELECT * FROM task_runs WHERE task = ? AND status = 'ok' ORDER BY id DESC LIMIT 1",
        (task,),
    ).fetchone()


def is_due(conn, task, min_minutes, now) -> bool:
    """True if the task never ran, or its last attempt (any outcome) is old enough."""
    row = last_attempt(conn, task)
    if row is None:
        return True
    return now - datetime.fromisoformat(row["started_utc"]) >= timedelta(minutes=min_minutes)