"""
Spectral index calculation and tabular feature-dataset construction.

All operations here are vectorised NumPy operations on already-sampled
1D pixel arrays (see src.preprocessing.sample_valid_pixels), never on a
full 2D/3D raster, keeping memory use bounded regardless of image size.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src import config as cfg


def safe_divide(numerator: np.ndarray, denominator: np.ndarray, fill: float = np.nan) -> np.ndarray:
    """Elementwise division that returns `fill` wherever denominator == 0."""
    numerator = np.asarray(numerator, dtype=np.float64)
    denominator = np.asarray(denominator, dtype=np.float64)
    result = np.full_like(numerator, fill, dtype=np.float64)
    nonzero = denominator != 0
    with np.errstate(divide="ignore", invalid="ignore"):
        result[nonzero] = numerator[nonzero] / denominator[nonzero]
    return result.astype(np.float32)


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red). Vegetation indicator."""
    return safe_divide(nir - red, nir + red)


def compute_ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDBI = (SWIR - NIR) / (SWIR + NIR). Built-up area indicator."""
    return safe_divide(swir - nir, swir + nir)


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI = (Green - NIR) / (Green + NIR). Water indicator."""
    return safe_divide(green - nir, green + nir)


def compute_indices(bands: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Compute NDVI/NDBI/NDWI from a dict of band arrays (any of the sampling
    or extraction functions in src.preprocessing produce this shape).
    SWIR1 (B11) is used for NDBI, matching the task's index definitions.
    """
    required = {"B3", "B4", "B8", "B11"}
    missing = required - bands.keys()
    if missing:
        raise ValueError(f"Cannot compute indices, missing bands: {sorted(missing)}")

    return {
        "NDVI": compute_ndvi(bands["B8"], bands["B4"]),
        "NDBI": compute_ndbi(bands["B11"], bands["B8"]),
        "NDWI": compute_ndwi(bands["B3"], bands["B8"]),
    }


def build_feature_dataframe(
    year: int,
    bands: dict[str, np.ndarray],
    class_labels: Optional[np.ndarray] = None,
) -> pd.DataFrame:
    """
    Assemble the final tabular feature dataset for one year:
    year, B2..B12, NDVI, NDBI, NDWI, [class].
    """
    indices = compute_indices(bands)
    data = {"year": year}
    for name in cfg.BAND_NAMES:
        if name in bands:
            data[name] = bands[name]
    data.update(indices)

    df = pd.DataFrame(data)
    if class_labels is not None:
        df["class"] = np.asarray(class_labels)
        if df["class"].dtype.kind in "iu":
            df["class_name"] = df["class"].map(cfg.CLASS_MAP)
    return df


def combine_years(dfs_by_year: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """Concatenate per-year feature DataFrames into one long-format table."""
    if not dfs_by_year:
        return pd.DataFrame(columns=["year", *cfg.BAND_NAMES, *cfg.INDEX_NAMES])
    return pd.concat(
        [dfs_by_year[y] for y in sorted(dfs_by_year)], ignore_index=True
    )
