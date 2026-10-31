import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.analysis.change_store import (
    ensure_change_table, latest_change_any, latest_change_ok,
)
from app.storage.db import connect

router = APIRouter()


@router.get("/api/vegetation/change/latest")
def get_change():
    """Latest NDVI change between two Sentinel-2 dates, comparable pixels only."""
    conn = connect()
    try:
        ensure_change_table(conn)
        ok = latest_change_ok(conn)
        last = latest_change_any(conn)
    finally:
        conn.close()
    info = {
        "last_run_status": last["status"] if last else None,
        "last_run_error": last["error"] if last else None,
        "last_run_utc": last["created_utc"] if last else None,
    }
    if ok is None:
        reason = last["error"] if last and last["error"] else \
            "No change result stored yet. Run: python -m app.analysis.change_job"
        return {"data_origin": "REAL_EXTERNAL", "status": "none", "message": reason, **info}
    return {"data_origin": "REAL_EXTERNAL", "status": "ok",
            "retrieved_utc": ok["created_utc"],
            "image_url": "/api/vegetation/change/latest.png",
            **json.loads(ok["meta_json"]), **info}


@router.get("/api/vegetation/change/latest.png")
def get_change_png():
    conn = connect()
    try:
        ensure_change_table(conn)
        ok = latest_change_ok(conn)
    finally:
        conn.close()
    if ok is None or not ok["image_path"] or not Path(ok["image_path"]).exists():
        raise HTTPException(status_code=404, detail="No change image stored")
    return FileResponse(ok["image_path"], media_type="image/png")
