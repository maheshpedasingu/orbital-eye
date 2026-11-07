import argparse
import json
from datetime import datetime, timezone

from app.analysis.change import load_change_config
from app.analysis.change_job import DATA_DIR
from app.analysis.change_series import compare_pair
from app.analysis.ndvi_scene import compute_scene
from app.analysis.scene_cache import load_or_compute
from app.analysis.vegetation_store import ensure_table, list_ok
from app.aoi import aoi_bbox
from app.storage.db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS change_baseline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'insufficient_overlap', 'different_grid')),
    data_origin TEXT NOT NULL DEFAULT 'REAL_EXTERNAL',
    current_scene_id TEXT NOT NULL,
    reference_scene_id TEXT NOT NULL,
    decimate INTEGER NOT NULL,
    meta_json TEXT,
    UNIQUE (current_scene_id, reference_scene_id, decimate)
);
"""


def ensure_baseline_table(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def list_baseline(conn, decimate=4):
    return conn.execute(
        "SELECT * FROM change_baseline WHERE decimate = ? ORDER BY id ASC", (decimate,)
    ).fetchall()


def _coverage(row) -> float:
    meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
    return float(meta.get("fraction_with_ndvi") or 0.0)


def unique_scenes(rows):
    """One row per scene (latest run wins)."""
    by_id = {}
    for r in rows:
        by_id[r["scene_id"]] = r
    return list(by_id.values())


def choose_baseline(rows):
    """Stored scene with the highest fraction of usable NDVI (newest wins a tie)."""
    scenes = unique_scenes(rows)
    if not scenes:
        return None
    best = max(scenes, key=lambda r: (_coverage(r), r["acquired_utc"] or ""))
    return {"id": best["scene_id"], "datetime": best["acquired_utc"]}


def run_change_baseline(conn, decimate=4, loader=load_or_compute,
                        computer=compute_scene, out_dir=DATA_DIR) -> list[dict]:
    """Compare every stored scene with one baseline scene. Nothing is substituted."""
    ensure_baseline_table(conn)
    ensure_table(conn)
    rows = list_ok(conn, decimate)
    base = choose_baseline(rows)
    if base is None:
        return []
    cfg = load_change_config()
    bbox = aoi_bbox(0.0)
    results = []
    for r in unique_scenes(rows):
        if r["scene_id"] == base["id"]:
            continue
        cur = {"id": r["scene_id"], "datetime": r["acquired_utc"]}
        done = conn.execute(
            "SELECT 1 FROM change_baseline WHERE current_scene_id=? AND reference_scene_id=?"
            " AND decimate=?", (cur["id"], base["id"], decimate)).fetchone()
        if done:
            results.append({"status": "cached", "current": cur["id"]})
            continue
        try:
            res = compare_pair(base, cur, bbox, decimate, out_dir / "cache", cfg,
                               loader, computer)
        except Exception as exc:
            results.append({"status": "failed", "current": cur["id"], "error": str(exc)})
            continue
        conn.execute(
            "INSERT INTO change_baseline (created_utc, status, current_scene_id,"
            " reference_scene_id, decimate, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), res["status"], cur["id"], base["id"],
             decimate, json.dumps(res["meta"])))
        conn.commit()
        results.append({"status": res["status"], "current": cur["id"]})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--decimate", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run_change_baseline(connect(), decimate=args.decimate), indent=2))
