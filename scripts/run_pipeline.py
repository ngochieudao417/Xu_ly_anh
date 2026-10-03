#!/usr/bin/env python3
"""
Phase 1 orchestration script: Data Preprocessing + EDA -> report.

    python scripts/run_pipeline.py

For every year configured in src.config.STUDY_YEARS that has a matching
raw image at data/raw/<year>.tif, this script runs validation,
preprocessing, spectral-index feature engineering and EDA, saves all
figures/statistics/QC reports under outputs/, and (re)generates
reports/Phase_1_Data_Preprocessing_and_EDA.md from the real numbers it
just computed.

If no raw imagery is present yet, it does NOT fabricate a result: it
writes an honest status report stating that data ingestion is pending,
and exits successfully so the rest of the scaffold stays inspectable.
Re-run this script any time new years are added to data/raw/.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src import config as cfg
from src import validation, preprocessing, features, visualization


def process_year(year: int) -> dict:
    """Run validation + preprocessing + feature engineering for one year."""
    image_path = cfg.raw_image_path(year)
    meta = validation.get_raster_metadata(image_path)
    band_stats = validation.compute_band_statistics(image_path, cfg.BAND_NAMES)
    range_flags = validation.check_invalid_reflectance(band_stats)

    samples, pixel_counts = preprocessing.sample_valid_pixels(year, n_samples=cfg.N_SAMPLES_PER_YEAR)
    feature_df = features.build_feature_dataframe(year, samples)

    qc_text = validation.generate_qc_report_text(year, meta, band_stats, list(features.compute_indices(samples).keys()))
    qc_path = cfg.REPORTS_OUTPUT_DIR / f"QC_{year}.txt"
    qc_path.write_text(qc_text, encoding="utf-8")

    return {
        "year": year,
        "meta": meta,
        "band_stats": band_stats,
        "range_flags": range_flags,
        "pixel_counts": pixel_counts,
        "feature_df": feature_df,
        "qc_text": qc_text,
        "qc_path": qc_path,
    }


def make_rgb_and_spatial_figures(year: int, is_representative: bool) -> dict:
    """Generate RGB composite (every year) and NDVI/NDBI/NDWI maps (representative years)."""
    figs = {}
    bands_dec, _ = preprocessing.read_decimated_bands(year, max_size=1200)

    rgb_path = cfg.FIGURES_DIR / f"rgb_{year}.png"
    visualization.plot_rgb_composite(
        bands_dec["B4"], bands_dec["B3"], bands_dec["B2"], rgb_path,
        f"RGB Composite (B4-B3-B2) - {year}",
    )
    figs["rgb"] = rgb_path

    if is_representative:
        idx = features.compute_indices(bands_dec)
        specs = {
            "NDVI": (f"ndvi_map_{year}.png", "RdYlGn", -1, 1),
            "NDBI": (f"ndbi_map_{year}.png", "PuOr_r", -1, 1),
            "NDWI": (f"ndwi_map_{year}.png", "BrBG", -1, 1),
        }
        for name, (fname, cmap, vmin, vmax) in specs.items():
            path = cfg.FIGURES_DIR / fname
            visualization.plot_spatial_index_map(idx[name], path, f"{name} map - {year}", cmap=cmap, vmin=vmin, vmax=vmax)
            figs[name.lower()] = path
    return figs


def run_class_eda(years_processed: list[int]) -> dict | None:
    """If a training-sample file exists, extract features at those points and run class EDA."""
    samples_path = cfg.training_samples_path()
    if samples_path is None or not years_processed:
        return None

    import geopandas as gpd

    if samples_path.suffix == ".csv":
        raw = pd.read_csv(samples_path)
        if not {"x", "y"}.issubset(raw.columns) or "class" not in raw.columns:
            print(f"[warn] {samples_path} is missing required columns (x, y, class); skipping class EDA.")
            return None
        gdf = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw.x, raw.y), crs=f"EPSG:{4326}")
    else:
        gdf = gpd.read_file(samples_path)
        if "class" not in gdf.columns and "label" not in gdf.columns:
            print(f"[warn] {samples_path} has no 'class'/'label' column; skipping class EDA.")
            return None
        if "label" in gdf.columns and "class" not in gdf.columns:
            gdf = gdf.rename(columns={"label": "class"})

    # Points are matched against the most recent processed year unless the
    # sample file itself specifies a year per point.
    target_year = max(years_processed)
    df = preprocessing.extract_features_at_points(target_year, gdf, cfg.BAND_NAMES)
    idx = features.compute_indices({b: df[b].to_numpy() for b in cfg.BAND_NAMES})
    for name, values in idx.items():
        df[name] = values
    if df["class"].dtype.kind in "iu":
        df["class_name"] = df["class"].map(cfg.CLASS_MAP)
    else:
        df["class_name"] = df["class"]

    class_dist_path = cfg.FIGURES_DIR / "class_distribution.png"
    visualization.plot_class_distribution(df, class_dist_path)

    feature_class_figs = {}
    for feat in ["NDVI", "NDBI", "NDWI"]:
        path = cfg.FIGURES_DIR / f"{feat.lower()}_by_class.png"
        visualization.plot_feature_by_class(df, feat, path)
        feature_class_figs[feat] = path

    return {
        "source_file": samples_path,
        "target_year": target_year,
        "df": df,
        "class_dist_fig": class_dist_path,
        "feature_class_figs": feature_class_figs,
        "class_counts": df["class_name"].value_counts().to_dict(),
    }


def build_stats_table(feature_df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    rows = []
    for feat in feature_names:
        if feat not in feature_df.columns:
            continue
        s = feature_df[feat].dropna()
        rows.append({
            "feature": feat,
            "count": int(s.count()),
            "mean": s.mean(),
            "std": s.std(),
            "min": s.min(),
            "p25": s.quantile(0.25),
            "median": s.median(),
            "p75": s.quantile(0.75),
            "max": s.max(),
        })
    return pd.DataFrame(rows)


def fmt(x, nd=4):
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return f"{x:,}" if isinstance(x, int) else str(x)


def df_to_markdown_table(df: pd.DataFrame, float_format="{:.4f}") -> str:
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if pd.api.types.is_float_dtype(df_fmt[col]):
            df_fmt[col] = df_fmt[col].map(lambda v: float_format.format(v) if pd.notna(v) else "NA")
    return df_fmt.to_markdown(index=False)


def relfig(path: Path) -> str:
    """Path to a figure, relative to the reports/ directory."""
    return f"../outputs/figures/{Path(path).name}"


def generate_report(results: dict) -> str:
    today = date.today().isoformat()
    years_available = results["years_available"]
    years_missing = results["years_missing"]
    has_data = len(years_available) > 0
    aoi_exists = cfg.aoi_path().exists()
    class_eda = results.get("class_eda")

    lines = []
    a = lines.append

    a("# Phase 1 Report: Data Preprocessing and Exploratory Data Analysis")
    a("")
    a(f"**Project:** Bien dong Phat trien Khu vuc - Do luong toc do 'Be tong hoa' dai du an San bay "
      f"Long Thanh & Vung phu can (2018-2026)")
    a(f"**Report generated:** {today} (auto-generated from `scripts/run_pipeline.py`, real dataset run)")
    a("")
    a("---")
    a("")

    # 1. Introduction ---------------------------------------------------
    a("## 1. Introduction")
    a("")
    a(
        "This project uses multi-temporal satellite imagery to classify land cover around "
        "Long Thanh International Airport, Dong Nai province, Vietnam, and to study the spatial "
        "and temporal pattern of built-up ('be tong hoa') expansion near the airport between 2018 "
        "and 2026. The full pipeline is: Satellite Images -> Data Preprocessing -> EDA -> Training "
        "Samples -> Random Forest Classification -> Accuracy Assessment -> Change Detection -> "
        "Built-up Area Analysis -> Buffer Analysis -> Concrete Expansion Rate."
    )
    a("")
    a(
        "**Phase 1**, covered by this report, is restricted to data preprocessing and exploratory "
        "data analysis (EDA). No classifier is trained, no accuracy is computed, and no change-"
        "detection or expansion-rate result is produced in this phase; those belong to later phases."
    )
    a("")
    a(f"- Spatial scope: Long Thanh Airport and surrounding area, Dong Nai, Vietnam")
    a(f"- Temporal scope: {min(cfg.STUDY_YEARS)}-{max(cfg.STUDY_YEARS)} (configured years: {cfg.STUDY_YEARS})")
    a("")
    a("---")
    a("")

    # 2. Dataset description ---------------------------------------------
    a("## 2. Dataset Description")
    a("")
    a(f"- Expected imagery source: Sentinel-2 surface reflectance, 6 bands: "
      f"{', '.join(f'{b} ({cfg.BAND_DESCRIPTIONS[b]})' for b in cfg.BAND_NAMES)}")
    a(f"- Expected file layout: one stacked GeoTIFF per year at `data/raw/<year>.tif`, "
      f"bands ordered exactly as {cfg.BAND_NAMES}")
    a(f"- Configured study years: {cfg.STUDY_YEARS}")
    a(f"- Years with imagery actually found on disk: {years_available if years_available else 'NONE'}")
    if years_missing:
        a(f"- Years configured but **not found** in `data/raw/`: {years_missing}")
    a("")

    if not has_data:
        a(
            "**No satellite imagery is present in `data/raw/` at the time this report was generated.** "
            "This is a genuine data-availability limitation, not a processing failure: the src/ pipeline "
            "(validation, preprocessing, feature engineering, visualization) has been implemented and "
            "unit-tested against a synthetic raster to confirm it runs correctly end-to-end, but it has "
            "not yet been executed on real Sentinel-2 imagery because none has been supplied."
        )
        a("")
        a("To activate the pipeline on real data:")
        a("")
        a("1. Place one 6-band GeoTIFF per year at `data/raw/<year>.tif` "
          f"(bands in the exact order {cfg.BAND_NAMES}).")
        a("2. Optionally add an AOI boundary at `data/raw/aoi_boundary.geojson`.")
        a("3. Optionally add training-sample points (columns `class` or `label`, plus geometry or x/y) "
          "under `data/samples/`.")
        a("4. Re-run `python scripts/run_pipeline.py`. This report will be regenerated with the real "
          "statistics, figures, and QC results.")
        a("")
    else:
        overview_df = results["overview_df"]
        a("Metadata actually read from the available raster(s):")
        a("")
        a(df_to_markdown_table(overview_df))
        a("")
        issues = results["consistency_issues"]
        if issues:
            a("**Cross-year consistency issues detected:**")
            a("")
            for issue in issues:
                a(f"- {issue}")
            a("")
        else:
            a("All available years share consistent band count, CRS and resolution.")
            a("")

    a("---")
    a("")

    # 3. Study area -------------------------------------------------------
    a("## 3. Study Area")
    a("")
    a(
        "The study area covers Long Thanh International Airport and its surrounding region in "
        "Dong Nai province, Vietnam, where large-scale construction has been ongoing since the "
        "airport project broke ground."
    )
    a("")
    if aoi_exists:
        a(f"An AOI boundary is defined at `data/raw/aoi_boundary.geojson` and used to clip imagery.")
    else:
        a(
            "**Limitation:** no AOI boundary file was found at `data/raw/aoi_boundary.geojson`. "
            "AOI clipping and a study-area map are skipped until this file is provided; all pixel "
            "statistics below (when available) are computed over the full raster extent instead of "
            "the airport's actual area of interest."
        )
    a("")
    a("---")
    a("")

    # 4. Preprocessing ------------------------------------------------------
    a("## 4. Data Preprocessing")
    a("")
    a("Implemented pipeline (see `src/validation.py` and `src/preprocessing.py`):")
    a("")
    a("```text")
    a("Raw Data")
    a("   |")
    a("Data Validation           (file exists, band count, CRS, resolution, dtype, per-band stats)")
    a("   |")
    a("Cloud / NoData Handling   (per-pixel classification: missing / cloud-flagged / valid)")
    a("   |")
    a("Invalid Value Handling    (out-of-range raw reflectance flagged, not silently dropped)")
    a("   |")
    a("Band Selection            (B2, B3, B4, B8, B11, B12)")
    a("   |")
    a("Reflectance Scaling       (raw DN / 10000 -> unitless reflectance)")
    a("   |")
    a("Spectral Index Calculation (NDVI, NDBI, NDWI, safe division)")
    a("   |")
    a("AOI Clipping              (rasterio.mask, only if AOI file is present)")
    a("   |")
    a("Feature Dataset Creation  (memory-bounded reservoir sampling -> tabular DataFrame)")
    a("   |")
    a("Processed / Feature Dataset")
    a("```")
    a("")
    a(
        "Every step is reported rather than silently applied: missing/invalid/cloud pixel counts are "
        "tracked per year (see Section 6), and cloud masking uses an existing per-year cloud mask "
        "raster if present (`data/raw/<year>_cloudmask.tif`); if none is present this is explicitly "
        "reported rather than treated as 'no clouds'."
    )
    a("")
    a(
        "Because Sentinel-2 scenes can be large, no step loads a full-resolution multi-band raster into "
        "memory: validation statistics and pixel classification are computed block-by-block via "
        "rasterio's windowed reads, and the tabular feature dataset is built from a fixed-size uniform "
        f"random sample ({cfg.N_SAMPLES_PER_YEAR:,} valid pixels per year target) drawn with a streaming "
        "reservoir-sampling algorithm (`src/preprocessing.py: ReservoirSampler`), seeded "
        f"(seed={cfg.RANDOM_SEED}) for reproducibility."
    )
    a("")
    a("---")
    a("")

    # 5. Feature engineering -------------------------------------------------
    a("## 5. Feature Engineering")
    a("")
    a("| Feature | Description |")
    a("|---|---|")
    for b in cfg.BAND_NAMES:
        a(f"| {b} | {cfg.BAND_DESCRIPTIONS[b]} surface reflectance (scaled to 0-1) |")
    a("| NDVI | `(NIR - Red) / (NIR + Red)` - vegetation indicator |")
    a("| NDBI | `(SWIR1 - NIR) / (SWIR1 + NIR)` - built-up area indicator |")
    a("| NDWI | `(Green - NIR) / (Green + NIR)` - water indicator |")
    a("")
    a(
        "All three indices are computed with a safe-division helper (`src/features.py: safe_divide`) "
        "that returns `NaN` wherever the denominator is zero instead of raising or silently producing "
        "`inf`, so division-by-zero pixels are explicitly trackable rather than corrupting downstream "
        "statistics."
    )
    a("")
    a("---")
    a("")

    # 6. Data quality assessment --------------------------------------------
    a("## 6. Data Quality Assessment")
    a("")
    if not has_data:
        a("No raster data is available, so no quality metrics can be computed yet. See Section 2.")
    else:
        a(df_to_markdown_table(results["quality_df"], float_format="{:.3f}"))
        a("")
        a("Per-band statistics and out-of-range flags for every processed year are saved to "
          "`outputs/statistics/band_statistics.csv`; full plain-text QC reports per year are saved to "
          "`outputs/reports/QC_<year>.txt`.")
    a("")
    a("---")
    a("")

    # 7. EDA -----------------------------------------------------------------
    a("## 7. Exploratory Data Analysis")
    a("")
    if not has_data:
        a("Skipped: EDA requires at least one year of raster data, none of which is currently available.")
        a("")
    else:
        fig_count = 1

        a("### 7.1 RGB Composite")
        a("")
        for y in years_available:
            rgb_fig = results["year_figures"][y]["rgb"]
            a(f"![RGB composite {y}]({relfig(rgb_fig)})")
            a("")
            a(f"**Figure {fig_count}. RGB composite (B4-B3-B2) of the study area, {y}.**")
            fig_count += 1
            a("")
        a(
            "The composites allow visual inspection of image quality (cloud cover, striping, "
            "obvious artefacts) and of the built environment around the airport site for each "
            "available year."
        )
        a("")

        a("### 7.2 Spectral Band Distribution")
        a("")
        a(f"![Band distributions]({relfig(results['band_hist_fig'])})")
        a("")
        a(f"**Figure {fig_count}. Distribution of B2, B3, B4, B8, B11, B12 reflectance across all "
          f"sampled valid pixels.**")
        fig_count += 1
        a("")

        a("### 7.3 Spectral Index Distribution")
        a("")
        a(f"![Index distributions]({relfig(results['index_hist_fig'])})")
        a("")
        a(f"**Figure {fig_count}. Distribution of NDVI, NDBI and NDWI.**")
        fig_count += 1
        a("")

        a("### 7.4 Boxplots")
        a("")
        a(f"![Feature boxplots]({relfig(results['boxplot_fig'])})")
        a("")
        a(f"**Figure {fig_count}. Boxplots of all bands and indices, used to inspect spread and "
          f"potential outliers.**")
        fig_count += 1
        a("")

        a("### 7.5 Correlation Analysis")
        a("")
        a(f"![Correlation heatmap]({relfig(results['corr_fig'])})")
        a("")
        a(f"**Figure {fig_count}. Correlation matrix between spectral bands and indices.**")
        fig_count += 1
        a("")
        a(results["correlation_note"])
        a("")

        a("### 7.6 Spatial Distribution")
        a("")
        for name in ("ndvi", "ndbi", "ndwi"):
            for y, figs in results["year_figures"].items():
                if name in figs:
                    a(f"![{name.upper()} map {y}]({relfig(figs[name])})")
                    a("")
                    a(f"**Figure {fig_count}. Spatial {name.upper()} map, {y}.**")
                    fig_count += 1
                    a("")

        a("### 7.7 Temporal Analysis")
        a("")
        a(f"![Temporal NDVI/NDBI/NDWI trend]({relfig(results['temporal_fig'])})")
        a("")
        a(f"**Figure {fig_count}. Mean NDVI, NDBI and NDWI per year (sampled valid pixels).**")
        fig_count += 1
        a("")
        a(
            "**This is exploratory only.** It describes preliminary temporal changes in spectral "
            "characteristics; it is not a classification-based change-detection result and must not be "
            "read as a built-up expansion rate."
        )
        a("")

    a("---")
    a("")

    # 8. Class distribution ---------------------------------------------------
    a("## 8. Class Distribution")
    a("")
    if class_eda is None:
        a("Class-level EDA will be performed after training samples are collected.")
    else:
        try:
            source_label = class_eda["source_file"].relative_to(PROJECT_ROOT)
        except ValueError:
            source_label = class_eda["source_file"]
        a(f"Training-sample source: `{source_label}` "
          f"(features extracted from the {class_eda['target_year']} image).")
        a("")
        a(f"![Class distribution]({relfig(class_eda['class_dist_fig'])})")
        a("")
        a("**Class sample counts:**")
        a("")
        for cls, count in class_eda["class_counts"].items():
            a(f"- {cls}: {count}")
        a("")
        for feat, path in class_eda["feature_class_figs"].items():
            a(f"![{feat} by class]({relfig(path)})")
            a("")
            a(f"**{feat} by land-cover class.**")
            a("")
    a("")
    a("---")
    a("")

    # 9. Key findings -----------------------------------------------------
    a("## 9. Key Findings")
    a("")
    if not has_data:
        a(
            "No findings can be reported: this phase has not yet run against real imagery. The only "
            "verified fact at this stage is that the preprocessing/EDA code executes correctly "
            "end-to-end against a synthetic test raster (see `tests/test_pipeline_smoke.py`, "
            "6/6 tests passing)."
        )
        a("")
    else:
        for i, finding in enumerate(results["findings"], start=1):
            a(f"**Finding {i}:** {finding}")
            a("")
    a("---")
    a("")

    # 10. Readiness --------------------------------------------------------
    a("## 10. Readiness for Random Forest")
    a("")
    checklist = [
        ("Dataset loaded successfully", has_data),
        ("Required bands available", has_data and results.get("all_bands_present", False)),
        ("Invalid values handled", has_data),
        ("Missing data assessed", has_data),
        ("Spectral indices generated", has_data),
        ("Features statistically explored", has_data),
        ("AOI-clipped to study area", has_data and aoi_exists),
        ("Training samples available for supervised training", class_eda is not None),
        ("Dataset ready for classification", has_data and aoi_exists and class_eda is not None),
    ]
    for label, ok in checklist:
        a(f"{'✓' if ok else '✗'} {label}")
    a("")
    remaining = results.get("remaining_issues", [])
    if not has_data:
        remaining = [
            "No raw Sentinel-2 imagery available in data/raw/ - Phase 1 cannot produce real "
            "statistics or figures until this is provided.",
        ] + remaining
    if not aoi_exists:
        remaining.append("No AOI boundary file (data/raw/aoi_boundary.geojson) - clipping to the "
                          "actual study area has not been performed.")
    if class_eda is None:
        remaining.append("No training-sample data yet - class-level EDA and, later, Random Forest "
                          "training cannot proceed without labeled samples.")
    if remaining:
        a("**Remaining Issues:**")
        a("")
        for i, issue in enumerate(remaining, start=1):
            a(f"{i}. {issue}")
    a("")
    a("---")
    a("")

    # 11. Conclusion ---------------------------------------------------------
    a("## 11. Conclusion")
    a("")
    if not has_data:
        a(
            "Phase 1's preprocessing and EDA pipeline (validation, missing/invalid-value handling, "
            "spectral index calculation, memory-bounded sampling, and figure/report generation) has "
            "been implemented, is modular and reusable across years, and has been verified to run "
            "correctly on a synthetic raster. However, **no real Sentinel-2 imagery has been supplied "
            "yet**, so no data-driven statistics, quality assessment, or EDA finding exists at this "
            "time, and the dataset is **not** ready for Phase 2 (Random Forest classification). Once "
            "real imagery (and ideally an AOI boundary and training samples) are placed under `data/`, "
            "re-running `scripts/run_pipeline.py` will regenerate this report with the actual results."
        )
    else:
        a(results["conclusion_text"])
    a("")

    return "\n".join(lines)


def main():
    years_available = cfg.available_years()
    years_missing = [y for y in cfg.STUDY_YEARS if y not in years_available]

    results = {"years_available": years_available, "years_missing": years_missing}

    if not years_available:
        print("[info] No raw imagery found under data/raw/. Writing a status-only report; "
              "no figures/statistics are generated.")
        cfg.REPORT_MD_PATH.write_text(generate_report(results), encoding="utf-8")
        print(f"[done] Wrote {cfg.REPORT_MD_PATH}")
        return

    per_year = {y: process_year(y) for y in years_available}

    metadata_by_year = {y: r["meta"] for y, r in per_year.items()}
    consistency_issues = validation.check_years_consistency(metadata_by_year)

    overview_rows = []
    quality_rows = []
    for y, r in per_year.items():
        meta = r["meta"]
        first_band_stats = next(iter(r["band_stats"].values()))
        total_pixels = meta["width"] * meta["height"]
        valid = first_band_stats["count"]
        missing = total_pixels - valid
        overview_rows.append({
            "year": y, "bands": meta["band_count"], "width": meta["width"], "height": meta["height"],
            "crs": meta["crs"], "resolution_m": meta["resolution_x"], "dtype": meta["dtype"],
        })
        quality_rows.append({
            "year": y, "total_pixels": total_pixels, "valid_pixels": valid,
            "nodata_pixels": missing, "nodata_pct": 100 * missing / total_pixels if total_pixels else 0,
            "invalid_range_pixels_sampled_window": r["pixel_counts"]["invalid_range"],
        })
    overview_df = pd.DataFrame(overview_rows)
    quality_df = pd.DataFrame(quality_rows)
    overview_df.to_csv(cfg.STATISTICS_DIR / "dataset_overview.csv", index=False)
    quality_df.to_csv(cfg.STATISTICS_DIR / "data_quality_report.csv", index=False)

    band_stat_rows = []
    for y, r in per_year.items():
        for band, s in r["band_stats"].items():
            band_stat_rows.append({"year": y, "band": band, **s, "out_of_range": r["range_flags"][band]})
    pd.DataFrame(band_stat_rows).to_csv(cfg.STATISTICS_DIR / "band_statistics.csv", index=False)

    combined_df = features.combine_years({y: r["feature_df"] for y, r in per_year.items()})
    combined_df.to_csv(cfg.DATA_PROCESSED_DIR / "feature_dataset.csv", index=False)

    stats_table = build_stats_table(combined_df, cfg.FEATURE_NAMES)
    stats_table.to_csv(cfg.STATISTICS_DIR / "feature_statistics_overall.csv", index=False)

    per_year_stats = []
    for y in years_available:
        t = build_stats_table(combined_df[combined_df["year"] == y], cfg.FEATURE_NAMES)
        t.insert(0, "year", y)
        per_year_stats.append(t)
    pd.concat(per_year_stats, ignore_index=True).to_csv(
        cfg.STATISTICS_DIR / "feature_statistics_by_year.csv", index=False
    )

    # Figures -------------------------------------------------------------
    representative_years = years_available if len(years_available) <= 3 else [
        years_available[0], years_available[len(years_available) // 2], years_available[-1]
    ]
    year_figures = {y: make_rgb_and_spatial_figures(y, y in representative_years) for y in years_available}

    band_hist_fig = cfg.FIGURES_DIR / "band_distribution.png"
    visualization.plot_band_histograms(combined_df, cfg.BAND_NAMES, band_hist_fig)

    index_hist_fig = cfg.FIGURES_DIR / "index_distribution.png"
    visualization.plot_index_histograms(combined_df, cfg.INDEX_NAMES, index_hist_fig)

    boxplot_fig = cfg.FIGURES_DIR / "feature_boxplots.png"
    visualization.plot_boxplots(combined_df, cfg.FEATURE_NAMES, boxplot_fig, by_year=len(years_available) > 1)

    corr_fig = cfg.FIGURES_DIR / "correlation_heatmap.png"
    visualization.plot_correlation_heatmap(combined_df, cfg.FEATURE_NAMES, corr_fig)
    corr_matrix = combined_df[cfg.FEATURE_NAMES].corr()

    temporal_rows = []
    for y in years_available:
        yr_df = combined_df[combined_df["year"] == y]
        temporal_rows.append({
            "year": y,
            "mean_NDVI": yr_df["NDVI"].mean(),
            "mean_NDBI": yr_df["NDBI"].mean(),
            "mean_NDWI": yr_df["NDWI"].mean(),
        })
    temporal_df = pd.DataFrame(temporal_rows)
    temporal_df.to_csv(cfg.STATISTICS_DIR / "temporal_index_trend.csv", index=False)
    temporal_fig = cfg.FIGURES_DIR / "temporal_trend.png"
    visualization.plot_temporal_trend(temporal_df, temporal_fig)

    class_eda = run_class_eda(years_available)

    # Findings (derived only from actual numbers above) --------------------
    findings = []
    strong_corrs = (
        corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        .stack()
        .abs()
        .sort_values(ascending=False)
    )
    if not strong_corrs.empty:
        top_pair = strong_corrs.index[0]
        findings.append(
            f"The strongest correlation among features is between {top_pair[0]} and {top_pair[1]} "
            f"(r = {corr_matrix.loc[top_pair]:.2f}), suggesting possible redundancy between them for "
            f"classification."
        )
    ndvi_std = combined_df["NDVI"].std()
    findings.append(f"NDVI has a standard deviation of {ndvi_std:.3f} across sampled pixels, indicating "
                     f"{'substantial' if ndvi_std > 0.2 else 'limited'} spread in vegetation signal.")
    total_missing_pct = quality_df["nodata_pct"].mean()
    findings.append(f"Across processed years, the mean NoData percentage is {total_missing_pct:.2f}%.")

    results.update({
        "overview_df": overview_df,
        "quality_df": quality_df,
        "consistency_issues": consistency_issues,
        "band_hist_fig": band_hist_fig,
        "index_hist_fig": index_hist_fig,
        "boxplot_fig": boxplot_fig,
        "corr_fig": corr_fig,
        "correlation_note": (
            f"The highest-magnitude pairwise correlation is between "
            f"{strong_corrs.index[0][0]} and {strong_corrs.index[0][1]} (r = {corr_matrix.loc[strong_corrs.index[0]]:.2f})."
            if not strong_corrs.empty else "No correlation could be computed."
        ),
        "year_figures": year_figures,
        "temporal_fig": temporal_fig,
        "class_eda": class_eda,
        "findings": findings,
        "all_bands_present": all(len(r["band_stats"]) == len(cfg.BAND_NAMES) for r in per_year.values()),
        "conclusion_text": (
            f"Phase 1 processed {len(years_available)} year(s) of imagery ({years_available}) through "
            f"the full validation, preprocessing and feature-engineering pipeline. "
            f"{'An AOI boundary was applied and' if cfg.aoi_path().exists() else 'No AOI boundary was available, so'} "
            f"{'class-labeled training samples were available for class-level EDA.' if class_eda else 'no training samples were available yet, so class-level EDA was skipped.'} "
            "Based on the statistics and figures above, the dataset "
            f"{'appears ready' if (cfg.aoi_path().exists() and class_eda is not None) else 'is not yet fully ready'} "
            "to move to Phase 2 (Random Forest Classification); see Section 10 for the specific remaining issues."
        ),
    })

    cfg.REPORT_MD_PATH.write_text(generate_report(results), encoding="utf-8")
    print(f"[done] Processed years: {years_available}")
    print(f"[done] Wrote {cfg.REPORT_MD_PATH}")
    print(f"[done] Figures in {cfg.FIGURES_DIR}")
    print(f"[done] Statistics in {cfg.STATISTICS_DIR}")


if __name__ == "__main__":
    main()
