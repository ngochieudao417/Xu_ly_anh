"""
Task 3.1 + 3.2: xay dung composite Sentinel-2 khong may (median, mua kho)
tren GEE cho AOI chuan, va tinh bo 9 dac trung (6 band pho + NDVI/NDBI/NDWI).
"""

from __future__ import annotations

import ee

from src.gee import config as gcfg

# Cac lop SCL coi la may/bong may/cirrus mong -- giong quy uoc da dung o
# pipeline AWS/STAC truoc do de nhat quan.
SCL_CLOUD_CODES = [3, 8, 9, 10]


def _mask_clouds_scl(image: "ee.Image") -> "ee.Image":
    scl = image.select("SCL")
    cloud_mask = scl.remap(SCL_CLOUD_CODES, [1] * len(SCL_CLOUD_CODES), 0).eq(0)
    return image.updateMask(cloud_mask)


def get_year_collection(year: int) -> "ee.ImageCollection":
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    start, end = gcfg.date_range(year)
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", gcfg.MAX_CLOUD_PROB))
    )


def add_indices(image: "ee.Image") -> "ee.Image":
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    return image.addBands([ndvi, ndbi, ndwi])


def build_composite(year: int) -> "ee.Image":
    """
    Composite trung vi (median), khong may (SCL), mua kho ket thuc trong
    `year`, cat theo AOI chuan, gom 6 band pho goc + 3 chi so (9 band).
    """
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    col = get_year_collection(year).map(_mask_clouds_scl)

    composite = (
        col.select(gcfg.BAND_NAMES)
        .median()
        .clip(aoi)
        .toFloat()
        .divide(gcfg.REFLECTANCE_SCALE)
    )
    composite = add_indices(composite)
    return composite.set({"year": year, "system:time_start": ee.Date(gcfg.date_range(year)[1]).millis()})


def scene_count(year: int) -> int:
    """So anh dung de composite (sau loc may thap) -- dung de bao cao/QC."""
    return get_year_collection(year).size().getInfo()
