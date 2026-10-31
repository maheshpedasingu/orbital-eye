import json
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS vegetation_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('ok', 'no_scene', 'no_reference', 'insufficient_overlap', 'failed')),
    data_origin TEXT NOT NULL DEFAULT 'REAL_EXTERNAL',
    collection TEXT NOT NULL,
    current_scene_id TEXT,
    reference_scene_id TEXT,
    decimate INTEGER NOT NULL,
    image_path TEXT,
    meta_json TEXT,
    error TEXT
);
"""


def ensure_change_table(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def record_change(conn, status, collection, decimate, current_scene_id=None,
                  reference_scene_id=None, image_path=None, meta=None, error=None) -> int:
    cur = conn.execute(
        "INSERT INTO vegetation_changes (created_utc, status, collection,"
        " current_scene_id, reference_scene_id, decimate, image_path, meta_json, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), status, collection,
         current_scene_id, reference_scene_id, decimate, image_path,
         json.dumps(meta) if meta is not None else None, error),
    )
    conn.commit()
    return cur.lastrowid


def latest_change_ok(conn):
    return conn.execute(
        "SELECT * FROM vegetation_changes WHERE status = 'ok' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def latest_change_any(conn):
    return conn.execute(
        "SELECT * FROM vegetation_changes ORDER BY id DESC LIMIT 1"
    ).fetchone()
