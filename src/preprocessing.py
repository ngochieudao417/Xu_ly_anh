"""
Preprocessing pipeline building blocks: NoData/invalid-value handling,
cloud masking, AOI clipping, reflectance scaling and memory-safe pixel
sampling for one Sentinel-2 image at a time.

All raster reading here goes through rasterio's block/window API so a
full-resolution multi-band image is never materialised in memory at once.
Random sampling uses a streaming reservoir-sampling algorithm for the same
reason.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask

from src import config as cfg


class ReservoirSampler:
    """
    Streaming, memory-bounded uniform random sample of rows from an
    arbitrarily long stream of (n_i, n_features) chunks (classic
    Algorithm R, vectorised across each chunk).
    """

    def __init__(self, k: int, n_features: int, rng: np.random.Generator, dtype=np.float32):
        self.k = k
        self.reservoir = np.empty((k, n_features), dtype=dtype)
        self.filled = 0
        self.seen = 0
        self.rng = rng

    def update(self, chunk: np.ndarray) -> None:
        if chunk.size == 0:
            return
        start = 0
        if self.filled < self.k:
            take = min(self.k - self.filled, chunk.shape[0])
            self.reservoir[self.filled:self.filled + take] = chunk[:take]
            self.filled += take
            self.seen += take
            start = take

        remaining = chunk[start:]
        m = remaining.shape[0]
        if m == 0:
            return

        # 1-based stream positions of the remaining pixels in this chunk
        stream_positions = self.seen + np.arange(1, m + 1)
        r = self.rng.integers(0, stream_positions)  # r_j in [0, stream_positions[j])
        self.seen += m

        hits = np.nonzero(r < self.k)[0]
        for h in hits:
            self.reservoir[r[h]] = remaining[h]

    def values(self) -> np.ndarray:
        return self.reservoir[: self.filled]


def scale_reflectance(raw_block: np.ndarray) -> np.ndarray:
    """Convert raw digital numbers to unitless reflectance (0-1 range)."""
    return raw_block.astype(np.float32) / cfg.REFLECTANCE_SCALE


def _load_aoi_mask_geoms(dst_crs) -> Optional[list]:
    """Load the AOI boundary (if present) reprojected to the raster CRS."""
    path = cfg.aoi_path()
    if not path.exists():
        return None
    import geopandas as gpd

    gdf = gpd.read_file(path)
    if gdf.crs is not None and dst_crs is not None:
        gdf = gdf.to_crs(dst_crs)
    return list(gdf.geometry)


def classify_pixel_validity(
    band_stack: np.ndarray,
    nodata,
    cloud_block: Optional[np.ndarray] = None,
    aoi_inside: Optional[np.ndarray] = None,
) -> dict:
    """
    Given a (n_bands, rows, cols) raw raster block, return boolean masks
    (each shape (rows, cols)) classifying every pixel as missing,
    out-of-range/invalid, cloud-flagged, outside-AOI, and finally valid.

    A pixel counts as missing if ANY band is NaN/Inf/NoData at that
    location; invalid if any band is finite but outside the physically
    valid raw reflectance range.
    """
    finite = np.isfinite(band_stack)
    missing = ~finite.all(axis=0)
    if nodata is not None:
        missing |= (band_stack == nodata).any(axis=0)

    with np.errstate(invalid="ignore"):
        out_of_range = (
            (band_stack < cfg.VALID_RAW_MIN) | (band_stack > cfg.VALID_RAW_MAX)
        ) & finite
    invalid_range = out_of_range.any(axis=0) & ~missing

    cloud = np.zeros(missing.shape, dtype=bool)
    if cloud_block is not None:
        cloud = cloud_block.astype(bool)

    outside_aoi = np.zeros(missing.shape, dtype=bool)
    if aoi_inside is not None:
        outside_aoi = ~aoi_inside

    valid = ~missing & ~invalid_range & ~cloud & ~outside_aoi
    return {
        "missing": missing,
        "invalid_range": invalid_range,
        "cloud": cloud,
        "outside_aoi": outside_aoi,
        "valid": valid,
    }


def sample_valid_pixels(
    year: int,
    n_samples: int = cfg.N_SAMPLES_PER_YEAR,
    band_names: list[str] = cfg.BAND_NAMES,
    random_seed: int = cfg.RANDOM_SEED,
) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    """
    Stream through one year's image block-by-block, classify every pixel
    (missing / out-of-range / cloud / outside-AOI / valid), and draw a
    uniform random sample of up to `n_samples` valid pixels using
    reservoir sampling.

    Returns:
        samples: dict band_name -> 1D float32 array of scaled reflectance
                 for the sampled valid pixels (empty if none valid)
        counts: dict with total/valid/missing/invalid_range/cloud/
                outside_aoi/sampled pixel counts
    """
    image_path = cfg.raw_image_path(year)
    if not image_path.exists():
        raise FileNotFoundError(f"Raw image for year {year} not found at {image_path}")

    rng = np.random.default_rng(random_seed + year)
    counts = dict(total=0, valid=0, missing=0, invalid_range=0, cloud=0, outside_aoi=0)

    with rasterio.open(image_path) as src:
        if src.count != len(band_names):
            raise ValueError(
                f"{image_path.name}: expected {len(band_names)} bands "
                f"({band_names}) but file has {src.count}."
            )

        cloud_path = cfg.cloud_mask_path(year)
        cloud_src = rasterio.open(cloud_path) if cloud_path.exists() else None

        aoi_geoms = _load_aoi_mask_geoms(src.crs)

        sampler = ReservoirSampler(n_samples, len(band_names), rng)

        try:
            for _, window in src.block_windows(1):
                block = src.read(window=window).astype(np.float32)  # (bands, rows, cols)
                counts["total"] += block.shape[1] * block.shape[2]

                cloud_block = None
                if cloud_src is not None:
                    cloud_block = cloud_src.read(1, window=window)

                aoi_inside = None
                if aoi_geoms is not None:
                    from rasterio.features import geometry_mask

                    window_transform = src.window_transform(window)
                    # geometry_mask returns True OUTSIDE geometries by default
                    aoi_inside = ~geometry_mask(
                        aoi_geoms,
                        out_shape=(window.height, window.width),
                        transform=window_transform,
                        invert=False,
                    )

                masks = classify_pixel_validity(block, src.nodata, cloud_block, aoi_inside)
                counts["missing"] += int(masks["missing"].sum())
                counts["invalid_range"] += int(masks["invalid_range"].sum())
                counts["cloud"] += int(masks["cloud"].sum())
                counts["outside_aoi"] += int(masks["outside_aoi"].sum())
                counts["valid"] += int(masks["valid"].sum())

                if masks["valid"].any():
                    valid_pixels = block[:, masks["valid"]].T  # (n_valid, n_bands)
                    sampler.update(scale_reflectance(valid_pixels))
        finally:
            if cloud_src is not None:
                cloud_src.close()

    reservoir = sampler.values()
    samples = {name: reservoir[:, i] for i, name in enumerate(band_names)}
    counts["sampled"] = reservoir.shape[0]
    return samples, counts


def extract_features_at_points(year: int, points_gdf, band_names: list[str] = cfg.BAND_NAMES):
    """
    Sample raster band values at a set of point geometries (e.g. training
    samples with a `class`/`label` column). Uses rasterio's point sampling,
    which reads only the pixels needed rather than the full raster.

    Returns a pandas DataFrame with one row per point: band columns plus
    any non-geometry columns already present in `points_gdf` (e.g. class).
    """
    import pandas as pd

    image_path = cfg.raw_image_path(year)
    if not image_path.exists():
        raise FileNotFoundError(f"Raw image for year {year} not found at {image_path}")

    with rasterio.open(image_path) as src:
        pts = points_gdf.to_crs(src.crs) if points_gdf.crs else points_gdf
        coords = [(geom.x, geom.y) for geom in pts.geometry]
        sampled = np.array(list(src.sample(coords)), dtype=np.float32)  # (n_points, n_bands)

    scaled = scale_reflectance(sampled)
    df = pd.DataFrame(scaled, columns=band_names)
    extra_cols = [c for c in points_gdf.columns if c != "geometry"]
    for col in extra_cols:
        df[col] = points_gdf[col].to_numpy()
    df["year"] = year
    return df


def read_decimated_bands(
    year: int,
    band_names: list[str] = cfg.BAND_NAMES,
    max_size: int = 1500,
) -> tuple[dict[str, np.ndarray], "rasterio.Affine"]:
    """
    Read a reduced-resolution ("overview-like") version of the requested
    bands for display/spatial-map purposes, decimated so that the longer
    image dimension is at most `max_size` pixels. This avoids ever loading
    a full-resolution scene into memory just to make a preview figure.

    Returns (dict band_name -> 2D scaled-reflectance array, output transform).
    """
    image_path = cfg.raw_image_path(year)
    if not image_path.exists():
        raise FileNotFoundError(f"Raw image for year {year} not found at {image_path}")

    with rasterio.open(image_path) as src:
        if src.count != len(cfg.BAND_NAMES):
            raise ValueError(
                f"{image_path.name}: expected {len(cfg.BAND_NAMES)} bands but has {src.count}."
            )
        scale = min(1.0, max_size / max(src.width, src.height))
        out_height = max(1, int(src.height * scale))
        out_width = max(1, int(src.width * scale))

        out_transform = src.transform * src.transform.scale(
            src.width / out_width, src.height / out_height
        )

        bands = {}
        for name in band_names:
            band_idx = cfg.BAND_NAMES.index(name) + 1
            data = src.read(
                band_idx,
                out_shape=(out_height, out_width),
                resampling=rasterio.enums.Resampling.average,
            )
            bands[name] = scale_reflectance(data)
    return bands, out_transform


def clip_to_aoi_and_save(year: int) -> Optional[Path]:
    """
    Clip a year's raw image to the AOI boundary (if one is available) and
    write the result to data/processed/<year>_processed.tif. Returns the
    output path, or None (with no file written) if no AOI is defined --
    this is reported as a limitation rather than silently skipped.
    """
    image_path = cfg.raw_image_path(year)
    aoi_file = cfg.aoi_path()
    if not aoi_file.exists():
        return None

    import geopandas as gpd

    with rasterio.open(image_path) as src:
        gdf = gpd.read_file(aoi_file)
        if gdf.crs is not None:
            gdf = gdf.to_crs(src.crs)
        out_image, out_transform = rio_mask(src, list(gdf.geometry), crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        })

    out_path = cfg.DATA_PROCESSED_DIR / f"{year}_processed.tif"
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(out_image)
    return out_path
