#!/usr/bin/env python3
"""Task W4 muc cuoi: dung bien doi Hough de tu tim duong bang san bay Long Thanh.

Dau vao : outputs/w4/ndbi_<year>.tif, classified_<year>.tif (mat na hop le),
          airport_boundary.geojson (ranh gioi san bay OSM).
Dau ra  : outputs/w4/hough_<year>.png, hough_lines.csv, hough.json.

Y tuong: duong bang la vat the nhan tao dai va thang nhat trong anh. Neu Hough
tu tim ra duoc no ma khong can bat ky nhan nao, do la bang chung doc lap cho
viec be mat da doi sang cong trinh nhan tao. So sanh 2022 va 2024 cho thay
duong bang xuat hien vao luc nao.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from scipy import ndimage as ndi
from shapely.geometry import shape
from skimage.transform import hough_line, hough_line_peaks, probabilistic_hough_line

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "outputs" / "w4"

YEARS = (2022, 2024)

# Duong bang Long Thanh giai doan 1 dai 4 000 m, rong 45 m.
# O do phan giai 10 m thi tuong duong 400 diem anh chieu dai.
RUNWAY_LEN_M = 4000
MIN_SEG_M = 1500          # doan thang toi thieu duoc giu lai
# Bien Canny trong san bay bi dut quang, nen phai cho phep noi. Da thu
# gap = 12, 20, 30, 50, 80 px: tu 30 px tro len Hough bat dau noi nham cac
# manh roi rac khong lien quan thanh duong dai 7-10 km, vo ly voi mot o
# chi rong 11 km. Chon 20 px (200 m) la muc con cho ket qua hop ly ve vat ly.
LINE_GAP_PX = 20
HOUGH_SEED = 42
ANGLE_TOL_DEG = 7.0       # dung gom cac doan cung huong thanh mot tuyen


def canny(ndbi: np.ndarray, valid: np.ndarray):
    """Ban sao dung bang thuat toan Canny da dung o run_w4_local.py."""
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
    high = float(np.percentile(positive, 90)) if positive.size else 0.0
    low = 0.4 * high
    edges = ndi.binary_propagation(nms >= high, mask=nms >= low)
    components, _ = ndi.label(edges)
    sizes = np.bincount(components.ravel())
    edges &= (sizes[components] >= 8) & interior
    return edges


def load_year(year: int):
    with rasterio.open(OUT / f"ndbi_{year}.tif") as src:
        ndbi = src.read(1)
        transform, crs = src.transform, src.crs
    with rasterio.open(OUT / f"classified_{year}.tif") as src:
        valid = src.read(1) != src.nodata
    return ndbi, valid, transform, crs


def airport_mask(shape_hw, transform, crs):
    data = json.loads((OUT / "airport_boundary.geojson").read_text(encoding="utf-8"))
    geoms = [transform_geom("EPSG:4326", crs.to_string(), f["geometry"]) for f in data["features"]]
    inside = ~geometry_mask(geoms, out_shape=shape_hw, transform=transform, invert=False)
    return inside, [shape(g) for g in geoms]


def bearing_deg(x1, y1, x2, y2) -> float:
    """Phuong vi 0-180 do so voi huong bac. Hang anh tang xuong phia nam."""
    dx = x2 - x1
    dy = -(y2 - y1)
    ang = math.degrees(math.atan2(dx, dy)) % 180.0
    return ang


def group_segments(segments, res_m: float):
    """Gom cac doan gan cung phuong vi thanh nhom, tra ve thong ke tung nhom."""
    items = []
    for (x1, y1), (x2, y2) in segments:
        length_m = math.hypot(x2 - x1, y2 - y1) * res_m
        items.append({"p1": (x1, y1), "p2": (x2, y2),
                      "bearing": bearing_deg(x1, y1, x2, y2),
                      "length_m": length_m})
    items.sort(key=lambda s: -s["length_m"])

    groups = []
    for seg in items:
        placed = False
        for g in groups:
            diff = abs(seg["bearing"] - g["bearing"])
            diff = min(diff, 180 - diff)
            if diff <= ANGLE_TOL_DEG:
                g["segments"].append(seg)
                total = sum(s["length_m"] for s in g["segments"])
                g["bearing"] = sum(s["bearing"] * s["length_m"] for s in g["segments"]) / total
                g["total_len_m"] = total
                g["max_len_m"] = max(s["length_m"] for s in g["segments"])
                placed = True
                break
        if not placed:
            groups.append({"bearing": seg["bearing"], "segments": [seg],
                           "total_len_m": seg["length_m"], "max_len_m": seg["length_m"]})
    groups.sort(key=lambda g: -g["total_len_m"])
    return groups


def builtup_axis(year: int, inside: np.ndarray):
    """Kiem chung doc lap: truc chinh cua vung built-up lien thong lon nhat.

    Khong dung Hough, khong dung bien. Neu duong bang that su ton tai thi vung
    nay phai vua lon vua thon dai, va truc cua no phai trung huong voi tuyen
    ma Hough tim duoc.
    """
    with rasterio.open(OUT / f"classified_{year}.tif") as src:
        cls = src.read(1)
    blob = (cls == 3) & inside
    lab, n = ndi.label(blob)
    if n == 0:
        return None
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    k = int(sizes.argmax())
    ys, xs = np.where(lab == k)
    pts = np.column_stack([xs - xs.mean(), -(ys - ys.mean())])
    eigval, eigvec = np.linalg.eigh(np.cov(pts.T))
    major = eigvec[:, int(np.argmax(eigval))]
    return {
        "px": int(sizes[k]),
        "ha": round(float(sizes[k]) * 0.01, 1),
        "bearing_deg": round(math.degrees(math.atan2(major[0], major[1])) % 180.0, 2),
        "elongation": round(float(math.sqrt(max(eigval) / max(min(eigval), 1e-9))), 2),
        "n_components": int(n),
    }


def builtup_hit_rate(seg, cls: np.ndarray) -> float:
    """Ty le diem tren tuyen co lop built-up trong cua so 3x3 quanh no."""
    (x1, y1), (x2, y2) = seg["p1"], seg["p2"]
    n = max(int(seg["length_m"] / 10), 2)
    xs = np.linspace(x1, x2, n).astype(int)
    ys = np.linspace(y1, y2, n).astype(int)
    hits = [3 in cls[max(0, Y - 1):Y + 2, max(0, X - 1):X + 2] for X, Y in zip(xs, ys)]
    return round(100.0 * float(np.mean(hits)), 1)


def polygon_principal_axis(geom) -> float:
    """Phuong vi truc dai cua da giac san bay, dung de doi chieu doc lap."""
    rect = geom.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    best, best_len = None, -1.0
    for i in range(len(xs) - 1):
        dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
        length = math.hypot(dx, dy)
        if length > best_len:
            best_len, best = length, math.degrees(math.atan2(dx, dy)) % 180.0
    return best, best_len


def plot_year(year, ndbi, edges, segments, runway_group, inside, out_path, platform=None):
    fig, ax = plt.subplots(figsize=(10, 7.4))
    base = np.where(np.isfinite(ndbi), ndbi, 0)
    ax.imshow(base, cmap="gray", vmin=-0.4, vmax=0.4)
    ax.imshow(np.ma.masked_where(~edges, edges), cmap="autumn", alpha=0.45)

    if platform is not None and platform.any():
        ax.contour(platform, levels=[0.5], colors="#00FF7F", linewidths=1.3)
        ax.plot([], [], color="#00FF7F", lw=1.3,
                label="Vùng built-up liền thông lớn nhất")

    ys, xs = np.where(inside)
    if ys.size:
        ax.add_patch(plt.Rectangle((xs.min(), ys.min()), xs.max() - xs.min(), ys.max() - ys.min(),
                                   fill=False, edgecolor="#1E90FF", lw=1.4, ls="--",
                                   label="Khung ranh giới sân bay (OSM)"))
    for (x1, y1), (x2, y2) in segments:
        ax.plot([x1, x2], [y1, y2], color="#00BFFF", lw=1.0, alpha=0.65)
    if runway_group:
        for s in runway_group["segments"]:
            (x1, y1), (x2, y2) = s["p1"], s["p2"]
            ax.plot([x1, x2], [y1, y2], color="#D7301F", lw=2.6)
        ax.plot([], [], color="#D7301F", lw=2.6,
                label=f"Tuyến trội: {runway_group['bearing']:.1f}°, "
                      f"tổng {runway_group['total_len_m']/1000:.2f} km")
    ax.plot([], [], color="#00BFFF", lw=1.0, label=f"Đoạn Hough khác ({len(segments)} đoạn)")
    ax.set_title(f"Hough trên biên Canny của NDBI — năm {year}")
    ax.set_xticks([]); ax.set_yticks([])
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    results = {"method": {
        "edge": "Canny (cùng tham số với run_w4_local.py)",
        "hough": "probabilistic_hough_line của scikit-image",
        "min_segment_m": MIN_SEG_M, "line_gap_px": LINE_GAP_PX,
        "angle_tolerance_deg": ANGLE_TOL_DEG, "seed": HOUGH_SEED,
        "scope": "chỉ xét trong ranh giới sân bay OSM",
    }, "years": {}}
    csv_rows = []

    for year in YEARS:
        ndbi, valid, transform, crs = load_year(year)
        res_m = abs(transform.a)
        inside, geoms = airport_mask(ndbi.shape, transform, crs)

        edges = canny(ndbi, valid) & inside
        min_len_px = int(round(MIN_SEG_M / res_m))

        segments = probabilistic_hough_line(
            edges, threshold=10, line_length=min_len_px, line_gap=LINE_GAP_PX,
            rng=HOUGH_SEED)
        groups = group_segments(segments, res_m)
        top = groups[0] if groups else None

        # Hough co dien: lay phuong vi troi tren toan anh bien
        h, theta, d = hough_line(edges)
        peaks = hough_line_peaks(h, theta, d, num_peaks=5)
        peak_bearings = [float((math.degrees(a) + 90) % 180) for a in peaks[1]]

        axis_bearing, axis_len = polygon_principal_axis(geoms[0])
        bu = builtup_axis(year, inside)
        with rasterio.open(OUT / f"classified_{year}.tif") as src:
            cls_arr = src.read(1)
        for g in groups:
            for sgm in g["segments"]:
                sgm["builtup_pct"] = builtup_hit_rate(sgm, cls_arr)
            g["builtup_pct"] = round(
                sum(x["builtup_pct"] * x["length_m"] for x in g["segments"])
                / max(g["total_len_m"], 1e-9), 1)

        diff = None
        if top and bu:
            diff = abs(top["bearing"] - bu["bearing_deg"])
            diff = min(diff, 180 - diff)

        platform = None
        if bu:
            lab, _ = ndi.label((cls_arr == 3) & inside)
            sizes = np.bincount(lab.ravel()); sizes[0] = 0
            platform = lab == int(sizes.argmax())
        plot_year(year, ndbi, edges, segments, top, inside,
                  OUT / f"hough_{year}.png", platform)

        results["years"][str(year)] = {
            "edge_px_in_airport": int(edges.sum()),
            "n_segments": len(segments),
            "n_groups": len(groups),
            "min_segment_m": MIN_SEG_M,
            "dominant_bearing_deg": round(top["bearing"], 2) if top else None,
            "dominant_total_len_m": round(top["total_len_m"], 1) if top else None,
            "dominant_max_len_m": round(top["max_len_m"], 1) if top else None,
            "dominant_n_segments": len(top["segments"]) if top else 0,
            "classic_hough_peak_bearings": [round(b, 2) for b in peak_bearings],
            "dominant_builtup_pct": top["builtup_pct"] if top else None,
            "airport_axis_bearing_deg": round(axis_bearing, 2),
            "airport_axis_len_m": round(axis_len, 1),
            "builtup_largest_component": bu,
            "bearing_diff_vs_builtup_axis_deg": round(diff, 2) if diff is not None else None,
            "longest_single_segment_m": round(max((s["length_m"] for g in groups for s in g["segments"]), default=0.0), 1),
        }

        for gi, g in enumerate(groups, 1):
            for s in g["segments"]:
                csv_rows.append({
                    "year": year, "group": gi,
                    "bearing_deg": round(s["bearing"], 2),
                    "length_m": round(s["length_m"], 1),
                    "builtup_pct": s["builtup_pct"],
                    "row1": s["p1"][1], "col1": s["p1"][0],
                    "row2": s["p2"][1], "col2": s["p2"][0],
                    "group_total_len_m": round(g["total_len_m"], 1),
                })

        if top:
            print(f"{year}: {len(segments)} đoạn ≥{MIN_SEG_M} m | tuyến trội "
                  f"{top['bearing']:.1f}°, dài {top['max_len_m']:.0f} m, "
                  f"trùng built-up {top['builtup_pct']:.1f}%", flush=True)
        else:
            print(f"{year}: không có đoạn nào đạt ngưỡng", flush=True)
        if bu:
            print(f"      kiểm chứng: vùng built-up lớn nhất {bu['ha']} ha, trục "
                  f"{bu['bearing_deg']:.1f}°, thon dài {bu['elongation']:.2f}"
                  + (f", lệch so với Hough {diff:.1f}°" if diff is not None else ""),
                  flush=True)

    with (OUT / "hough_lines.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()) if csv_rows else
                           ["year", "group", "bearing_deg", "length_m"])
        w.writeheader()
        w.writerows(csv_rows)

    (OUT / "hough.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    print("Wrote", OUT / "hough.json", flush=True)


if __name__ == "__main__":
    main()
