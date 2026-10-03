#!/usr/bin/env python3
"""W4 muc 1: ve cac tuyen duong lon quanh san bay TREN GEE va kiem chung tren do.

Truoc day nhom chi xuat scripts/w4_roads_gee.js de dan tay vao Code Editor, kem
ghi chu la tai khoan dich vu thieu quyen nen chua chay duoc. Ghi chu do nay da
khong con dung: tai khoan dich vu hien truy cap GEE binh thuong.

Script nay dua mang duong OSM va ranh gioi san bay len GEE, roi de chinh GEE
tinh va ve, thay vi tin vao ket qua tinh cuc bo:
  - tong chieu dai duong, tinh bang ee.Feature.length() tren may chu
  - chieu dai nam trong hang rao san bay, phai bang 0
  - anh ban do nen Sentinel-2 co phu lop duong va ranh san bay

Dau ra: outputs/w4/gee_roads_map.png, outputs/w4/gee_roads.json
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ee
from PIL import Image

from src.gee import config as gcfg
from src.gee import composite as gcomp

OUT = ROOT / "outputs" / "w4"
# Ranh AOI cua W4 (rong hon AOI chuan mot chut vi mang duong trai ra ngoai).
AOI_W4 = [106.98849946776265, 10.736755380981812, 107.09698945799703, 10.814327243656404]
BASE_YEAR = 2024


def load_fc(path: Path, props=("name", "highway")) -> "ee.FeatureCollection":
    data = json.loads(path.read_text(encoding="utf-8"))
    feats = []
    for f in data["features"]:
        attrs = {k: (f["properties"].get(k) or "") for k in props}
        feats.append(ee.Feature(ee.Geometry(f["geometry"]), attrs))
    return ee.FeatureCollection(feats)


def fetch(url: str, retries: int = 3) -> bytes:
    last = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception as e:
            last = e
    raise last


def main():
    gcfg.init_ee()
    aoi = ee.Geometry.Rectangle(AOI_W4)

    roads = load_fc(OUT / "roads.geojson")
    airport = load_fc(OUT / "airport_boundary.geojson", props=("name",))
    airport_geom = airport.geometry()

    # --- GEE tu tinh, khong lay lai so da tinh cuc bo -------------------
    total_m = roads.geometry().length(maxError=1)
    inside_m = roads.geometry().intersection(airport_geom, maxError=1).length(maxError=1)
    n_seg = roads.size()
    names = roads.aggregate_array("name").distinct().sort()

    stats = ee.Dictionary({
        "n_segments": n_seg,
        "total_length_m": total_m,
        "length_inside_airport_m": inside_m,
        "airport_area_ha": airport_geom.area(maxError=1).divide(1e4),
        "names": names,
    }).getInfo()

    print("=== GEE tu tinh ===")
    print(f"  so doan duong          : {stats['n_segments']}")
    print(f"  tong chieu dai         : {stats['total_length_m']:,.0f} m")
    print(f"  nam trong hang rao     : {stats['length_inside_airport_m']:,.2f} m "
          f"-> {'DAT' if stats['length_inside_airport_m'] < 1 else 'CHUA DAT'}")
    print(f"  dien tich san bay      : {stats['airport_area_ha']:,.1f} ha")
    print(f"  so ten/ma tuyen        : {len([n for n in stats['names'] if n])}")
    for n in stats["names"]:
        if n:
            print(f"     - {n}")

    # --- Ve ban do tren GEE ---------------------------------------------
    base = gcomp.build_composite(BASE_YEAR).select(["B4", "B3", "B2"]).clip(aoi)
    vis = base.visualize(min=0.0, max=0.30, gamma=1.3)

    road_layer = ee.Image().byte().paint(roads, 1, 2).visualize(palette=["#FFD400"])
    fence_layer = ee.Image().byte().paint(airport, 1, 2).visualize(palette=["#FF2D2D"])

    blended = vis.blend(fence_layer).blend(road_layer)
    url = blended.getThumbURL({"region": aoi, "dimensions": 1500, "format": "png"})
    img = Image.open(io.BytesIO(fetch(url))).convert("RGB")
    out_png = OUT / "gee_roads_map.png"
    img.save(out_png)
    print(f"\n  ban do GEE -> {out_png} ({img.width}x{img.height})")

    stats["base_year"] = BASE_YEAR
    stats["note"] = ("Moi con so trong tep nay do chinh GEE tinh tren may chu "
                     "(ee.Geometry.length / intersection), khong phai tinh cuc bo.")
    (OUT / "gee_roads.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"  so lieu    -> {OUT / 'gee_roads.json'}")


if __name__ == "__main__":
    main()
