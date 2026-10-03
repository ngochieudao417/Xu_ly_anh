#!/usr/bin/env python3
"""Fetch major roads and airport polygon from Geofabrik's Vietnam OSM PBF.

Run this once before prepare_w4_roads.py. The PBF is read remotely and only
features intersecting the small study bbox are written locally.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pyogrio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "w4"
URL = "https://download.geofabrik.de/asia/vietnam-latest.osm.pbf"
REMOTE = "/vsicurl/" + URL
BBOX = (106.97, 10.72, 107.12, 10.83)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    roads = pyogrio.read_dataframe(REMOTE, layer="lines", bbox=BBOX)
    roads = roads[roads.highway.isin(("motorway","trunk","primary","secondary"))]
    roads.to_file(OUT / "osm_major_raw.geojson", driver="GeoJSON")
    airport = pyogrio.read_dataframe(REMOTE, layer="multipolygons", bbox=BBOX,
                                     where="aeroway = 'aerodrome'")
    airport = airport[airport.name.fillna("").str.contains("Long Thành|Long Thanh",case=False,regex=True)]
    if len(airport) != 1:
        raise RuntimeError(f"Expected one Long Thanh airport polygon, found {len(airport)}")
    airport.to_file(OUT / "aerodrome.geojson", driver="GeoJSON")
    provenance = {"source":URL,"retrieved_utc":datetime.now(timezone.utc).isoformat(),
                  "road_segments":len(roads),"airport_name":airport.name.iloc[0],
                  "bbox_wgs84":BBOX}
    (OUT / "osm_provenance.json").write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding="utf-8")
    print(provenance)


if __name__ == "__main__": main()
