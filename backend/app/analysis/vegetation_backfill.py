import argparse
import json

from app.analysis.vegetation_job import run_vegetation_job
from app.aoi import aoi_bbox
from app.ingestion.stac import search_items, summarize_item
from app.storage.db import connect


def select_scenes(summaries, max_cloud, limit):
    """Usable scenes (cloud under the limit, red/nir/scl present), newest first."""
    ok = [
        s for s in summaries
        if s["cloud_cover"] is not None
        and s["cloud_cover"] <= max_cloud
        and all(k in s["bands"] for k in ("red", "nir", "scl"))
    ]
    ok.sort(key=lambda s: s["datetime"], reverse=True)
    return ok[:limit]


def run_backfill(conn, collection="sentinel-2-c1-l2a", days=90, max_cloud=40.0,
                 limit=6, decimate=4, force=False, searcher=search_items,
                 job=run_vegetation_job) -> list[dict]:
    """Process several recent real scenes, one stored result per scene."""
    bbox = aoi_bbox(0.0)
    summaries = [summarize_item(i) for i in searcher(collection, bbox, days=days)]
    results = []
    for scene in select_scenes(summaries, max_cloud, limit):
        res = job(conn, collection=collection, max_cloud=max_cloud, days=days,
                  decimate=decimate, force=force,
                  finder=lambda c, b, d, m, s=scene: s)
        results.append(res)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="sentinel-2-c1-l2a")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--max-cloud", type=float, default=40.0)
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--decimate", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.decimate < 1 or args.limit < 1:
        raise SystemExit("--decimate and --limit must be >= 1")
    out = run_backfill(connect(), args.collection, args.days, args.max_cloud,
                       args.limit, args.decimate, args.force)
    print(json.dumps([{k: r.get(k) for k in ("status", "scene_id", "error")}
                      for r in out], indent=2))
