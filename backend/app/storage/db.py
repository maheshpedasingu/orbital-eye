import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "orbital_eye.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    bbox TEXT NOT NULL,
    day_range INTEGER NOT NULL,
    started_utc TEXT NOT NULL,
    finished_utc TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'failed')),
    rows_valid INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    rows_new INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS fire_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES ingestion_runs(id),
    data_origin TEXT NOT NULL CHECK (data_origin IN ('REAL_EXTERNAL', 'SIMULATED')),
    source TEXT NOT NULL,
    latitude_deg REAL NOT NULL,
    longitude_deg REAL NOT NULL,
    acquired_utc TEXT NOT NULL,
    satellite TEXT,
    instrument TEXT,
    confidence_raw TEXT,
    frp_mw REAL,
    brightness_k REAL,
    daynight TEXT,
    retrieved_utc TEXT NOT NULL,
    UNIQUE (source, latitude_deg, longitude_deg, acquired_utc)
);
CREATE INDEX IF NOT EXISTS idx_fire_acquired ON fire_detections(acquired_utc);
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def start_run(conn, source: str, bbox, day_range: int) -> int:
    cur = conn.execute(
        "INSERT INTO ingestion_runs (source, bbox, day_range, started_utc, status)"
        " VALUES (?, ?, ?, ?, 'running')",
        (source, ",".join(str(v) for v in bbox), day_range, now_utc()),
    )
    conn.commit()
    return cur.lastrowid


def finish_run(conn, run_id, status, rows_valid, rows_rejected, rows_new, error):
    conn.execute(
        "UPDATE ingestion_runs SET finished_utc=?, status=?, rows_valid=?,"
        " rows_rejected=?, rows_new=?, error=? WHERE id=?",
        (now_utc(), status, rows_valid, rows_rejected, rows_new, error, run_id),
    )
    conn.commit()


def save_detections(conn, run_id, source, detections, data_origin="REAL_EXTERNAL") -> int:
    """Insert detections, ignoring duplicates. Returns the number of new rows."""
    retrieved = now_utc()
    new = 0
    for d in detections:
        cur = conn.execute(
            "INSERT OR IGNORE INTO fire_detections (run_id, data_origin, source,"
            " latitude_deg, longitude_deg, acquired_utc, satellite, instrument,"
            " confidence_raw, frp_mw, brightness_k, daynight, retrieved_utc)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, data_origin, source, d["latitude_deg"], d["longitude_deg"],
             d["acquired_utc"], d["satellite"], d["instrument"],
             d["confidence_raw"], d["frp_mw"], d["brightness_k"], d["daynight"],
             retrieved),
        )
        new += cur.rowcount
    conn.commit()
    return new
