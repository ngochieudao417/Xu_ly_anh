#!/usr/bin/env python3
"""
Ve histogram NDBI cua 5 moc thoi gian tu ket qua da luu trong
outputs/statistics/gee/change_analysis.json.

Tao 3 hinh:
  - ndbi_hist_overlay.png : 5 duong phan bo chong len nhau
  - ndbi_hist_grid.png    : 5 histogram rieng, xep luoi
  - ndbi_shift_summary.png: trung vi NDBI va ty le NDBI > 0 theo nam

Chay:
    python scripts/plot_ndbi_histograms.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.gee import config as gcfg

JSON_PATH = gcfg.GEE_STATS_DIR / "change_analysis.json"
FIG_DIR = gcfg.GEE_FIGURES_DIR

# Mau chuyen dan tu xanh (nam dau) sang do (nam cuoi) de thay huong dich chuyen
YEAR_COLORS = {
    2018: "#2E8B57", 2020: "#66A61E", 2022: "#D9A404",
    2024: "#E8590C", 2026: "#D7301F",
}


def load():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return data["ndbi_histograms"]


def normalize(counts):
    counts = np.asarray(counts, dtype=float)
    total = counts.sum()
    return counts / total * 100 if total else counts


def plot_overlay(hists, out_path):
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for year in gcfg.STUDY_YEARS:
        h = hists.get(str(year)) or hists.get(year)
        if not h:
            continue
        x = np.asarray(h["bin_centers"], dtype=float)
        y = normalize(h["counts"])
        ax.plot(x, y, label=str(year), color=YEAR_COLORS[year], linewidth=2.2)
    ax.axvline(0, color="black", linestyle="--", linewidth=1.2)
    ax.annotate("NDBI = 0\n(ranh giới thiên về bề mặt xây dựng)",
                xy=(0, ax.get_ylim()[1] * 0.92), xytext=(0.06, ax.get_ylim()[1] * 0.92),
                fontsize=9, va="top")
    ax.set_xlabel("Giá trị NDBI")
    ax.set_ylabel("Tỷ lệ diện tích (%)")
    ax.set_title("Phân bố NDBI toàn vùng nghiên cứu qua 5 mốc thời gian")
    ax.legend(title="Mốc thời gian")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  ->", out_path)


def plot_grid(hists, out_path):
    years = [y for y in gcfg.STUDY_YEARS if (hists.get(str(y)) or hists.get(y))]
    fig, axes = plt.subplots(1, len(years), figsize=(4.0 * len(years), 3.6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, year in zip(axes, years):
        h = hists.get(str(year)) or hists.get(year)
        x = np.asarray(h["bin_centers"], dtype=float)
        y = normalize(h["counts"])
        ax.fill_between(x, y, color=YEAR_COLORS[year], alpha=0.75)
        ax.axvline(0, color="black", linestyle="--", linewidth=1)
        med = h["stats"]["NDBI_p50"]
        ax.axvline(med, color="navy", linewidth=1.4)
        ax.set_title(f"{year}\ntrung vị = {med:+.3f}", fontsize=11)
        ax.set_xlabel("NDBI")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Tỷ lệ diện tích (%)")
    fig.suptitle("Phân bố NDBI từng mốc — đường xanh đậm là trung vị", y=1.04, fontsize=13)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  ->", out_path)


def plot_summary(hists, out_path):
    years, medians, means, shares = [], [], [], []
    for year in gcfg.STUDY_YEARS:
        h = hists.get(str(year)) or hists.get(year)
        if not h:
            continue
        years.append(year)
        medians.append(h["stats"]["NDBI_p50"])
        means.append(h["stats"]["NDBI_mean"])
        shares.append(h["positive_share_pct"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    ax1.plot(years, medians, marker="o", color="#D7301F", linewidth=2.2, label="Trung vị")
    ax1.plot(years, means, marker="s", color="#1E90FF", linewidth=2.0,
             linestyle="--", label="Trung bình")
    ax1.axhline(0, color="black", linestyle=":", linewidth=1)
    ax1.set_xticks(years)
    ax1.set_xlabel("Mốc thời gian")
    ax1.set_ylabel("Giá trị NDBI")
    ax1.set_title("Dịch chuyển trung tâm phân bố NDBI")
    ax1.legend()
    ax1.grid(alpha=0.3)

    bars = ax2.bar([str(y) for y in years], shares,
                   color=[YEAR_COLORS[y] for y in years])
    for b, v in zip(bars, shares):
        ax2.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}%",
                 ha="center", fontsize=10)
    ax2.set_ylabel("Tỷ lệ diện tích có NDBI > 0 (%)")
    ax2.set_xlabel("Mốc thời gian")
    ax2.set_title("Tỷ lệ diện tích thiên về bề mặt xây dựng")
    ax2.grid(alpha=0.3, axis="y")
    ax2.set_ylim(0, max(shares) * 1.2)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  ->", out_path)


def main():
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"Chua co {JSON_PATH}. Chay scripts/run_change_analysis.py truoc.")
    hists = load()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("Ve histogram NDBI:")
    plot_overlay(hists, FIG_DIR / "ndbi_hist_overlay.png")
    plot_grid(hists, FIG_DIR / "ndbi_hist_grid.png")
    plot_summary(hists, FIG_DIR / "ndbi_shift_summary.png")
    print("[done]")


if __name__ == "__main__":
    main()
