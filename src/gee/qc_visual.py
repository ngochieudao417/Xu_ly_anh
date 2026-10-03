"""
Task 3.4: ra mau bang mat. Export anh chip RGB that (nen composite Sentinel-2
cua nam tham chieu) quanh tung diem mau, ghep thanh contact sheet theo tung
lop de kiem tra WorldCover co gan nham khong.
"""

from __future__ import annotations

import io
import random
import urllib.request
from pathlib import Path

import ee
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.gee import config as gcfg
from src.gee import composite as gcomp

VIS_MIN, VIS_MAX, VIS_GAMMA = 0.0, 0.30, 1.3
CHIP_BUFFER_M = 150  # -> vung 300x300 m quanh diem
CHIP_PX = 180


def fetch_chip_png(image: "ee.Image", lon: float, lat: float, retries: int = 3) -> Image.Image:
    point = ee.Geometry.Point([lon, lat])
    region = point.buffer(CHIP_BUFFER_M).bounds()
    url = image.getThumbURL({
        "region": region, "dimensions": CHIP_PX,
        "bands": ["B4", "B3", "B2"], "min": VIS_MIN, "max": VIS_MAX, "gamma": VIS_GAMMA,
        "format": "png",
    })
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = resp.read()
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:  # loi mang tam thoi -- thu lai
            last_err = e
    raise last_err


def annotate_chip(img: Image.Image, label: str) -> Image.Image:
    img = img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    # dau cham giua chip = vi tri diem mau
    r = 4
    draw.ellipse((w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r), outline=(255, 0, 0), width=2)
    draw.rectangle((0, 0, w, 16), fill=(0, 0, 0))
    draw.text((3, 2), label, fill=(255, 255, 0))
    return img


def build_contact_sheet(chips: list[tuple[Image.Image, str]], ncols: int, title: str, out_path: Path) -> Path:
    n = len(chips)
    nrows = -(-n // ncols)
    cell = CHIP_PX
    pad = 4
    header_h = 30
    sheet = Image.new("RGB", (ncols * (cell + pad) + pad, nrows * (cell + pad) + pad + header_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((5, 5), title, fill=(0, 0, 0))
    for i, (img, label) in enumerate(chips):
        r, c = divmod(i, ncols)
        x = pad + c * (cell + pad)
        y = header_h + pad + r * (cell + pad)
        sheet.paste(annotate_chip(img, label), (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return out_path


def sample_points_for_qc(reference_year: int = gcfg.REFERENCE_YEAR_FOR_SAMPLING, n_per_class: int = 20, seed: int = gcfg.SAMPLE_SEED):
    """Lay danh sach (lon, lat, class) tu bo mau da stratified-sample, chon ngau nhien n_per_class/lop."""
    from src.gee import sampling as gsamp

    samples = gsamp.build_labeled_samples(reference_year)
    feats = samples.getInfo()["features"]
    by_class: dict[int, list] = {c: [] for c in gcfg.CLASS_MAP}
    for f in feats:
        cls = int(f["properties"][gcfg.CLASS_COL])
        lon, lat = f["geometry"]["coordinates"]
        by_class[cls].append((lon, lat))

    rng = random.Random(seed)
    picked = {}
    for cls, pts in by_class.items():
        rng.shuffle(pts)
        picked[cls] = pts[:n_per_class]
    return picked


def run_visual_qc(reference_year: int = gcfg.REFERENCE_YEAR_FOR_SAMPLING, n_per_class: int = 20, only_classes=None) -> dict[int, Path]:
    gcfg.init_ee()
    composite = gcomp.build_composite(reference_year)
    picked = sample_points_for_qc(reference_year, n_per_class)
    if only_classes is not None:
        picked = {c: pts for c, pts in picked.items() if c in only_classes}

    out_paths = {}
    for cls, pts in picked.items():
        cls_name = gcfg.CLASS_MAP[cls]
        chips = []
        for i, (lon, lat) in enumerate(pts):
            img = fetch_chip_png(composite, lon, lat)
            chips.append((img, f"#{i} {lon:.4f},{lat:.4f}"))
        out_path = gcfg.GEE_FIGURES_DIR / f"qc_visual_{cls_name.lower().replace(' ', '_')}.png"
        build_contact_sheet(chips, ncols=5, title=f"QC truc quan - lop {cls_name} (nam tham chieu {reference_year})", out_path=out_path)
        out_paths[cls] = out_path
        print(f"  {cls_name}: {len(chips)} chip -> {out_path}")
    return out_paths


if __name__ == "__main__":
    run_visual_qc()
