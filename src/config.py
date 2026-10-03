"""
Central configuration for the Long Thanh Airport land-cover project (Phase 1).

Keeping paths, band names and constants here avoids hard-coding them across
src/ modules and the notebook, and makes the pipeline reusable across years.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_SAMPLES_DIR = DATA_DIR / "samples"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
STATISTICS_DIR = OUTPUTS_DIR / "statistics"
REPORTS_OUTPUT_DIR = OUTPUTS_DIR / "reports"

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORT_MD_PATH = REPORTS_DIR / "Phase_1_Data_Preprocessing_and_EDA.md"

for _d in (DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_SAMPLES_DIR,
           FIGURES_DIR, STATISTICS_DIR, REPORTS_OUTPUT_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Study design
# ---------------------------------------------------------------------------
# Target years for the study. The pipeline only processes years for which a
# matching raw file actually exists in data/raw/ -- it never assumes missing
# years are available.
STUDY_YEARS = [2018, 2020, 2022, 2024, 2026]

# Expected data layout: one stacked, multi-band GeoTIFF per year at
#   data/raw/<year>.tif
# with bands ordered exactly as BAND_NAMES below (Sentinel-2 surface
# reflectance). An optional per-year cloud mask (1 = cloud/invalid,
# 0 = clear) can be provided at data/raw/<year>_cloudmask.tif.
BAND_NAMES = ["B2", "B3", "B4", "B8", "B11", "B12"]
BAND_DESCRIPTIONS = {
    "B2": "Blue",
    "B3": "Green",
    "B4": "Red",
    "B8": "NIR",
    "B11": "SWIR1",
    "B12": "SWIR2",
}
EXPECTED_BAND_COUNT = len(BAND_NAMES)

RGB_BANDS = ("B4", "B3", "B2")  # Red-Green-Blue composite

INDEX_NAMES = ["NDVI", "NDBI", "NDWI"]

FEATURE_NAMES = BAND_NAMES + INDEX_NAMES

CLASS_MAP = {0: "Water", 1: "Vegetation", 2: "Bare Soil", 3: "Built-up"}
CLASS_COLUMN_CANDIDATES = ["class", "label"]

# ---------------------------------------------------------------------------
# Sentinel-2 surface reflectance conventions
# ---------------------------------------------------------------------------
# Sentinel-2 L2A surface reflectance is typically stored as uint16 scaled by
# this factor. Pixels outside [0, REFLECTANCE_SCALE] are flagged as
# out-of-range/invalid rather than silently clipped.
REFLECTANCE_SCALE = 10000
VALID_RAW_MIN = 0
VALID_RAW_MAX = 10000

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# Number of valid pixels sampled per image for the tabular feature dataset
# used in EDA (kept well below full-image size so nothing large ever has to
# be held in RAM at once).
N_SAMPLES_PER_YEAR = 20_000


def raw_image_path(year: int) -> Path:
    return DATA_RAW_DIR / f"{year}.tif"


def cloud_mask_path(year: int) -> Path:
    return DATA_RAW_DIR / f"{year}_cloudmask.tif"


def aoi_path() -> Path:
    return DATA_RAW_DIR / "aoi_boundary.geojson"


def training_samples_path():
    """Return the first training-sample vector/table file found, if any."""
    patterns = ("*.geojson", "*.shp", "*.csv", "*.gpkg")
    for pattern in patterns:
        matches = sorted(DATA_SAMPLES_DIR.glob(pattern))
        if matches:
            return matches[0]
    return None


def available_years() -> list[int]:
    """Years in STUDY_YEARS that actually have a raw image on disk."""
    return [y for y in STUDY_YEARS if raw_image_path(y).exists()]
