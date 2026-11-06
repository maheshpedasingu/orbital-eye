import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.analysis.vegetation_store import ensure_table, latest_any, latest_ok, list_ok
from app.storage.db import connect

router = APIRouter()


@router.get("/api/vegetation/latest")
def get_latest():
    """Latest stored NDVI result (Sentinel-2). Computed from real imagery."""
    conn = connect()
    try:
        ensure_table(conn)
        ok = latest_ok(conn)
        last = latest_any(conn)
    finally:
        conn.close()
    info = {
        "last_run_status": last["status"] if last else None,
        "last_run_error": last["error"] if last else None,
        "last_run_utc": last["created_utc"] if last else None,
    }
    if ok is None:
        return {"data_origin": "REAL_EXTERNAL", "status": "none",
                "message": "No NDVI result stored yet. Run: "
                           "python -m app.analysis.vegetation_job", **info}
    return {"data_origin": "REAL_EXTERNAL", "status": "ok",
            "retrieved_utc": ok["created_utc"],
            "image_url": "/api/vegetation/latest.png",
            **json.loads(ok["meta_json"]), **info}


@router.get("/api/vegetation/latest.png")
def get_latest_png():
    conn = connect()
    try:
        ensure_table(conn)
        ok = latest_ok(conn)
    finally:
        conn.close()
    if ok is None or not ok["image_path"] or not Path(ok["image_path"]).exists():
        raise HTTPException(status_code=404, detail="No NDVI image stored")
    return FileResponse(ok["image_path"], media_type="image/png")


def build_series(rows) -> list[dict]:
    """One point per scene (latest run wins), sorted by acquisition time."""
    by_scene = {}
    for r in rows:
        by_scene[r["scene_id"]] = r
    points = []
    for r in by_scene.values():
        meta = json.loads(r["meta_json"]) if r["meta_json"] else {}
        points.append({
            "scene_id": r["scene_id"],
            "acquired_utc": r["acquired_utc"],
            "decimate": r["decimate"],
            "metrics": {k: v for k, v in meta.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)},
            "category_fractions": {c["name"]: c["fraction"]
                                   for c in meta.get("categories", [])},
        })
    points.sort(key=lambda p: p["acquired_utc"] or "")
    return points


@router.get("/api/vegetation/series")
def get_series(decimate: int = 4):
    """NDVI history: one point per stored real Sentinel-2 scene."""
    conn = connect()
    try:
        ensure_table(conn)
        rows = list_ok(conn, decimate)
    finally:
        conn.close()
    points = build_series(rows)
    return {"data_origin": "REAL_EXTERNAL", "count": len(points), "points": points}
