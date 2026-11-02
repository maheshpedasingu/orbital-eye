import time

from fastapi import APIRouter, Query

from app.orbit.pass_predictor import predict_all
from app.storage.db import connect

router = APIRouter()

CACHE_SECONDS = 600.0
_CACHE: dict = {}


@router.get("/api/passes/next")
def get_next_passes(hours: float = Query(72.0, gt=0, le=168),
                    limit: int = Query(5, ge=1, le=20)):
    """Upcoming observation opportunities over the AOI centre (PROPAGATED_FROM_REAL_TLE).

    Results are cached for 10 minutes because the calculation is slow.
    """
    key = (round(hours, 3), limit)
    hit = _CACHE.get(key)
    if hit is not None and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    conn = connect()
    try:
        result = predict_all(conn, hours=hours, limit=limit)
    finally:
        conn.close()
    _CACHE[key] = (time.time(), result)
    return result