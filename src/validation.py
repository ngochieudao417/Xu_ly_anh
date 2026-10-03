"""
Data validation utilities for the Long Thanh land-cover project.

These functions check that raw/processed satellite images exist, are
readable, and report their structural metadata and basic quality metrics
(NoData counts, band statistics) *without* loading a full raster into
memory -- all statistics are accumulated block-by-block using rasterio's
windowed reading.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import rasterio

from src import config as cfg


def file_exists(path: Path) -> bool:
    """Return True if `path` exists and is a regular file."""
    return Path(path).is_file()


def get_raster_metadata(path: Path) -> dict:
    """
    Read structural metadata of a raster without loading pixel data.

    Returns band count, width/height, CRS, resolution, dtype, bounds and
    the declared NoData value.
    """
    path = Path(path)
    if not file_exists(path):
        raise FileNotFoundError(f"Raster file not found: {path}")

    with rasterio.open(path) as src:
        meta = {
            "path": str(path),
            "band_count": src.count,
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs) if src.crs else None,
            "resolution_x": abs(src.transform.a),
            "resolution_y": abs(src.transform.e),
            "dtype": src.dtypes[0],
            "bounds": tuple(src.bounds),
            "nodata": src.nodata,
            "total_pixels": src.width * src.height * src.count,
        }
    return meta


def compute_band_statistics(path: Path, band_names: Optional[list[str]] = None) -> dict:
    """
    Compute per-band min/max/mean/std and NoData counts using chunked
    (windowed) reading, so the full raster is never held in memory at once.

    Returns a dict keyed by band name, each containing:
        count, mean, std, min, max, nodata_count, nodata_pct
    """
    path = Path(path)
    with rasterio.open(path) as src:
        n_bands = src.count
        names = band_names or [f"B{i + 1}" for i in range(n_bands)]
        if len(names) != n_bands:
            raise ValueError(
                f"Expected {len(names)} band names but raster has {n_bands} bands: {path}"
            )

        nodata = src.nodata
        stats = {
            name: {
                "sum": 0.0,
                "sumsq": 0.0,
                "min": np.inf,
                "max": -np.inf,
                "valid_count": 0,
                "nodata_count": 0,
                "total_count": 0,
            }
            for name in names
        }

        for _, window in src.block_windows(1):
            for band_idx, name in enumerate(names, start=1):
                block = src.read(band_idx, window=window).astype(np.float64)
                total = block.size

                invalid_mask = ~np.isfinite(block)
                if nodata is not None:
                    invalid_mask |= (block == nodata)

                valid = block[~invalid_mask]

                s = stats[name]
                s["total_count"] += total
                s["nodata_count"] += int(invalid_mask.sum())
                if valid.size:
                    s["valid_count"] += valid.size
                    s["sum"] += float(valid.sum())
                    s["sumsq"] += float(np.square(valid).sum())
                    s["min"] = min(s["min"], float(valid.min()))
                    s["max"] = max(s["max"], float(valid.max()))

    results = {}
    for name, s in stats.items():
        valid_count = s["valid_count"]
        mean = s["sum"] / valid_count if valid_count else float("nan")
        variance = (s["sumsq"] / valid_count - mean ** 2) if valid_count else float("nan")
        std = float(np.sqrt(max(variance, 0.0))) if valid_count else float("nan")
        results[name] = {
            "count": valid_count,
            "mean": mean,
            "std": std,
            "min": s["min"] if valid_count else float("nan"),
            "max": s["max"] if valid_count else float("nan"),
            "nodata_count": s["nodata_count"],
            "nodata_pct": 100.0 * s["nodata_count"] / s["total_count"] if s["total_count"] else 0.0,
            "total_count": s["total_count"],
        }
    return results


def check_years_consistency(metadata_by_year: dict[int, dict]) -> list[str]:
    """
    Compare structural metadata (band count, CRS, resolution) across years
    and return a list of human-readable inconsistency warnings. Empty list
    means all available years are consistent.
    """
    issues = []
    years = sorted(metadata_by_year)
    if len(years) < 2:
        return issues

    reference_year = years[0]
    reference = metadata_by_year[reference_year]

    for year in years[1:]:
        meta = metadata_by_year[year]
        if meta["band_count"] != reference["band_count"]:
            issues.append(
                f"Band count mismatch: {reference_year} has {reference['band_count']} bands, "
                f"{year} has {meta['band_count']} bands."
            )
        if meta["crs"] != reference["crs"]:
            issues.append(
                f"CRS mismatch: {reference_year} is {reference['crs']}, {year} is {meta['crs']}."
            )
        if not np.isclose(meta["resolution_x"], reference["resolution_x"], rtol=1e-3):
            issues.append(
                f"Resolution mismatch: {reference_year} is {reference['resolution_x']:.2f}m, "
                f"{year} is {meta['resolution_x']:.2f}m."
            )
    return issues


def check_invalid_reflectance(band_stats: dict) -> dict:
    """
    Flag bands whose min/max fall outside the physically valid raw
    reflectance range defined in config (does not modify data, reporting
    only).
    """
    flags = {}
    for name, s in band_stats.items():
        out_of_range = (
            np.isfinite(s["min"]) and s["min"] < cfg.VALID_RAW_MIN
        ) or (
            np.isfinite(s["max"]) and s["max"] > cfg.VALID_RAW_MAX
        )
        flags[name] = out_of_range
    return flags


def generate_qc_report_text(year: int, meta: dict, band_stats: dict, indices_present: list[str]) -> str:
    """Render the plain-text QC report block described in the task spec."""
    total_pixels = meta["width"] * meta["height"]
    valid_counts = [s["valid_count"] if "valid_count" in s else s["count"] for s in band_stats.values()]
    # Use the first band as the representative valid/missing pixel count
    first_band = next(iter(band_stats.values()))
    valid_pixels = first_band["count"]
    missing_pixels = total_pixels - valid_pixels
    missing_pct = 100.0 * missing_pixels / total_pixels if total_pixels else 0.0

    lines = [
        "========== DATA QUALITY REPORT ==========",
        "",
        f"Year: {year}",
        "",
        f"Total pixels: {total_pixels:,}",
        f"Valid pixels: {valid_pixels:,}",
        f"Missing pixels: {missing_pixels:,}",
        f"Missing percentage: {missing_pct:.3f}%",
        "",
        "Bands:",
    ]
    for name in cfg.BAND_NAMES:
        mark = "✓" if name in band_stats else "✗ (missing)"
        lines.append(f"{name} {mark}")

    lines.append("")
    lines.append("Indices:")
    for name in cfg.INDEX_NAMES:
        mark = "✓" if name in indices_present else "✗ (not computed)"
        lines.append(f"{name} {mark}")

    lines.extend([
        "",
        f"CRS: {meta['crs']}",
        f"Resolution: {meta['resolution_x']:.2f} x {meta['resolution_y']:.2f} m",
        "",
        "==========================================",
    ])
    return "\n".join(lines)
