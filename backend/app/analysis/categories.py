import io
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

CATEGORIES_PATH = Path(__file__).resolve().parents[3] / "config" / "ndvi_categories.json"


def load_categories(path: Path = CATEGORIES_PATH) -> list[dict]:
    """Load and validate NDVI categories (contiguous bands, hex colours)."""
    with open(path, encoding="utf-8-sig") as f:
        cats = json.load(f)["categories"]
    if not cats:
        raise ValueError("no categories defined")
    for i, c in enumerate(cats):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", c["color"]):
            raise ValueError(f"bad colour for {c['name']!r}")
        if not c["min"] < c["max"]:
            raise ValueError(f"min must be below max for {c['name']!r}")
        if i > 0 and cats[i - 1]["max"] != c["min"]:
            raise ValueError("categories must be contiguous (no gaps or overlaps)")
    return cats


def classify_ndvi(values: np.ndarray, categories: list[dict]) -> np.ndarray:
    """Category index per pixel (min inclusive, max exclusive, last max inclusive).

    NaN pixels get -1, meaning "no usable data".
    """
    out = np.full(values.shape, -1, dtype=np.int16)
    last = len(categories) - 1
    for i, c in enumerate(categories):
        upper = values <= c["max"] if i == last else values < c["max"]
        out[np.isfinite(values) & (values >= c["min"]) & upper] = i
    return out


def category_fractions(index: np.ndarray, categories: list[dict]) -> dict:
    """Share of USABLE pixels in each category."""
    n = int((index >= 0).sum())
    return {
        c["name"]: (round(float((index == i).sum()) / n, 3) if n else None)
        for i, c in enumerate(categories)
    }


def render_png(index: np.ndarray, categories: list[dict], alpha: int = 200) -> bytes:
    """RGBA PNG. Pixels with no usable data are fully transparent."""
    h, w = index.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for i, c in enumerate(categories):
        h_ = c["color"].lstrip("#")
        rgb = tuple(int(h_[k:k + 2], 16) for k in (0, 2, 4))
        mask = index == i
        rgba[mask, :3] = rgb
        rgba[mask, 3] = alpha
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG")
    return buf.getvalue()
