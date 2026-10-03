#!/usr/bin/env python3
"""Clip OSM major roads outside the Long Thanh aerodrome polygon.

Inputs come from the Geofabrik Vietnam OSM extract and are saved in
outputs/w4/osm_major_raw.geojson and outputs/w4/aerodrome.geojson.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box, mapping

from run_w4_local import AOI, OUT, load_scene


def main():
    roads = gpd.read_file(OUT / "osm_major_raw.geojson").to_crs(32648)
    airport = gpd.read_file(OUT / "aerodrome.geojson").to_crs(32648)
    fence = airport.geometry.union_all()
    aoi = gpd.GeoSeries([box(*AOI)],crs=4326).to_crs(32648).iloc[0]
    vicinity = aoi.buffer(1500)
    features = []
    removed_m = 0.
    for _, row in roads.iterrows():
        g = row.geometry.intersection(vicinity)
        if g.is_empty: continue
        removed_m += g.intersection(fence).length
        outside = g.difference(fence)
        if outside.is_empty: continue
        if outside.geom_type == "GeometryCollection":
            from shapely.ops import unary_union
            outside = unary_union([part for part in outside.geoms if part.geom_type in ("LineString","MultiLineString")])
        if outside.is_empty or outside.length < 5: continue
        features.append({"type":"Feature", "properties":{"name":row.get("name") or "(chưa đặt tên)",
                         "highway":row.get("highway"),"osm_id":str(row.get("osm_id"))},
                         "geometry":mapping(gpd.GeoSeries([outside],crs=32648).to_crs(4326).iloc[0])})
    road_json = {"type":"FeatureCollection","features":features}
    (OUT / "roads.geojson").write_text(json.dumps(road_json,ensure_ascii=False),encoding="utf-8")
    airport_wgs = airport.to_crs(4326)
    airport_wgs.to_file(OUT / "airport_boundary.geojson",driver="GeoJSON")
    names = sorted({f["properties"]["name"] for f in features})
    (OUT / "road_names.txt").write_text("\n".join(names)+"\n",encoding="utf-8")

    # Check in metric CRS: no drawn line has positive length inside airport.
    filtered = gpd.read_file(OUT / "roads.geojson").to_crs(32648)
    inside_m = sum(geom.intersection(fence).length for geom in filtered.geometry)
    if inside_m > 0.1: raise AssertionError(f"Road length inside airport: {inside_m} m")

    bands, valid, transform, crs, _ = load_scene(2024)
    rgb = np.stack([bands[2],bands[1],bands[0]],axis=-1)
    for i in range(3):
        lo,hi=np.percentile(rgb[:,:,i][valid],[2,98])
        rgb[:,:,i]=np.clip((rgb[:,:,i]-lo)/(hi-lo),0,1)
    extent=(transform.c,transform.c+rgb.shape[1]*transform.a,
            transform.f+rgb.shape[0]*transform.e,transform.f)
    fig,ax=plt.subplots(figsize=(9,8),dpi=160)
    ax.imshow(rgb,extent=extent)
    airport.boundary.plot(ax=ax,color="#f9e64a",linewidth=1.4)
    filtered.plot(ax=ax,color="#d7301f",linewidth=1.4)
    ax.set_xlim(aoi.bounds[0],aoi.bounds[2]);ax.set_ylim(aoi.bounds[1],aoi.bounds[3])
    ax.set_xlabel("UTM 48N - m");ax.set_ylabel("UTM 48N - m")
    ax.set_title("Đường lớn quanh sân bay Long Thành (OpenStreetMap)")
    ax.plot([],[],color="#f9e64a",label="Ranh sân bay OSM")
    ax.plot([],[],color="#d7301f",label="Đường lớn ngoài sân bay")
    ax.legend(loc="lower left",fontsize=8)
    fig.tight_layout();fig.savefig(OUT / "roads_map.png");plt.close(fig)

    # Portable Code Editor overlay. All coordinates are from the clipped OSM
    # features, so even when pasted into GEE no segment enters the fence.
    js = ["// Dán vào Google Earth Engine Code Editor để vẽ đường lớn quanh sân bay.",
          "// Nguồn: OpenStreetMap/Geofabrik Vietnam; các đoạn trong polygon sân bay đã bị cắt.",
          f"var AOI = ee.Geometry.Rectangle({json.dumps(AOI)});",
          f"var sanBay = ee.Geometry({json.dumps(mapping(airport_wgs.geometry.union_all()),ensure_ascii=False)});",
          "var tuyenDuong = ee.FeatureCollection(["]
    for n,f in enumerate(features):
        geo = f["geometry"]; typ=geo["type"]
        if typ not in ("LineString","MultiLineString"): continue
        constructor = "LineString" if typ == "LineString" else "MultiLineString"
        suffix = "," if n < len(features)-1 else ""
        js.append(f"  ee.Feature(ee.Geometry.{constructor}({json.dumps(geo['coordinates'])}), "
                  f"{{name: {json.dumps(f['properties']['name'],ensure_ascii=False)}, "
                  f"highway: {json.dumps(f['properties']['highway'])}}}){suffix}")
    js += ["]);","Map.centerObject(AOI, 12);",
           "Map.addLayer(AOI, {color: 'white'}, 'AOI');",
           "Map.addLayer(sanBay, {color: 'yellow'}, 'Ranh sân bay OSM');",
           "Map.addLayer(tuyenDuong.style({color: 'd7301f', width: 2}), {}, 'Đường lớn ngoài sân bay');",
           "print('Tên tuyến đường', tuyenDuong.aggregate_array('name').distinct().sort());"]
    js_text = "\n".join(js)+"\n"
    (OUT / "w4_roads_gee.js").write_text(js_text,encoding="utf-8")
    (Path(__file__).resolve().parent / "w4_roads_gee.js").write_text(js_text,encoding="utf-8")
    print("segments",len(features),"names",len(names),"removed_m",round(removed_m,1),"inside_m",inside_m)


if __name__ == "__main__": main()
