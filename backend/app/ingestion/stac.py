from datetime import datetime, timedelta, timezone

import httpx

STAC_URL = "https://earth-search.aws.element84.com/v1"
BAND_KEYS = ("red", "nir", "scl")


def list_collections() -> list[dict]:
    """All collections in the catalogue (id, title, temporal extent)."""
    try:
        r = httpx.get(f"{STAC_URL}/collections", timeout=30.0)
        r.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Earth Search request failed: {exc}") from None
    out = []
    for c in r.json().get("collections", []):
        interval = c.get("extent", {}).get("temporal", {}).get("interval", [[None, None]])
        out.append({"id": c.get("id"), "title": c.get("title"), "interval": interval[0]})
    return out


def search_items(collection: str, bbox, days: int = 45, limit: int = 50) -> list[dict]:
    """Recent items intersecting a bbox (west, south, east, north)."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    body = {
        "collections": [collection],
        "bbox": list(bbox),
        "datetime": f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}",
        "limit": limit,
    }
    try:
        r = httpx.post(f"{STAC_URL}/search", json=body, timeout=60.0)
        r.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Earth Search request failed: {exc}") from None
    return r.json().get("features", [])


def summarize_item(item: dict) -> dict:
    """Reduce a STAC item to what we need to decide how to read it."""
    props = item.get("properties", {})
    assets = item.get("assets", {})
    bands = {}
    for key in BAND_KEYS:
        a = assets.get(key)
        if a is None:
            continue
        rb = (a.get("raster:bands") or [{}])[0]
        bands[key] = {
            "href": a.get("href"),
            "type": a.get("type"),
            "scale": rb.get("scale"),
            "offset": rb.get("offset"),
            "nodata": rb.get("nodata"),
        }
    return {
        "id": item.get("id"),
        "datetime": props.get("datetime"),
        "cloud_cover": props.get("eo:cloud_cover"),
        "platform": props.get("platform"),
        "asset_keys": sorted(assets.keys()),
        "bands": bands,
    }
