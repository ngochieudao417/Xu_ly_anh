"""
End-to-end smoke test for the Phase 1 pipeline.

Real Sentinel-2 imagery is not part of this repository (see data/raw/README.md),
so this test builds a small synthetic 6-band raster + AOI + training points in a
pytest tmp_path, points src.config at that temporary location, and exercises
validation -> preprocessing -> features -> visualization end to end. It exists to
give confidence that the pipeline is correct *before* real imagery is available,
not to validate any particular real-world result.

Run with:  pytest tests/test_pipeline_smoke.py -v
"""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
import geopandas as gpd
from shapely.geometry import Point, box

from src import config as cfg
from src import features, preprocessing, validation, visualization


@pytest.fixture
def synthetic_project(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    monkeypatch.setattr(cfg, "DATA_RAW_DIR", raw_dir)
    monkeypatch.setattr(cfg, "DATA_PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(cfg, "DATA_SAMPLES_DIR", tmp_path / "samples")
    monkeypatch.setattr(cfg, "FIGURES_DIR", tmp_path / "figures")
    for d in (cfg.DATA_PROCESSED_DIR, cfg.DATA_SAMPLES_DIR, cfg.FIGURES_DIR):
        d.mkdir()

    year = 2099
    rng = np.random.default_rng(0)
    height = width = 120
    transform = from_origin(600000, 1200000, 10, 10)
    data = (rng.random((6, height, width)) * 9000 + 100).astype(np.uint16)
    data[:, 0:5, 0:5] = 0  # NoData block
    with rasterio.open(
        cfg.raw_image_path(year), "w", driver="GTiff", height=height, width=width,
        count=6, dtype=data.dtype, crs="EPSG:32648", transform=transform, nodata=0,
    ) as dst:
        dst.write(data)

    aoi_geom = box(600000 + 200, 1200000 - 1000, 600000 + 1000, 1200000 - 200)
    gpd.GeoDataFrame({"id": [1]}, geometry=[aoi_geom], crs="EPSG:32648").to_file(
        cfg.aoi_path(), driver="GeoJSON"
    )

    points = gpd.GeoDataFrame(
        {"class": [0, 1, 2, 3]},
        geometry=[Point(600400 + i * 100, 1199500 - i * 50) for i in range(4)],
        crs="EPSG:32648",
    )
    points.to_file(cfg.DATA_SAMPLES_DIR / "training_samples.geojson", driver="GeoJSON")

    return year


def test_validation_reads_metadata_and_stats(synthetic_project):
    year = synthetic_project
    meta = validation.get_raster_metadata(cfg.raw_image_path(year))
    assert meta["band_count"] == len(cfg.BAND_NAMES)
    assert meta["crs"] == "EPSG:32648"

    stats = validation.compute_band_statistics(cfg.raw_image_path(year), cfg.BAND_NAMES)
    assert set(stats.keys()) == set(cfg.BAND_NAMES)
    for s in stats.values():
        assert s["nodata_count"] == 25  # the 5x5 NoData block injected above
        assert 0 <= s["min"] <= s["max"]


def test_sampling_respects_aoi_and_is_reproducible(synthetic_project):
    year = synthetic_project
    samples_a, counts_a = preprocessing.sample_valid_pixels(year, n_samples=1000)
    samples_b, counts_b = preprocessing.sample_valid_pixels(year, n_samples=1000)

    assert counts_a["outside_aoi"] > 0  # AOI is smaller than the full raster
    assert counts_a["sampled"] == counts_b["sampled"]
    np.testing.assert_array_equal(samples_a["B2"], samples_b["B2"])  # seeded -> reproducible


def test_indices_are_bounded_and_handle_zero_denominator():
    nir = np.array([0.0, 0.5, 0.3])
    red = np.array([0.0, 0.1, 0.3])
    ndvi = features.compute_ndvi(nir, red)
    assert np.isnan(ndvi[0])  # 0/0 must not silently become 0 or inf
    assert -1 <= ndvi[1] <= 1


def test_feature_dataframe_and_figures_are_generated(synthetic_project):
    year = synthetic_project
    samples, _ = preprocessing.sample_valid_pixels(year, n_samples=2000)
    df = features.build_feature_dataframe(year, samples)
    assert set(cfg.BAND_NAMES + cfg.INDEX_NAMES).issubset(df.columns)
    assert len(df) > 0

    fig_path = visualization.plot_band_histograms(df, cfg.BAND_NAMES, cfg.FIGURES_DIR / "bands.png")
    assert fig_path.exists()

    fig_path = visualization.plot_correlation_heatmap(df, cfg.FEATURE_NAMES, cfg.FIGURES_DIR / "corr.png")
    assert fig_path.exists()


def test_aoi_clip_writes_smaller_raster(synthetic_project):
    year = synthetic_project
    out_path = preprocessing.clip_to_aoi_and_save(year)
    assert out_path is not None and out_path.exists()
    with rasterio.open(cfg.raw_image_path(year)) as full, rasterio.open(out_path) as clipped:
        assert clipped.width * clipped.height < full.width * full.height


def test_extract_features_at_points(synthetic_project):
    year = synthetic_project
    gdf = gpd.read_file(cfg.DATA_SAMPLES_DIR / "training_samples.geojson")
    df = preprocessing.extract_features_at_points(year, gdf, cfg.BAND_NAMES)
    assert len(df) == len(gdf)
    assert set(cfg.BAND_NAMES).issubset(df.columns)
    assert (df[cfg.BAND_NAMES] >= 0).all().all()
