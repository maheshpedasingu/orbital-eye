import argparse
import json
from datetime import datetime, timezone

import numpy as np

from app.analysis.change import (
    change_summary, classify_change, load_change_config, ndvi_difference,
)
from app.analysis.change_job import DATA_DIR, _when, list_candidates
from app.analysis.ndvi_scene import compute_scene
from app.analysis.scene_cache import load_or_compute
from app.analysis.vegetation_store import ensure_table, list_ok
from app.aoi import aoi_bbox
from app.storage.db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS change_series (
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


def ensure_series_table(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def list_series(conn, decimate=4):
    return conn.execute(
        "SELECT * FROM change_series WHERE decimate = ? ORDER BY id ASC", (decimate,)
    ).fetchall()


def pair_done(conn, cur_id, ref_id, decimate) -> bool:
    return conn.execute(
        "SELECT 1 FROM change_series WHERE current_scene_id = ? AND reference_scene_id = ?"
        " AND decimate = ?", (cur_id, ref_id, decimate)).fetchone() is not None


def consecutive_pairs(scenes):
    """(reference, current) for each neighbouring pair, oldest first. Duplicate ids dropped."""
    seen, uniq = set(), []
    for s in sorted(scenes, key=lambda s: _when(s["datetime"])):
        if s["id"] not in seen:
            seen.add(s["id"])
            uniq.append(s)
    return list(zip(uniq[:-1], uniq[1:]))


def compare_pair(ref, cur, bbox, decimate, cache_dir, cfg, loader, computer) -> dict:
    ref_comp = loader(ref, bbox, decimate, cache_dir, computer)
    cur_comp = loader(cur, bbox, decimate, cache_dir, computer)
    days = round((_when(cur["datetime"]) - _when(ref["datetime"])).total_seconds() / 86400, 1)
    base = {"current": {"scene_id": cur["id"], "acquired_utc": cur["datetime"]},
            "reference": {"scene_id": ref["id"], "acquired_utc": ref["datetime"]},
            "days_between": days,
            "thresholds": {"decrease": cfg["decrease_threshold"],
                           "increase": cfg["increase_threshold"]}}
    if not np.allclose(cur_comp["bounds_lonlat"], ref_comp["bounds_lonlat"], atol=1e-4):
        return {"status": "different_grid", "meta": base}
    diff = ndvi_difference(cur_comp["values"], ref_comp["values"])
    index = classify_change(diff, cfg)
    meta = {**base, **change_summary(index, diff, 10 * decimate)}
    ok = meta["overlap_fraction"] >= cfg["min_usable_fraction"]
    return {"status": "ok" if ok else "insufficient_overlap", "meta": meta}


def run_change_series(conn, collection="sentinel-2-c1-l2a", days=120, decimate=4,
                      lister=list_candidates, loader=load_or_compute,
                      computer=compute_scene, out_dir=DATA_DIR) -> list[dict]:
    """Compare each stored real scene with the one before it. Nothing is substituted."""
    ensure_series_table(conn)
    ensure_table(conn)
    stored = {r["scene_id"] for r in list_ok(conn, decimate)}
    cfg = load_change_config()
    bbox = aoi_bbox(0.0)
    scenes = [s for s in lister(collection, bbox, days) if s["id"] in stored]
    results = []
    for ref, cur in consecutive_pairs(scenes):
        if pair_done(conn, cur["id"], ref["id"], decimate):
            results.append({"status": "cached", "current": cur["id"], "reference": ref["id"]})
            continue
        try:
            res = compare_pair(ref, cur, bbox, decimate, out_dir / "cache", cfg, loader, computer)
        except Exception as exc:       # not stored, so it is retried next run
            results.append({"status": "failed", "current": cur["id"],
                            "reference": ref["id"], "error": str(exc)})
            continue
        conn.execute(
            "INSERT INTO change_series (created_utc, status, current_scene_id,"
            " reference_scene_id, decimate, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), res["status"], cur["id"], ref["id"],
             decimate, json.dumps(res["meta"])))
        conn.commit()
        results.append({"status": res["status"], "current": cur["id"], "reference": ref["id"]})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--decimate", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run_change_series(connect(), days=args.days, decimate=args.decimate),
                     indent=2))
