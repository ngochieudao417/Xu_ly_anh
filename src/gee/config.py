"""
Cau hinh cho pipeline Google Earth Engine (Phase 2): AOI chuan, cac nam
nghien cuu, dinh nghia band/chi so, va bang anh xa ESA WorldCover -> 4 lop
land-cover cua du an.

AOI va service account duoc giu nguyen nhu Minh/team da chot, khong tu y doi.
"""

from __future__ import annotations

from pathlib import Path

import ee

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Xac thuc GEE
# ---------------------------------------------------------------------------
GEE_KEY_PATH = PROJECT_ROOT / "key_GEE" / "nth-period-425718-i5-9141ae282d31.json"
GEE_SERVICE_ACCOUNT = "gee-longthanh@nth-period-425718-i5.iam.gserviceaccount.com"

_initialized = False


def init_ee():
    """Khoi tao ket noi Earth Engine (idempotent trong 1 process)."""
    global _initialized
    if _initialized:
        return
    credentials = ee.ServiceAccountCredentials(GEE_SERVICE_ACCOUNT, str(GEE_KEY_PATH))
    ee.Initialize(credentials)
    _initialized = True


# ---------------------------------------------------------------------------
# AOI chuan (do Minh/team cung cap, giu nguyen toa do)
# ---------------------------------------------------------------------------
AIRPORT_CENTER = [107.04111, 10.78444]

AOI_COORDS = [[
    [106.98849946776265, 10.814327243656404],
    [106.98849946776265, 10.736755380981812],
    [107.09698945799703, 10.736755380981812],
    [107.09698945799703, 10.814327243656404],
]]


def get_aoi() -> "ee.Geometry":
    init_ee()
    return ee.Geometry.Polygon(AOI_COORDS, None, False)


def get_airport_point() -> "ee.Geometry":
    init_ee()
    return ee.Geometry.Point(AIRPORT_CENTER)


# ---------------------------------------------------------------------------
# Nam nghien cuu + khung thoi gian lay composite
# ---------------------------------------------------------------------------
# Composite theo mua kho (thang 12 nam truoc - thang 4 nam sau) de giam may,
# gan voi mua kho Nam Bo (thang 12 - thang 4).
STUDY_YEARS = [2018, 2020, 2022, 2024, 2026]

def date_range(year: int) -> tuple[str, str]:
    """Khung ngay mua kho ket thuc trong nam `year` (vd 2022 -> 2021-12-01..2022-04-30)."""
    return f"{year - 1}-12-01", f"{year}-04-30"

MAX_CLOUD_PROB = 60  # loc scene truoc khi mask, tranh anh toan may

# ---------------------------------------------------------------------------
# Band / dac trung
# ---------------------------------------------------------------------------
S2_BAND_MAP = {  # ten du an -> ten band Sentinel-2 (COPERNICUS/S2_SR_HARMONIZED)
    "B2": "B2", "B3": "B3", "B4": "B4", "B8": "B8", "B11": "B11", "B12": "B12",
}
BAND_NAMES = list(S2_BAND_MAP.keys())
INDEX_NAMES = ["NDVI", "NDBI", "NDWI"]
FEATURE_NAMES_9 = BAND_NAMES + INDEX_NAMES  # phuong an A (9 band)
FEATURE_NAMES_5 = ["B4", "B8", "B11", "NDVI", "NDBI"]  # phuong an B (5 band, ban dau -- co the dieu chinh sau khi xem feature importance)

REFLECTANCE_SCALE = 10000

# ---------------------------------------------------------------------------
# Lop land-cover cua du an
# ---------------------------------------------------------------------------
CLASS_MAP = {0: "Water", 1: "Vegetation", 2: "Bare Soil", 3: "Built-up"}
CLASS_COL = "class"

# ESA WorldCover (10m) -> 4 lop cua du an. WorldCover v200 = nam 2021.
# https://esa-worldcover.org/en : 10 Tree cover, 20 Shrubland, 30 Grassland,
# 40 Cropland, 50 Built-up, 60 Bare/sparse veg, 70 Snow/ice, 80 Water,
# 90 Herbaceous wetland, 95 Mangroves, 100 Moss/lichen.
WORLDCOVER_TO_CLASS = {
    10: 1, 20: 1, 30: 1, 40: 1,   # Vegetation
    50: 3,                        # Built-up
    60: 2,                        # Bare Soil
    80: 0, 90: 0, 95: 0,          # Water (bao gom dat ngap nuoc/rung ngap man)
}
WORLDCOVER_ASSET = "ESA/WorldCover/v200"

# Nam dung lam moc lay mau (gan nhat voi WorldCover v200 = 2021).
REFERENCE_YEAR_FOR_SAMPLING = 2022

SAMPLES_PER_CLASS = 300
SAMPLE_SEED = 42
TRAIN_FRACTION = 0.7

# ---------------------------------------------------------------------------
# Duong dan output
# ---------------------------------------------------------------------------
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
GEE_STATS_DIR = OUTPUTS_DIR / "statistics" / "gee"
GEE_FIGURES_DIR = OUTPUTS_DIR / "figures" / "gee"
GEE_MAPS_DIR = OUTPUTS_DIR / "maps"
for _d in (GEE_STATS_DIR, GEE_FIGURES_DIR, GEE_MAPS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
