"""
Task 3.3: lay mau tu ESA WorldCover (remap ve 4 lop cua du an), stratified
sampling 300 diem/lop (seed=42), tach train/test 70/30.
"""

from __future__ import annotations

import ee

from src.gee import config as gcfg
from src.gee import composite as gcomp


def get_class_image() -> "ee.Image":
    """Anh WorldCover da remap ve 4 lop du an (0=Water,1=Vegetation,2=Bare Soil,3=Built-up)."""
    gcfg.init_ee()
    wc = ee.ImageCollection(gcfg.WORLDCOVER_ASSET).first().select("Map")
    from_vals = list(gcfg.WORLDCOVER_TO_CLASS.keys())
    to_vals = list(gcfg.WORLDCOVER_TO_CLASS.values())
    return wc.remap(from_vals, to_vals, defaultValue=-1).rename(gcfg.CLASS_COL)


def class_pixel_histogram() -> dict:
    """Dem so pixel WorldCover (da remap) theo tung lop trong AOI -- dung de kiem tra du mau truoc khi sample."""
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    class_img = get_class_image()
    hist = class_img.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), geometry=aoi, scale=10, maxPixels=1e9, bestEffort=True,
    ).getInfo()
    raw = hist.get(gcfg.CLASS_COL, {})
    return {int(float(k)): int(v) for k, v in raw.items()}


def build_labeled_samples(reference_year: int = gcfg.REFERENCE_YEAR_FOR_SAMPLING) -> "ee.FeatureCollection":
    """
    Stratified-sample diem tu lop WorldCover (4 lop), lay gia tri 9 dac
    trung tu composite cua `reference_year` tai cac diem do.
    """
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    class_img = get_class_image()
    composite = gcomp.build_composite(reference_year)

    sample_image = composite.addBands(class_img.toInt())
    class_values = sorted(gcfg.CLASS_MAP.keys())
    samples = sample_image.stratifiedSample(
        numPoints=gcfg.SAMPLES_PER_CLASS,
        classBand=gcfg.CLASS_COL,
        region=aoi,
        scale=10,
        seed=gcfg.SAMPLE_SEED,
        classValues=class_values,
        classPoints=[gcfg.SAMPLES_PER_CLASS] * len(class_values),
        geometries=True,
        dropNulls=True,
    )
    return samples.map(lambda f: f.set("reference_year", reference_year))


WATER_NDWI_MIN = 0.0  # nguong loc diem "Water" theo QC truc quan (~30% nham, chu yeu la duong/mai nha)
WATER_OVERSAMPLE = 950  # gan het quan the Water trong AOI (~1002 pixel) de co du diem sau khi loc


def build_labeled_samples_cleaned(reference_year: int = gcfg.REFERENCE_YEAR_FOR_SAMPLING) -> tuple["ee.FeatureCollection", dict]:
    """
    Nhu build_labeled_samples, nhung loc rieng lop Water: lay gan het quan
    the diem Water trong AOI, bo cac diem co NDWI <= WATER_NDWI_MIN (nghi
    la duong/nha bi WorldCover gan nham "nuoc" -- phat hien qua QC truc
    quan task 3.4), roi chon lai toi da SAMPLES_PER_CLASS diem sach nhat
    (uu tien NDWI cao) de giu tap mau on dinh, tai lap duoc.

    Tra ve (FeatureCollection da lam sach, thong ke loc de ghi vao bao cao).
    """
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    class_img = get_class_image()
    composite = gcomp.build_composite(reference_year)
    sample_image = composite.addBands(class_img.toInt())

    # LUU Y: stratifiedSample chi gioi han classPoints cho cac lop liet ke
    # trong classValues; lop KHONG liet ke nhung van co mat trong vung se
    # tu dong duoc lay theo numPoints (mac dinh), gay "ro ri" mau lop khac
    # vao ket qua. De an toan, luon loc cung lai bang class sau khi sample,
    # khong chi dua vao classValues/classPoints.
    other_classes = [c for c in sorted(gcfg.CLASS_MAP) if c != 0]
    others_raw = sample_image.stratifiedSample(
        numPoints=gcfg.SAMPLES_PER_CLASS, classBand=gcfg.CLASS_COL, region=aoi, scale=10,
        seed=gcfg.SAMPLE_SEED, classValues=other_classes,
        classPoints=[gcfg.SAMPLES_PER_CLASS] * len(other_classes), geometries=True, dropNulls=True,
    )
    others = others_raw.filter(ee.Filter.inList(gcfg.CLASS_COL, other_classes))

    water_candidates_raw = sample_image.stratifiedSample(
        numPoints=WATER_OVERSAMPLE, classBand=gcfg.CLASS_COL, region=aoi, scale=10,
        seed=gcfg.SAMPLE_SEED, classValues=[0], classPoints=[WATER_OVERSAMPLE],
        geometries=True, dropNulls=True,
    )
    water_candidates = water_candidates_raw.filter(ee.Filter.eq(gcfg.CLASS_COL, 0))
    n_candidates = water_candidates.size().getInfo()
    water_clean = water_candidates.filter(ee.Filter.gt("NDWI", WATER_NDWI_MIN))
    n_clean = water_clean.size().getInfo()

    if n_clean > gcfg.SAMPLES_PER_CLASS:
        water_final = (
            water_clean.randomColumn("__sort", gcfg.SAMPLE_SEED)
            .sort("__sort")
            .limit(gcfg.SAMPLES_PER_CLASS)
            .select(water_clean.first().propertyNames())
        )
        n_final = gcfg.SAMPLES_PER_CLASS
    else:
        water_final = water_clean
        n_final = n_clean

    combined = water_final.merge(others).map(lambda f: f.set("reference_year", reference_year))
    stats = {
        "water_candidates": n_candidates,
        "water_passed_ndwi_filter": n_clean,
        "water_final_used": n_final,
        "water_removed_pct": 100 * (1 - n_clean / n_candidates) if n_candidates else None,
        "ndwi_threshold": WATER_NDWI_MIN,
    }
    return combined, stats


def train_test_split(samples: "ee.FeatureCollection") -> tuple["ee.FeatureCollection", "ee.FeatureCollection"]:
    """Chia 70/30 bang cot ngau nhien co seed co dinh (tai lap duoc)."""
    with_rand = samples.randomColumn("__rand", gcfg.SAMPLE_SEED)
    train = with_rand.filter(ee.Filter.lt("__rand", gcfg.TRAIN_FRACTION))
    test = with_rand.filter(ee.Filter.gte("__rand", gcfg.TRAIN_FRACTION))
    return train, test
