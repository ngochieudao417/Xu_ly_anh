"""
Task 3.8: ap model thang (phuong an A, 9 band) len ca 5 moc thoi gian ->
ban do phan loai + dien tich lop Built-up (va cac lop khac) tung nam.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import ee
from PIL import Image

from src.gee import config as gcfg
from src.gee import composite as gcomp

CLASS_PALETTE = {0: "1a73e8", 1: "34a853", 2: "c9a66b", 3: "d93025"}  # Water,Veg,Bare,Built-up
PIXEL_AREA_M2 = 10 * 10


def classify_year(classifier: "ee.Classifier", year: int, feature_names: list[str]) -> "ee.Image":
    composite = gcomp.build_composite(year)
    return composite.select(feature_names).classify(classifier).rename("class").set("year", year)


def class_area_table(classifier: "ee.Classifier", years: list[int], feature_names: list[str]) -> dict[int, dict]:
    """Dem so pixel tung lop trong AOI cho tung nam, quy doi ra dien tich (ha)."""
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    out = {}
    for year in years:
        classified = classify_year(classifier, year, feature_names)
        hist = classified.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(), geometry=aoi, scale=10, maxPixels=1e9, bestEffort=True,
        ).getInfo()
        raw = hist.get("class", {})
        counts = {int(float(k)): int(v) for k, v in raw.items()}
        total = sum(counts.values())
        out[year] = {
            "pixel_counts": counts,
            "total_pixels": total,
            "area_ha": {c: counts.get(c, 0) * PIXEL_AREA_M2 / 10_000 for c in gcfg.CLASS_MAP},
            "area_pct": {c: 100 * counts.get(c, 0) / total if total else 0 for c in gcfg.CLASS_MAP},
        }
        print(f"  {year}: total={total:,} px  " + ", ".join(
            f"{gcfg.CLASS_MAP[c]}={out[year]['area_ha'][c]:.1f}ha ({out[year]['area_pct'][c]:.1f}%)"
            for c in sorted(gcfg.CLASS_MAP)
        ))
    return out


def export_classified_map_png(classifier: "ee.Classifier", year: int, feature_names: list[str], out_path: Path, dimensions=900) -> Path:
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    classified = classify_year(classifier, year, feature_names)
    vis = classified.visualize(min=0, max=3, palette=[CLASS_PALETTE[c] for c in sorted(CLASS_PALETTE)])
    url = vis.getThumbURL({"region": aoi, "dimensions": dimensions, "format": "png"})
    with urllib.request.urlopen(url, timeout=90) as resp:
        data = resp.read()
    img = Image.open(io.BytesIO(data)).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path
