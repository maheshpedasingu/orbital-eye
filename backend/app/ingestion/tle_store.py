from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS tle_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catnr INTEGER NOT NULL,
    name TEXT NOT NULL,
    line1 TEXT NOT NULL,
    line2 TEXT NOT NULL,
    epoch_utc TEXT NOT NULL,
    retrieved_utc TEXT NOT NULL,
    source_url TEXT NOT NULL,
    data_origin TEXT NOT NULL DEFAULT 'REAL_EXTERNAL' CHECK (data_origin = 'REAL_EXTERNAL'),
    UNIQUE (catnr, epoch_utc)
);
CREATE TABLE IF NOT EXISTS tle_fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catnr INTEGER NOT NULL,
    requested_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'failed')),
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_tle_catnr ON tle_sets(catnr, epoch_utc);
"""


def ensure_tle_tables(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def last_attempt(conn, catnr: int):
    row = conn.execute(
        "SELECT MAX(requested_utc) FROM tle_fetches WHERE catnr = ?", (catnr,)
    ).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


def record_attempt(conn, catnr: int, when: datetime, status: str, error) -> None:
    conn.execute(
        "INSERT INTO tle_fetches (catnr, requested_utc, status, error) VALUES (?, ?, ?, ?)",
        (catnr, when.isoformat(), status, error),
    )
    conn.commit()


def save_tle(conn, tle: dict, retrieved: datetime, source_url: str) -> bool:
    """Insert an element set. Returns True if it is new (a different epoch)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO tle_sets (catnr, name, line1, line2, epoch_utc,"
        " retrieved_utc, source_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tle["catnr"], tle["name"], tle["line1"], tle["line2"], tle["epoch_utc"],
         retrieved.isoformat(), source_url),
    )
    conn.commit()
    return cur.rowcount == 1


def latest_tle(conn, catnr: int):
    return conn.execute(
        "SELECT * FROM tle_sets WHERE catnr = ? ORDER BY epoch_utc DESC LIMIT 1",
        (catnr,),
    ).fetchone()