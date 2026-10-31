import argparse
import json

from app.analysis.categories import (
    category_fractions, classify_ndvi, load_categories, render_png,
)
from app.analysis.ndvi_scene import compute_scene, find_best_scene, summarize_arrays
from app.analysis.vegetation_store import ensure_table, record_result, scene_done
from app.aoi import aoi_bbox
from app.storage.db import DB_PATH, connect

DATA_DIR = DB_PATH.parent / "vegetation"


def run_vegetation_job(conn, collection="sentinel-2-c1-l2a", max_cloud=40.0, days=45,
                       decimate=4, force=False, finder=find_best_scene,
                       computer=compute_scene, out_dir=DATA_DIR) -> dict:
    """Find the clearest recent scene, compute NDVI, store PNG + metadata.

    Failures and "no scene" are recorded as such. Nothing is ever substituted.
    """
    ensure_table(conn)
    bbox = aoi_bbox(0.0)
    try:
        scene = finder(collection, bbox, days, max_cloud)
        if scene is None:
            message = (f"No scene under {max_cloud}% scene cloud cover in the "
                       f"last {days} days")
            record_result(conn, "no_scene", collection, decimate, error=message)
            return {"status": "no_scene", "error": message}
        if not force and scene_done(conn, scene["id"], decimate):
            return {"status": "cached", "scene_id": scene["id"]}

        comp = computer(scene, bbox, decimate)
        cats = load_categories()
        index = classify_ndvi(comp["values"], cats)
        fractions = category_fractions(index, cats)

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{scene['id']}_d{decimate}.png"
        path.write_bytes(render_png(index, cats))

        meta = summarize_arrays(scene, comp, decimate)
        meta.update({
            "collection": collection,
            "pixel_size_m_approx": 10 * decimate,
            "bounds_lonlat": list(comp["bounds_lonlat"]),
            "categories": [
                {"name": c["name"], "min": c["min"], "max": c["max"],
                 "color": c["color"], "fraction": fractions[c["name"]]}
                for c in cats
            ],
            "attribution": "Contains modified Copernicus Sentinel data "
                           f"{scene['datetime'][:4]}",
        })
        record_result(conn, "ok", collection, decimate, scene["id"],
                      scene["datetime"], str(path), meta)
        return {"status": "ok", "scene_id": scene["id"], "image_path": str(path),
                "fraction_with_ndvi": meta["fraction_with_ndvi"],
                "category_fractions": fractions}
    except Exception as exc:
        record_result(conn, "failed", collection, decimate, error=str(exc))
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="sentinel-2-c1-l2a")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--max-cloud", type=float, default=40.0)
    parser.add_argument("--decimate", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.decimate < 1:
        raise SystemExit("--decimate must be >= 1")
    print(json.dumps(run_vegetation_job(
        connect(), collection=args.collection, max_cloud=args.max_cloud,
        days=args.days, decimate=args.decimate, force=args.force), indent=2))
