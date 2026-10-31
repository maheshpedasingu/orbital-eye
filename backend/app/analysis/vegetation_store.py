import json
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS vegetation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'no_scene', 'failed')),
    data_origin TEXT NOT NULL DEFAULT 'REAL_EXTERNAL',
    collection TEXT NOT NULL,
    scene_id TEXT,
    acquired_utc TEXT,
    decimate INTEGER NOT NULL,
    image_path TEXT,
    meta_json TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_veg_scene ON vegetation_results(scene_id);
"""


def ensure_table(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record_result(conn, status, collection, decimate, scene_id=None,
                  acquired_utc=None, image_path=None, meta=None, error=None) -> int:
    cur = conn.execute(
        "INSERT INTO vegetation_results (created_utc, status, collection, scene_id,"
        " acquired_utc, decimate, image_path, meta_json, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), status, collection, scene_id,
         acquired_utc, decimate, image_path,
         json.dumps(meta) if meta is not None else None, error),
    )
    conn.commit()
    return cur.lastrowid


def latest_ok(conn):
    return conn.execute(
        "SELECT * FROM vegetation_results WHERE status = 'ok' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def latest_any(conn):
    return conn.execute(
        "SELECT * FROM vegetation_results ORDER BY id DESC LIMIT 1"
    ).fetchone()


def scene_done(conn, scene_id, decimate) -> bool:
    row = conn.execute(
        "SELECT 1 FROM vegetation_results WHERE status = 'ok' AND scene_id = ?"
        " AND decimate = ?", (scene_id, decimate)
    ).fetchone()
    return row is not None
