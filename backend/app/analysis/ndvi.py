import numpy as np


def ndvi(red, nir, valid=None) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red), from surface REFLECTANCE arrays.

    Returns NaN wherever the result is not meaningful: non-finite input,
    negative reflectance, a zero (or negative) denominator, or where the
    optional boolean `valid` mask is False (for example clouds or no-data).
    NDVI indicates vegetation greenness. It is not a direct measure of plant
    health, crop yield or drought.
    """
    red = np.asarray(red, dtype=float)
    nir = np.asarray(nir, dtype=float)
    if red.shape != nir.shape:
        raise ValueError("red and nir must have the same shape")
    denom = nir + red
    ok = np.isfinite(red) & np.isfinite(nir) & (red >= 0) & (nir >= 0) & (denom > 0)
    if valid is not None:
        valid = np.asarray(valid, dtype=bool)
        if valid.shape != red.shape:
            raise ValueError("valid mask must have the same shape as the bands")
        ok &= valid
    out = np.full(red.shape, np.nan)
    np.divide(nir - red, denom, out=out, where=ok)
    return out
