import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

CHANGE_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ndvi_change.json"
CLASS_NAMES = ("decrease", "stable", "increase")
ALPHAS = (210, 70, 210)  # stable is faint so it differs from "not comparable" (0)


def load_change_config(path: Path = CHANGE_CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        cfg = json.load(f)
    if not cfg["decrease_threshold"] < 0 < cfg["increase_threshold"]:
        raise ValueError("decrease_threshold must be negative, increase_threshold positive")
    if not 0 < cfg["min_usable_fraction"] <= 1:
        raise ValueError("min_usable_fraction must be in (0, 1]")
    if cfg["min_gap_days"] < 1 or cfg["max_reference_tries"] < 1:
        raise ValueError("min_gap_days and max_reference_tries must be >= 1")
    for name in CLASS_NAMES:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", cfg["colors"][name]):
            raise ValueError(f"bad colour for {name}")
    return cfg


def ndvi_difference(current, reference) -> np.ndarray:
    """current - reference. NaN wherever either date has no usable NDVI."""
    current = np.asarray(current, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if current.shape != reference.shape:
        raise ValueError("scenes have different grids")
    return current - reference


def classify_change(diff: np.ndarray, cfg: dict) -> np.ndarray:
    """-1 not comparable, 0 decrease, 1 stable, 2 increase."""
    out = np.full(diff.shape, -1, dtype=np.int8)
    ok = np.isfinite(diff)
    out[ok] = 1
    out[ok & (diff <= cfg["decrease_threshold"])] = 0
    out[ok & (diff >= cfg["increase_threshold"])] = 2
    return out


def change_summary(index: np.ndarray, diff: np.ndarray, pixel_size_m: float) -> dict:
    usable = index >= 0
    n = int(usable.sum())
    px_km2 = (pixel_size_m / 1000.0) ** 2
    counts = {name: int((index == i).sum()) for i, name in enumerate(CLASS_NAMES)}
    return {
        "overlap_fraction": round(n / index.size, 3),
        "class_fractions": {k: (round(v / n, 3) if n else None) for k, v in counts.items()},
        "area_km2": {k: round(v * px_km2, 4) for k, v in counts.items()},
        "mean_change": round(float(diff[usable].mean()), 3) if n else None,
    }


def render_change_png(index: np.ndarray, cfg: dict) -> bytes:
    h, w = index.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for i, name in enumerate(CLASS_NAMES):
        hx = cfg["colors"][name].lstrip("#")
        mask = index == i
        rgba[mask, :3] = tuple(int(hx[k:k + 2], 16) for k in (0, 2, 4))
        rgba[mask, 3] = ALPHAS[i]
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()
