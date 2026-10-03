#!/usr/bin/env python3
"""
Fetch real Sentinel-2 L2A imagery for the Long Thanh Airport study area from
the public AWS "sentinel-cogs" archive (via Element84's Earth Search STAC
API, https://earth-search.aws.element84.com/v1) and write it into
data/raw/<year>.tif in the layout expected by src/config.py.

No credentials are needed -- sentinel-cogs is a public, requester-does-not-
pay bucket, and rasterio reads each band as a windowed (range-request) read
over the AOI only, never downloading a full ~110x110 km tile.

Scene selection (one per study year) was done manually beforehand by
querying the STAC API for low cloud cover AND full bbox coverage of the AOI
(see the query transcript in this session) -- STAC_ITEMS below is the
result, pinned for reproducibility. Re-running this script always downloads
the same scenes.

Usage:
    python scripts/fetch_sentinel2_data.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from src import config as cfg

STAC_API = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# AOI around Long Thanh International Airport (10.7844 N, 107.0411 E),
# ~30 km x 21 km, chosen to sit fully inside a single MGRS tile (48PYS) so
# every year comes from one seamless scene with no mosaicking needed.
AOI_WGS84 = (106.90, 10.65, 107.18, 10.84)  # lon_min, lat_min, lon_max, lat_max

# One STAC item id per study year: lowest cloud cover among scenes whose
# footprint fully contains AOI_WGS84.
STAC_ITEMS = {
    2018: "S2A_48PYS_20181129_0_L2A",
    2020: "S2B_48PYS_20201203_1_L2A",
    2022: "S2A_48PYS_20220422_0_L2A",
    2024: "S2B_48PYS_20240406_0_L2A",
    2026: "S2C_48PYS_20260322_0_L2A",
}

# config.BAND_NAMES -> Earth Search asset key
BAND_ASSET_KEYS = {
    "B2": "blue", "B3": "green", "B4": "red",
    "B8": "nir", "B11": "swir16", "B12": "swir22",
}

# Sentinel-2 Scene Classification Layer codes considered cloud/shadow/cirrus.
SCL_CLOUD_CODES = {3, 8, 9, 10}


def fetch_item(item_id: str) -> dict:
    url = f"{STAC_API}/collections/{COLLECTION}/items/{item_id}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def read_band_window(href: str, target_shape: tuple[int, int], resampling: Resampling):
    """Read only the AOI window of a remote COG, resampled to target_shape."""
    with rasterio.open(href) as src:
        bounds_utm = transform_bounds("EPSG:4326", src.crs, *AOI_WGS84)
        window = from_bounds(*bounds_utm, transform=src.transform).round_offsets().round_lengths()
        data = src.read(
            1, window=window, out_shape=target_shape, resampling=resampling,
        )
        window_transform = src.window_transform(window)
        # Rescale the transform to account for out_shape resampling.
        scale_x = window.width / target_shape[1]
        scale_y = window.height / target_shape[0]
        out_transform = window_transform * window_transform.scale(scale_x, scale_y)
        return data, out_transform, src.crs, src.nodata


def process_year(year: int, item_id: str) -> None:
    print(f"\n=== {year}: {item_id} ===")
    t0 = time.time()
    item = fetch_item(item_id)
    assets = item["assets"]

    # Reference grid: the 10 m blue band, read once to fix width/height/transform.
    ref_href = assets[BAND_ASSET_KEYS["B2"]]["href"]
    with rasterio.open(ref_href) as src:
        bounds_utm = transform_bounds("EPSG:4326", src.crs, *AOI_WGS84)
        ref_window = from_bounds(*bounds_utm, transform=src.transform).round_offsets().round_lengths()
        target_shape = (int(ref_window.height), int(ref_window.width))
        crs = src.crs
        nodata = src.nodata

    band_arrays = {}
    for band_name in cfg.BAND_NAMES:
        asset_key = BAND_ASSET_KEYS[band_name]
        href = assets[asset_key]["href"]
        gsd = assets[asset_key].get("gsd", 10)
        resampling = Resampling.nearest if gsd == 10 else Resampling.bilinear
        arr, out_transform, band_crs, band_nodata = read_band_window(href, target_shape, resampling)
        assert band_crs == crs, f"CRS mismatch for {band_name} in {item_id}"
        band_arrays[band_name] = arr
        print(f"  {band_name} ({asset_key}, {gsd}m native): shape={arr.shape} "
              f"min={arr.min()} max={arr.max()}")

    stacked = np.stack([band_arrays[b] for b in cfg.BAND_NAMES], axis=0)
    out_path = cfg.raw_image_path(year)
    with rasterio.open(
        out_path, "w", driver="GTiff", height=target_shape[0], width=target_shape[1],
        count=len(cfg.BAND_NAMES), dtype=stacked.dtype, crs=crs, transform=out_transform,
        nodata=nodata, compress="deflate",
    ) as dst:
        dst.write(stacked)
        for i, band_name in enumerate(cfg.BAND_NAMES, start=1):
            dst.set_band_description(i, band_name)
    print(f"  -> wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")

    # Cloud mask, derived from the real Scene Classification Layer (SCL).
    scl_href = assets["scl"]["href"]
    scl_arr, scl_transform, scl_crs, _ = read_band_window(scl_href, target_shape, Resampling.nearest)
    cloud_mask = np.isin(scl_arr, list(SCL_CLOUD_CODES)).astype(np.uint8)
    mask_path = cfg.cloud_mask_path(year)
    with rasterio.open(
        mask_path, "w", driver="GTiff", height=target_shape[0], width=target_shape[1],
        count=1, dtype=np.uint8, crs=crs, transform=out_transform, nodata=255, compress="deflate",
    ) as dst:
        dst.write(cloud_mask, 1)
    cloud_pct = 100 * cloud_mask.mean()
    print(f"  -> wrote {mask_path} (cloud/shadow/cirrus: {cloud_pct:.2f}% of AOI, from SCL)")
    print(f"  elapsed: {time.time() - t0:.1f}s")


def write_aoi_boundary() -> None:
    import geopandas as gpd
    from shapely.geometry import box

    geom = box(*AOI_WGS84)
    gdf = gpd.GeoDataFrame(
        {"name": ["Long Thanh Airport study area"]}, geometry=[geom], crs="EPSG:4326"
    )
    gdf.to_file(cfg.aoi_path(), driver="GeoJSON")
    print(f"\nWrote AOI boundary -> {cfg.aoi_path()}")


def main():
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        VSI_CACHE="TRUE",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    ):
        for year, item_id in STAC_ITEMS.items():
            process_year(year, item_id)
        write_aoi_boundary()

    print("\n[done] All years fetched. Run `python scripts/run_pipeline.py` next.")


if __name__ == "__main__":
    main()
