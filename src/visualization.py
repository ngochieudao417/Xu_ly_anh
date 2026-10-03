"""
Plotting utilities for the Phase 1 EDA. Every function saves a figure to
outputs/figures/ (title + axis labels + adequate DPI) and closes it, so
notebooks/scripts can call these in a loop without leaking matplotlib
figures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src import config as cfg

sns.set_theme(style="whitegrid")
FIG_DPI = 200


def _save(fig, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_rgb_composite(red: np.ndarray, green: np.ndarray, blue: np.ndarray, out_path: Path, title: str) -> Path:
    """Percentile-stretched true-colour composite (B4-B3-B2)."""

    def stretch(band):
        lo, hi = np.nanpercentile(band, (2, 98))
        if hi <= lo:
            return np.clip(band, 0, 1)
        return np.clip((band - lo) / (hi - lo), 0, 1)

    rgb = np.dstack([stretch(red), stretch(green), stretch(blue)])
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(rgb)
    ax.set_title(title)
    ax.set_xlabel("Column (pixels)")
    ax.set_ylabel("Row (pixels)")
    ax.set_xticks([])
    ax.set_yticks([])
    return _save(fig, out_path)


def plot_band_histograms(df: pd.DataFrame, band_names: list[str], out_path: Path) -> Path:
    present = [b for b in band_names if b in df.columns]
    n = len(present)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows))
    axes = np.atleast_1d(axes).flatten()
    for ax, band in zip(axes, present):
        sns.histplot(df[band].dropna(), bins=60, ax=ax, color="steelblue")
        ax.set_title(f"{band} ({cfg.BAND_DESCRIPTIONS.get(band, '')}) distribution")
        ax.set_xlabel("Reflectance (scaled 0-1)")
        ax.set_ylabel("Pixel count")
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Spectral Band Distributions", y=1.02, fontsize=14)
    return _save(fig, out_path)


def plot_index_histograms(df: pd.DataFrame, index_names: list[str], out_path: Path) -> Path:
    present = [i for i in index_names if i in df.columns]
    fig, axes = plt.subplots(1, len(present), figsize=(5 * len(present), 4))
    axes = np.atleast_1d(axes)
    for ax, idx in zip(axes, present):
        sns.histplot(df[idx].dropna(), bins=60, ax=ax, color="darkorange")
        ax.set_title(f"{idx} distribution")
        ax.set_xlabel(idx)
        ax.set_ylabel("Pixel count")
    fig.suptitle("Spectral Index Distributions", y=1.02, fontsize=14)
    return _save(fig, out_path)


def plot_boxplots(df: pd.DataFrame, feature_names: list[str], out_path: Path, by_year: bool = False) -> Path:
    present = [f for f in feature_names if f in df.columns]
    melted = df.melt(
        id_vars=["year"] if (by_year and "year" in df.columns) else None,
        value_vars=present,
        var_name="feature",
        value_name="value",
    )
    fig, ax = plt.subplots(figsize=(max(8, 1.2 * len(present)), 6))
    if by_year and "year" in melted.columns:
        sns.boxplot(data=melted, x="feature", y="value", hue="year", ax=ax)
    else:
        sns.boxplot(data=melted, x="feature", y="value", ax=ax, color="lightseagreen")
    ax.set_title("Feature Boxplots (bands and spectral indices)")
    ax.set_xlabel("Feature")
    ax.set_ylabel("Value")
    return _save(fig, out_path)


def plot_correlation_heatmap(df: pd.DataFrame, feature_names: list[str], out_path: Path) -> Path:
    present = [f for f in feature_names if f in df.columns]
    corr = df[present].corr()
    fig, ax = plt.subplots(figsize=(1 + len(present), 1 + len(present)))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, square=True, ax=ax)
    ax.set_title("Correlation Matrix: Spectral Bands and Indices")
    return _save(fig, out_path)


def plot_spatial_index_map(
    index_array: np.ndarray,
    out_path: Path,
    title: str,
    cmap: str = "RdYlGn",
    vmin: float = -1,
    vmax: float = 1,
) -> Path:
    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(index_array, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Index value")
    return _save(fig, out_path)


def plot_temporal_trend(temporal_df: pd.DataFrame, out_path: Path) -> Path:
    """temporal_df must have columns: year, mean_NDVI, mean_NDBI, mean_NDWI."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for col, marker in zip(["mean_NDVI", "mean_NDBI", "mean_NDWI"], ["o", "s", "^"]):
        if col in temporal_df.columns:
            ax.plot(temporal_df["year"], temporal_df[col], marker=marker, label=col.replace("mean_", "Mean "))
    ax.set_title("Preliminary Temporal Trend of Spectral Indices (exploratory only)")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean index value")
    ax.legend()
    return _save(fig, out_path)


def plot_class_distribution(df: pd.DataFrame, out_path: Path, class_col: str = "class_name") -> Path:
    fig, ax = plt.subplots(figsize=(6, 5))
    order = df[class_col].value_counts().index
    sns.countplot(data=df, x=class_col, order=order, ax=ax, color="cornflowerblue")
    ax.set_title("Training Sample Class Distribution")
    ax.set_xlabel("Land-cover class")
    ax.set_ylabel("Sample count")
    return _save(fig, out_path)


def plot_feature_by_class(df: pd.DataFrame, feature: str, out_path: Path, class_col: str = "class_name") -> Path:
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.boxplot(data=df, x=class_col, y=feature, ax=ax, color="mediumpurple")
    ax.set_title(f"{feature} by Land-cover Class")
    ax.set_xlabel("Land-cover class")
    ax.set_ylabel(feature)
    return _save(fig, out_path)
