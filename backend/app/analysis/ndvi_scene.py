import argparse
import json
import math

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import Window, bounds as window_bounds, from_bounds

from app.analysis.ndvi import ndvi
from app.aoi import aoi_bbox
from app.ingestion.stac import search_items, summarize_item

# Sen2Cor scene classification codes (Sentinel-2 L2A SCL layer)
SCL_NAMES = {
    0: "no data", 1: "saturated/defective", 2: "dark area", 3: "cloud shadow",
    4: "vegetation", 5: "not vegetated", 6: "water", 7: "unclassified",
    8: "cloud medium probability", 9: "cloud high probability",
    10: "thin cirrus", 11: "snow/ice",
}
VALID_SCL = (4, 5, 6)
EPS = 1e-6


def window_for_native_bounds(ds, bounds):
    """Pixel window for bounds given in the dataset's own CRS, clipped to the raster.

    Returns (Window, coverage) where coverage is the fraction of the requested
    window that lies inside the raster (1.0 = fully covered).
    """
    west, south, east, north = bounds
    w = from_bounds(west, south, east, north, transform=ds.transform)
    col0 = math.floor(w.col_off + EPS)
    row0 = math.floor(w.row_off + EPS)
    width = math.ceil(w.width - EPS)
    height = math.ceil(w.height - EPS)
    if width <= 0 or height <= 0:
        raise ValueError("empty window")
    c0, r0 = max(col0, 0), max(row0, 0)
    c1, r1 = min(col0 + width, ds.width), min(row0 + height, ds.height)
    if c1 <= c0 or r1 <= r0:
        raise ValueError("scene does not cover the AOI")
    coverage = ((c1 - c0) * (r1 - r0)) / (width * height)
    return Window(c0, r0, c1 - c0, r1 - r0), coverage


def window_for_lonlat(ds, bbox):
    """Window for a (west, south, east, north) box given in degrees."""
    native = transform_bounds("EPSG:4326", ds.crs, *bbox)
    return window_for_native_bounds(ds, native)


def choose_scene(summaries, max_cloud):
    """Lowest scene-level cloud cover under the limit, or None."""
    ok = [
        s for s in summaries
        if s["cloud_cover"] is not None
        and s["cloud_cover"] <= max_cloud
        and all(k in s["bands"] for k in ("red", "nir", "scl"))
    ]
    return min(ok, key=lambda s: s["cloud_cover"]) if ok else None


def find_best_scene(collection, bbox, days, max_cloud):
    items = search_items(collection, bbox, days=days)
    return choose_scene([summarize_item(i) for i in items], max_cloud)


def scale_offset(info):
    if info.get("scale") is None or info.get("offset") is None:
        raise ValueError(
            "Reflectance scale/offset missing from the item metadata; refusing to guess"
        )
    return info["scale"], info["offset"]


def read_scene_ndvi(summary, bbox, decimate=4) -> dict:
    bands = summary["bands"]
    r_scale, r_off = scale_offset(bands["red"])
    n_scale, n_off = scale_offset(bands["nir"])
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    }
    with rasterio.Env(**env):
        with rasterio.open(bands["red"]["href"]) as red_ds, \
                rasterio.open(bands["nir"]["href"]) as nir_ds, \
                rasterio.open(bands["scl"]["href"]) as scl_ds:
            if red_ds.transform != nir_ds.transform or red_ds.shape != nir_ds.shape:
                raise ValueError("red and nir grids differ")
            if scl_ds.crs != red_ds.crs:
                raise ValueError("scl and red use different coordinate systems")

            win, coverage = window_for_lonlat(red_ds, bbox)
            shape = (max(1, int(win.height) // decimate),
                     max(1, int(win.width) // decimate))
            red_dn = red_ds.read(1, window=win, out_shape=shape,
                                 resampling=Resampling.average)
            nir_dn = nir_ds.read(1, window=win, out_shape=shape,
                                 resampling=Resampling.average)
            native_bounds = window_bounds(win, red_ds.transform)
            scl_win, _ = window_for_native_bounds(scl_ds, native_bounds)
            scl = scl_ds.read(1, window=scl_win, out_shape=shape,
                              resampling=Resampling.nearest)
            bounds_lonlat = transform_bounds(red_ds.crs, "EPSG:4326", *native_bounds)

    red = np.where(red_dn > 0, red_dn * r_scale + r_off, np.nan)
    nir = np.where(nir_dn > 0, nir_dn * n_scale + n_off, np.nan)
    scl_valid = np.isin(scl, VALID_SCL)
    valid = scl_valid & (red_dn > 0) & (nir_dn > 0)
    values = ndvi(red, nir, valid)

    finite = values[np.isfinite(values)]
    stats = None
    bins = None
    if finite.size:
        p5, median, p95 = np.percentile(finite, [5, 50, 95])
        stats = {
            "min": round(float(finite.min()), 3), "p5": round(float(p5), 3),
            "median": round(float(median), 3), "mean": round(float(finite.mean()), 3),
            "p95": round(float(p95), 3), "max": round(float(finite.max()), 3),
        }
        edges = [-1.0, 0.0, 0.2, 0.4, 0.6, 1.0001]
        counts, _ = np.histogram(finite, bins=edges)
        labels = ["<0", "0-0.2", "0.2-0.4", "0.4-0.6", ">0.6"]
        bins = {l: round(float(c) / finite.size, 3) for l, c in zip(labels, counts)}

    classes, counts = np.unique(scl, return_counts=True)
    return {
        "scene_id": summary["id"],
        "acquired_utc": summary["datetime"],
        "scene_cloud_cover_percent": summary["cloud_cover"],
        "aoi_coverage_fraction": round(float(coverage), 3),
        "decimate": decimate,
        "pixels": [int(shape[0]), int(shape[1])],
        "bounds_lonlat": [round(v, 4) for v in bounds_lonlat],
        "scl_fractions_in_aoi": {
            SCL_NAMES.get(int(c), f"class {int(c)}"): round(float(n) / scl.size, 3)
            for c, n in zip(classes, counts)
        },
        "fraction_valid_by_scl": round(float(scl_valid.mean()), 3),
        "fraction_with_ndvi": round(float(finite.size) / values.size, 3),
        "ndvi_stats": stats,
        "ndvi_class_fractions": bins,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="sentinel-2-c1-l2a")
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--max-cloud", type=float, default=40.0)
    parser.add_argument("--decimate", type=int, default=4)
    args = parser.parse_args()
    if args.decimate < 1:
        raise SystemExit("--decimate must be >= 1")

    bbox = aoi_bbox(0.0)
    scene = find_best_scene(args.collection, bbox, args.days, args.max_cloud)
    if scene is None:
        print(
            f"No scene under {args.max_cloud}% scene cloud cover in the last "
            f"{args.days} days. This is a real result: no older or simulated "
            "data is substituted."
        )
    else:
        print(json.dumps(read_scene_ndvi(scene, bbox, args.decimate), indent=2))
