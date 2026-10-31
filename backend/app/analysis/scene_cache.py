from pathlib import Path

import numpy as np

from app.analysis.ndvi_scene import compute_scene

CACHE_VERSION = "v1"


def cache_path(cache_dir, scene_id, bbox, decimate) -> Path:
    tag = "_".join(f"{v:g}" for v in bbox)
    return Path(cache_dir) / f"{scene_id}_d{decimate}_{tag}_{CACHE_VERSION}.npz"


def load_or_compute(scene, bbox, decimate, cache_dir, computer=compute_scene) -> dict:
    """NDVI arrays for a scene, from the on-disk cache when available."""
    path = cache_path(cache_dir, scene["id"], bbox, decimate)
    if path.exists():
        with np.load(path) as z:
            return {
                "values": z["values"], "scl": z["scl"],
                "bounds_lonlat": tuple(float(v) for v in z["bounds"]),
                "coverage": float(z["coverage"]),
            }
    comp = computer(scene, bbox, decimate)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        values=np.asarray(comp["values"]).astype("float32"),
        scl=np.asarray(comp["scl"]).astype("uint8"),
        bounds=np.array(comp["bounds_lonlat"], dtype=float),
        coverage=np.array(comp["coverage"]),
    )
    return comp
