import argparse
import json
from datetime import datetime, timedelta

import numpy as np

from app.analysis.change import (
    change_summary, classify_change, load_change_config, ndvi_difference,
    render_change_png,
)
from app.analysis.change_store import ensure_change_table, record_change
from app.analysis.ndvi_scene import compute_scene, find_best_scene
from app.analysis.scene_cache import load_or_compute
from app.aoi import aoi_bbox
from app.ingestion.stac import search_items, summarize_item
from app.storage.db import DB_PATH, connect

DATA_DIR = DB_PATH.parent / "vegetation"
REQUIRED_BANDS = ("red", "nir", "scl")


def list_candidates(collection, bbox, days) -> list[dict]:
    return [summarize_item(i) for i in search_items(collection, bbox, days=days)]


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _attribution(*scenes) -> str:
    years = sorted({s["datetime"][:4] for s in scenes})
    return "Contains modified Copernicus Sentinel data " + ", ".join(years)


def run_change_job(conn, collection="sentinel-2-c1-l2a", max_cloud=40.0,
                   current_days=45, reference_days=120, decimate=4,
                   finder=find_best_scene, lister=list_candidates,
                   computer=compute_scene, out_dir=DATA_DIR) -> dict:
    """Compare the current scene with an earlier one. Never substitutes data."""
    ensure_change_table(conn)
    bbox = aoi_bbox(0.0)
    try:
        cfg = load_change_config()
        cur_scene = finder(collection, bbox, current_days, max_cloud)
        if cur_scene is None:
            message = f"No scene under {max_cloud}% scene cloud cover in the last {current_days} days"
            record_change(conn, "no_scene", collection, decimate, error=message)
            return {"status": "no_scene", "error": message}

        cutoff = _when(cur_scene["datetime"]) - timedelta(days=cfg["min_gap_days"])
        candidates = [
            s for s in lister(collection, bbox, reference_days)
            if s["id"] != cur_scene["id"]
            and _when(s["datetime"]) <= cutoff
            and s["cloud_cover"] is not None and s["cloud_cover"] <= max_cloud
            and all(k in s["bands"] for k in REQUIRED_BANDS)
        ]
        candidates.sort(key=lambda s: s["cloud_cover"])
        if not candidates:
            message = (f"No reference scene at least {cfg['min_gap_days']} days earlier "
                       f"with scene cloud <= {max_cloud}% in the last {reference_days} days")
            record_change(conn, "no_reference", collection, decimate,
                          current_scene_id=cur_scene["id"], error=message)
            return {"status": "no_reference", "error": message}

        cache_dir = out_dir / "cache"
        cur_comp = load_or_compute(cur_scene, bbox, decimate, cache_dir, computer)

        tried, chosen = [], None
        for ref_scene in candidates[:cfg["max_reference_tries"]]:
            ref_comp = load_or_compute(ref_scene, bbox, decimate, cache_dir, computer)
            if not np.allclose(cur_comp["bounds_lonlat"], ref_comp["bounds_lonlat"], atol=1e-4):
                raise ValueError("scenes have different grids")
            diff = ndvi_difference(cur_comp["values"], ref_comp["values"])
            overlap = float(np.isfinite(diff).mean())
            tried.append({"scene_id": ref_scene["id"], "acquired_utc": ref_scene["datetime"],
                          "scene_cloud_cover_percent": ref_scene["cloud_cover"],
                          "overlap_fraction": round(overlap, 3)})
            if overlap >= cfg["min_usable_fraction"]:
                chosen = (ref_scene, diff)
                break

        if chosen is None:
            message = ("No reference scene had enough usable overlap: " +
                       "; ".join(f"{t['scene_id']} overlap {t['overlap_fraction']}" for t in tried))
            record_change(conn, "insufficient_overlap", collection, decimate,
                          current_scene_id=cur_scene["id"], error=message,
                          meta={"reference_attempts": tried})
            return {"status": "insufficient_overlap", "error": message, "attempts": tried}

        ref_scene, diff = chosen
        index = classify_change(diff, cfg)
        pixel_m = 10 * decimate
        meta = change_summary(index, diff, pixel_m)
        meta.update({
            "collection": collection,
            "current": {"scene_id": cur_scene["id"], "acquired_utc": cur_scene["datetime"],
                        "scene_cloud_cover_percent": cur_scene["cloud_cover"]},
            "reference": {"scene_id": ref_scene["id"], "acquired_utc": ref_scene["datetime"],
                          "scene_cloud_cover_percent": ref_scene["cloud_cover"]},
            "days_between": round((_when(cur_scene["datetime"]) -
                                   _when(ref_scene["datetime"])).total_seconds() / 86400, 1),
            "thresholds": {"decrease": cfg["decrease_threshold"],
                           "increase": cfg["increase_threshold"]},
            "colors": cfg["colors"],
            "pixel_size_m_approx": pixel_m,
            "bounds_lonlat": list(cur_comp["bounds_lonlat"]),
            "reference_attempts": tried,
            "attribution": _attribution(cur_scene, ref_scene),
        })

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"change_{cur_scene['id']}_vs_{ref_scene['id']}_d{decimate}.png"
        path.write_bytes(render_change_png(index, cfg))
        record_change(conn, "ok", collection, decimate, cur_scene["id"], ref_scene["id"],
                      str(path), meta)
        return {"status": "ok", "image_path": str(path), **{
            k: meta[k] for k in ("overlap_fraction", "class_fractions", "area_km2",
                                 "mean_change", "days_between")},
            "current": meta["current"], "reference": meta["reference"],
            "attempts": tried}
    except Exception as exc:
        record_change(conn, "failed", collection, decimate, error=str(exc))
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="sentinel-2-c1-l2a")
    parser.add_argument("--max-cloud", type=float, default=40.0)
    parser.add_argument("--current-days", type=int, default=45)
    parser.add_argument("--reference-days", type=int, default=120)
    parser.add_argument("--decimate", type=int, default=4)
    args = parser.parse_args()
    if args.decimate < 1:
        raise SystemExit("--decimate must be >= 1")
    print(json.dumps(run_change_job(
        connect(), collection=args.collection, max_cloud=args.max_cloud,
        current_days=args.current_days, reference_days=args.reference_days,
        decimate=args.decimate), indent=2))
