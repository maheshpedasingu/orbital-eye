import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.analysis.vegetation_store import ensure_table, latest_any, latest_ok
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
