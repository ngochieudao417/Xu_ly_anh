#!/usr/bin/env python3
"""Reproducible W4 analysis using local Sentinel-2 and public WorldCover.

The local rasters are single scenes from STAC, not Cuong's GEE composites.
This script preserves that distinction in its machine-readable metadata.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import requests
from affine import Affine

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, rasterize
from rasterio.windows import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom
from scipy import ndimage as ndi
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix
from shapely.geometry import shape, LineString, mapping, box
from shapely.ops import transform as shp_transform
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "w4"
OUT.mkdir(parents=True, exist_ok=True)
AOI = [106.98849946776265, 10.736755380981812, 107.09698945799703, 10.814327243656404]
CENTER = (107.04111, 10.78444)
WORLD_COVER_URL = "https://esa-worldcover.s3.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N09E105_Map.tif"
CLASS_NAMES = ["Water", "Vegetation", "Bare Soil", "Built-up"]
BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]
COLORS = ["#1a73e8", "#34a853", "#c9a66b", "#d93025"]
STAC_ITEMS = {2022: "S2A_48PYS_20220422_0_L2A", 2024: "S2B_48PYS_20240406_0_L2A"}


def bicubic_swir(year, shape_hw, transform, crs):
    """Read native 20 m B11/B12 COGs and resample to the 10 m AOI grid."""
    cache = OUT / f"bicubic_swir_{year}.tif"
    if cache.exists():
        with rasterio.open(cache) as src:
            if src.shape == shape_hw and src.transform == transform:
                return src.read()
    url = ("https://earth-search.aws.element84.com/v1/collections/"
           f"sentinel-2-l2a/items/{STAC_ITEMS[year]}")
    item = requests.get(url, timeout=30)
    item.raise_for_status()
    assets = item.json()["assets"]
    arrs = []
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="YES", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        for asset in ("swir16", "swir22"):
            with rasterio.open(assets[asset]["href"]) as src:
                with WarpedVRT(src, crs=crs, transform=transform, width=shape_hw[1], height=shape_hw[0],
                               resampling=Resampling.cubic) as vrt:
                    arrs.append(vrt.read(1).astype(np.float32) / 10000)
    output = np.stack(arrs)
    with rasterio.open(cache, "w", driver="GTiff", height=shape_hw[0], width=shape_hw[1],
                       count=2, dtype="float32", crs=crs, transform=transform, compress="deflate") as dst:
        dst.write(output)
    return output


def load_scene(year):
    path = ROOT / "data" / "raw" / f"{year}.tif"
    with rasterio.open(path) as src:
        geom = transform_geom("EPSG:4326", src.crs, mapping(box(*AOI)))
        b = shape(geom).bounds
        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        bands = src.read(window=win).astype(np.float32) / 10000
        transform = src.window_transform(win)
        crs = src.crs
        aoi_mask = geometry_mask([geom], (int(win.height), int(win.width)), transform, invert=True)
    with rasterio.open(ROOT / "data" / "raw" / f"{year}_cloudmask.tif") as m:
        cloud = m.read(1, window=win).astype(bool)
    bands[4:6] = bicubic_swir(year, bands.shape[1:], transform, crs)
    valid = aoi_mask & ~cloud & np.all((bands > 0) & (bands <= 1), axis=0)
    return bands, valid, transform, crs, aoi_mask


def load_worldcover(shape_hw, transform, crs):
    cached = OUT / "worldcover_aoi.tif"
    if cached.exists():
        with rasterio.open(cached) as src:
            if src.shape == shape_hw and src.transform == transform:
                return src.read(1)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="YES", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        with rasterio.open(WORLD_COVER_URL) as src:
            with WarpedVRT(src, crs=crs, transform=transform, width=shape_hw[1], height=shape_hw[0], resampling=Resampling.nearest) as vrt:
                data = vrt.read(1)
    with rasterio.open(cached, "w", driver="GTiff", height=shape_hw[0], width=shape_hw[1], count=1,
                       dtype="uint8", crs=crs, transform=transform, compress="deflate") as dst:
        dst.write(data, 1)
    return data


def remap_labels(raw):
    out = np.full(raw.shape, 255, np.uint8)
    for value in (80, 90, 95): out[raw == value] = 0
    for value in (10, 20, 30, 40): out[raw == value] = 1
    out[raw == 60] = 2
    out[raw == 50] = 3
    return out


def indices(b):
    b2, b3, b4, b8, b11, b12 = b
    div = lambda a, c: (a - c) / np.maximum(a + c, 1e-6)
    return np.stack((div(b8, b4), div(b11, b8), div(b3, b8))).astype(np.float32)


def canny(ndbi, valid):
    """Gaussian -> Sobel -> interpolated nonmax suppression -> hysteresis."""
    interior = ndi.binary_erosion(valid, iterations=5)
    clean = np.where(valid, ndbi, 0)
    smooth = ndi.gaussian_filter(clean, 1)
    gx = ndi.sobel(smooth, axis=1) / 8
    gy = ndi.sobel(smooth, axis=0) / 8
    mag = np.hypot(gx, gy)
    yy, xx = np.indices(mag.shape, dtype=np.float32)
    ux = gx / np.maximum(mag, 1e-9)
    uy = gy / np.maximum(mag, 1e-9)
    plus = ndi.map_coordinates(mag, [yy + uy, xx + ux], order=1, mode="nearest")
    minus = ndi.map_coordinates(mag, [yy - uy, xx - ux], order=1, mode="nearest")
    nms = np.where((mag > plus) & (mag >= minus) & interior, mag, 0)
    positive = nms[nms > 0]
    high = float(np.percentile(positive, 90)) if positive.size else 0
    low = 0.4 * high
    weak = nms >= low
    strong = nms >= high
    edges = ndi.binary_propagation(strong, mask=weak)
    components, n = ndi.label(edges)
    sizes = np.bincount(components.ravel())
    edges &= (sizes[components] >= 8) & interior
    return edges, mag.astype(np.float32), {"low": low, "high": high, "percentile_high": 90, "min_component_px": 8}


def edge_maps(ndbi, valid):
    x = np.where(valid, ndbi, 0)
    x = ndi.gaussian_filter(x, 1)
    kernels = {
        "Roberts": (np.array([[1, 0], [0, -1]]), np.array([[0, 1], [-1, 0]])),
        "Prewitt": (np.array([[-1, 0, 1]] * 3), np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]])),
        "Sobel": (np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]), np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])),
    }
    result = {}
    for name, (kx, ky) in kernels.items():
        result[name] = np.hypot(ndi.convolve(x, kx), ndi.convolve(x, ky)).astype(np.float32)
    result["Laplace"] = np.abs(ndi.convolve(x, np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]]))).astype(np.float32)
    result["Canny"], _, params = canny(ndbi, valid)
    return result, params


def glcm_features(nir):
    """Four directional 5x5 GLCM features on 8-level quantized B8.

    Quantization and window are fixed for reproducibility. Four offsets are
    averaged before computing entropy; homogeneity uses 1/(1+d^2).
    """
    q = np.clip((np.nan_to_num(nir) / 0.5 * 8).astype(np.int16), 0, 7).astype(np.uint8)
    h, w = q.shape
    contrast = np.zeros((h, w), np.float32)
    entropy = np.zeros_like(contrast)
    homogeneity = np.zeros_like(contrast)
    dissimilarity = np.zeros_like(contrast)
    offsets = ((0, 1), (1, 0), (1, 1), (-1, 1))
    for i in range(8):
        for j in range(8):
            p = np.zeros((h, w), np.float32)
            for dy, dx in offsets:
                other = np.roll(q, shift=(-dy, -dx), axis=(0, 1))
                p += ndi.uniform_filter(((q == i) & (other == j)).astype(np.float32), size=5) / 4
            d = abs(i-j)
            contrast += p * d*d
            dissimilarity += p * d
            homogeneity += p / (1 + d*d)
            entropy -= np.where(p > 0, p * np.log2(np.maximum(p, 1e-12)), 0)
    return np.stack((contrast, entropy, homogeneity, dissimilarity))


def save_png(array, valid, path, binary=False):
    fig, ax = plt.subplots(figsize=(9, 6), dpi=140)
    z = np.ma.masked_where(~valid, array)
    if binary:
        ax.imshow(z, cmap="gray", vmin=0, vmax=1)
    else:
        high = np.nanpercentile(array[valid], 99)
        ax.imshow(z, cmap="magma", vmin=0, vmax=high)
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(path, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def write_geotiff(array, path, transform, crs, nodata=None):
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[-2], width=array.shape[-1],
                       count=1, dtype=array.dtype, transform=transform, crs=crs,
                       nodata=nodata, compress="deflate") as dst:
        dst.write(array, 1)


def sample_points(labels, features, valid, seed=42):
    rng = np.random.default_rng(seed)
    selected = []
    # Match prior QC: reject nominal Water samples with NDWI <= 0.
    for c in range(4):
        eligible = valid & (labels == c)
        if c == 0: eligible &= features[8] > 0
        ids = np.flatnonzero(eligible)
        if len(ids) < 120: raise RuntimeError(f"Class {c} has only {len(ids)} valid samples")
        selected.append(rng.choice(ids, min(300, len(ids)), replace=False))
    all_ids = np.concatenate(selected)
    y = labels.ravel()[all_ids]
    train = np.zeros(len(all_ids), bool)
    for c in range(4):
        pos = np.where(y == c)[0]
        train[rng.choice(pos, round(len(pos)*0.7), replace=False)] = True
    return all_ids, y, train


def fit_compare(feature_arrays, names, labels, valid):
    full = np.concatenate(feature_arrays, axis=0).astype(np.float32)
    ids, y, train = sample_points(labels, full, valid)
    X = full.reshape(full.shape[0], -1)[:, ids].T
    rows = []
    models = {}
    for title, count in (("Gốc 9", 9), ("Gốc + biên 11", 11), ("Gốc + biên + GLCM 15", 15)):
        model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        model.fit(X[train, :count], y[train])
        pred = model.predict(X[~train, :count])
        cm = confusion_matrix(y[~train], pred, labels=range(4))
        row = {"bo_dac_trung": title, "so_dac_trung": count,
               "OA": float(accuracy_score(y[~train], pred)),
               "Kappa": float(cohen_kappa_score(y[~train], pred)),
               "train_n": int(train.sum()), "test_n": int((~train).sum()),
               "confusion_matrix": cm.tolist(), "features": names[:count]}
        rows.append(row)
        models[title] = model
    return rows, models, full


def classify_all(model, full, count, valid):
    flat = full.reshape(full.shape[0], -1)
    ids = np.flatnonzero(valid)
    result = np.full(valid.size, 255, np.uint8)
    for chunk in np.array_split(ids, max(1, math.ceil(len(ids)/100000))):
        result[chunk] = model.predict(flat[:count, chunk].T).astype(np.uint8)
    return result.reshape(valid.shape)


def spatial_table(classes, valid, transform, crs, year, road_distance=None):
    to_xy = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    cx, cy = to_xy.transform(*CENTER)
    yy, xx = np.indices(classes.shape)
    x = transform.c + (xx + 0.5)*transform.a + (yy + 0.5)*transform.b
    y = transform.f + (xx + 0.5)*transform.d + (yy + 0.5)*transform.e
    dist = np.hypot(x-cx, y-cy)
    # 0=N, clockwise: N, NE, E, SE, S, SW, W, NW.
    sector = (np.floor(((np.degrees(np.arctan2(x-cx, y-cy)) + 22.5) % 360) / 45)).astype(np.uint8)
    names = ["Bắc", "Đông Bắc", "Đông", "Đông Nam", "Nam", "Tây Nam", "Tây", "Tây Bắc"]
    pixel_ha = abs(transform.a*transform.e-transform.b*transform.d)/10000
    rows = []
    for lo, hi in ((0,2000),(2000,4000),(4000,6000)):
        for s in range(8):
            zone = valid & (dist >= lo) & (dist < hi) & (sector == s)
            total = int(zone.sum()); built = int((zone & (classes == 3)).sum())
            rows.append({"year": year, "ring_m": f"{lo}-{hi}", "direction": names[s],
                         "zone_ha": total*pixel_ha, "builtup_ha": built*pixel_ha,
                         "builtup_pct": 100*built/total if total else 0})
    road_rows = []
    if road_distance is not None:
        d = road_distance
        for lo, hi in ((0,100),(100,250),(250,500),(500,1000),(1000,float("inf"))):
            zone = valid & (d >= lo) & (d < hi)
            total = int(zone.sum()); built = int((zone & (classes == 3)).sum())
            road_rows.append({"year": year,"distance_road_m": f"{lo}-{hi}",
                              "zone_ha":total*pixel_ha,"builtup_ha":built*pixel_ha,
                              "builtup_pct":100*built/total if total else 0})
    return rows, road_rows


def load_roads(shape_hw, transform, crs):
    path = OUT / "roads.geojson"
    if not path.exists(): return None, []
    data = json.loads(path.read_text())
    transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    records = []
    names = set()
    for f in data.get("features", []):
        geom = shp_transform(transformer, shape(f["geometry"]))
        if geom.is_empty: continue
        props = f.get("properties", {})
        records.append((geom, 1))
        names.add(props.get("name") or props.get("ref") or "(chưa đặt tên)")
    if not records: return None, []
    # Extend the raster 1.5 km beyond AOI so roads just outside its edge
    # contribute to nearest-road distance inside the study area.
    pad = math.ceil(1500/min(abs(transform.e),abs(transform.a)))
    padded_shape = (shape_hw[0]+2*pad,shape_hw[1]+2*pad)
    padded_transform = transform*Affine.translation(-pad,-pad)
    mask = rasterize(records, out_shape=padded_shape, transform=padded_transform,
                     fill=0, dtype="uint8").astype(bool)
    distance = ndi.distance_transform_edt(~mask,sampling=(abs(transform.e),abs(transform.a)))
    return distance[pad:pad+shape_hw[0],pad:pad+shape_hw[1]], sorted(names)


def write_csv(path, rows):
    if not rows: return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    all_results = {"source": "AWS/STAC single Sentinel-2 scenes; B11/B12 re-read at native 20m and cubic-resampled to 10m. These are not GEE median composites.", "worldcover": WORLD_COVER_URL, "years": {}}
    bands22, valid22, trans, crs, aoi = load_scene(2022)
    wc = remap_labels(load_worldcover(valid22.shape, trans, crs))
    distance_raster, road_names = load_roads(valid22.shape, trans, crs)
    all_results["roads"] = road_names
    all_results["label_counts"] = {CLASS_NAMES[c]: int(((wc == c) & valid22).sum()) for c in range(4)}
    spatial, road_rows_all, density_rows = [], [], []
    class_maps, valid_maps = {}, {}
    shared_model = None
    shared_title = None
    shared_count = None
    for year in (2022, 2024):
        bands, valid, transform, year_crs, aoi_mask = (bands22, valid22, trans, crs, aoi) if year == 2022 else load_scene(year)
        if valid.shape != valid22.shape or transform != trans: raise ValueError("Years have nonmatching pixel grids")
        idx = indices(bands)
        base = np.concatenate((bands, idx), axis=0)
        ndbi = idx[1]
        edges, canny_params = edge_maps(ndbi, valid)
        edge_valid = ndi.binary_erosion(valid, iterations=5)
        for name, array in edges.items():
            save_png(array, edge_valid, OUT / f"{year}_{name.lower()}.png", binary=(name=="Canny"))
        density = ndi.uniform_filter(edges["Canny"].astype(np.float32), size=7)
        grad = edges["Sobel"] / 8
        textures = glcm_features(bands[3])
        names = BANDS + ["NDVI","NDBI","NDWI","edge_density","sobel_gradient", "glcm_contrast","glcm_entropy","glcm_homogeneity","glcm_dissimilarity"]
        valid_ml = valid & (wc != 255) & np.all(np.isfinite(base), axis=0)
        rows, models, full = fit_compare([base,density[None],grad[None],textures], names, wc, valid_ml)
        best = max(rows, key=lambda r:(r["OA"],r["Kappa"]))
        if year == 2022:
            shared_model = models[best["bo_dac_trung"]]
            shared_title = best["bo_dac_trung"]
            shared_count = best["so_dac_trung"]
        cls = classify_all(shared_model, full, shared_count, valid)
        class_maps[year] = cls
        valid_maps[year] = valid
        write_geotiff(cls, OUT / f"classified_{year}.tif", transform, crs, nodata=255)
        write_geotiff(ndbi.astype(np.float32), OUT / f"ndbi_{year}.tif", transform, crs, nodata=None)
        save_png(density, valid, OUT / f"{year}_edge_density.png")
        for c in range(4):
            mask = valid & (wc == c)
            density_rows.append({"year":year,"class":CLASS_NAMES[c],"reference":"ESA WorldCover 2021",
                                 "n_pixels":int(mask.sum()),"mean_edge_density":float(density[mask].mean()) if mask.any() else None,
                                 "mean_sobel_gradient":float(grad[mask].mean()) if mask.any() else None})
        all_results["years"][year] = {"valid_pixels":int(valid.sum()),"canny_thresholds":canny_params,
                                        "canny_edge_pct":float(100*edges["Canny"][valid].mean()),
                                        "models":rows,"year_specific_winner":best["bo_dac_trung"],
                                        "spatial_model":shared_title,
                                        "builtup_ha_all_valid":float((cls==3).sum()*abs(trans.a*trans.e)/10000)}
        print(year, "spatial model", shared_title,"built-up ha on own valid area",all_results["years"][year]["builtup_ha_all_valid"],flush=True)
    common_valid = valid_maps[2022] & valid_maps[2024]
    all_results["common_valid_pixels"] = int(common_valid.sum())
    all_results["pixel_area_ha"] = abs(trans.a*trans.e)/10000
    all_results["common_valid_area_ha"] = float(common_valid.sum()*all_results["pixel_area_ha"])
    for year in (2022,2024):
        cls = class_maps[year]
        s, r = spatial_table(cls, common_valid, trans, crs, year, distance_raster)
        spatial += s; road_rows_all += r
        all_results["years"][year]["builtup_ha"] = float(((cls==3)&common_valid).sum()*all_results["pixel_area_ha"])
    write_csv(OUT / "spatial_ring_direction.csv", spatial)
    write_csv(OUT / "distance_to_roads.csv", road_rows_all)
    write_csv(OUT / "edge_density_by_class.csv", density_rows)
    all_results["edge_density_by_class"] = density_rows
    (OUT / "analysis.json").write_text(json.dumps(all_results,ensure_ascii=False,indent=2),encoding="utf-8")
    print('Wrote',OUT,flush=True)


if __name__ == "__main__": main()
