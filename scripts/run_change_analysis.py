#!/usr/bin/env python3
"""
Chay 4 phan tich cua task tuan 3 va luu ket qua ra JSON + PNG:
  1. Ma tran chuyen doi 2022 -> 2024
  2. Do chinh xac co trong so dien tich
  3. Histogram NDBI 5 moc
  4. Kiem dinh nguong bien dong

Chay:
    python scripts/run_change_analysis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from src.gee import config as gcfg
from src.gee import classify as gcls
from src.gee import change_analysis as ca

OUT_JSON = gcfg.GEE_STATS_DIR / "change_analysis.json"
SCRATCH = Path("/tmp/claude-1000/-home-ngochieu-repo-Xu-ly-anh/"
               "30286c35-2985-4ece-ab8e-23d090f3ecce/scratchpad")

# Dien tich Built-up da bao cao o task 3.8 (sau loc majority + bo sung mau 2018)
BUILTUP_HA = {2018: 1342.0, 2020: 1178.3, 2022: 1026.7, 2024: 2756.8, 2026: 2625.1}
TOTAL_AREA_HA = 10222.1  # AOI 102,22 km2


def save(results):
    """Ghi checkpoint sau moi phan, de loi mang khong lam mat ket qua da tinh."""
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def load_checkpoint() -> dict:
    if OUT_JSON.exists():
        try:
            return json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def retry(fn, what: str, attempts: int = 4):
    """Goi lai vai lan khi GEE/mang loi tam thoi."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"   [retry {i+1}/{attempts}] {what}: {type(e).__name__}: {e}")
    raise last


def main():
    results = load_checkpoint()
    if results:
        print(f"[info] Tiep tuc tu checkpoint: da co {list(results)}")
    print("== Huan luyen mo hinh cuoi cung ==")
    clf, train, test = ca.build_final_model()
    print("   train:", train.size().getInfo(), "| test:", test.size().getInfo())

    # ---- 2. Do chinh xac co trong so dien tich -------------------------
    print("\n== 2. Do chinh xac co trong so dien tich ==")
    ev = retry(lambda: gcls.evaluate(clf, test, gcfg.FEATURE_NAMES_9), "evaluate")
    cm = np.asarray(ev["confusion_matrix"], dtype=float)
    print("   Ma tran nham lan:")
    for row in cm.astype(int):
        print("     ", row.tolist())

    awa = ca.area_weighted_accuracy(cm, ca.AREA_PROPORTIONS_WORLDCOVER)
    print(f"   OA thong thuong      : {100*awa['oa_simple']:.2f}%")
    print(f"   OA co trong so       : {100*awa['oa_weighted']:.2f}%  "
          f"(+/- {100*awa['margin95']:.2f} diem %)")
    print(f"   Khoang tin cay 95%   : {100*awa['ci95'][0]:.2f}% - {100*awa['ci95'][1]:.2f}%")
    for i, name in gcfg.CLASS_MAP.items():
        print(f"     {name:12s} PA có trọng số {100*awa['producer_weighted'][i]:6.2f}% | "
              f"UA {100*awa['user_weighted'][i]:6.2f}%")

    ci_built = ca.class_area_confidence(cm, ca.AREA_PROPORTIONS_WORLDCOVER,
                                        TOTAL_AREA_HA, class_index=3)
    print(f"   Sai so dien tich Built-up: +/- {ci_built['margin95_pct_points']:.2f} diem % "
          f"= +/- {ci_built['margin95_ha']:.1f} ha")

    results["accuracy"] = {"confusion_matrix": cm.astype(int).tolist(),
                           "kappa": ev["kappa"], **awa, "builtup_ci": ci_built}
    save(results)

    # ---- 1. Ma tran chuyen doi ----------------------------------------
    print("\n== 1. Ma tran chuyen doi 2022 -> 2024 ==")
    tm = results.get("transition_2022_2024") or retry(
        lambda: ca.transition_matrix(clf, 2022, 2024), "transition_matrix")
    # JSON bien khoa so thanh chuoi khi doc lai checkpoint -> chuan hoa ve int
    tm["matrix_ha"] = {int(i): {int(j): v for j, v in row.items()}
                       for i, row in tm["matrix_ha"].items()}
    classes = sorted(gcfg.CLASS_MAP)
    print("   Don vi: hec ta. Hang = lop nam 2022, cot = lop nam 2024")
    header = "        " + "".join(f"{gcfg.CLASS_MAP[j][:9]:>11s}" for j in classes)
    print(header)
    for i in classes:
        row = "".join(f"{tm['matrix_ha'][i][j]:11.1f}" for j in classes)
        print(f"   {gcfg.CLASS_MAP[i][:7]:8s}{row}")
    print(f"   Tong: {tm['total_ha']:.1f} ha | Khong doi: {tm['unchanged_ha']:.1f} ha "
          f"| Da chuyen: {tm['changed_ha']:.1f} ha ({tm['changed_pct']:.2f}%)")
    print("   Cac luong chuyen doi lon nhat:")
    for label, ha, pct in ca.transition_rows(tm)[:6]:
        print(f"     {label:28s} {ha:9.1f} ha  ({pct:5.2f}%)")
    results["transition_2022_2024"] = tm
    save(results)

    # ---- 3. Histogram NDBI --------------------------------------------
    print("\n== 3. Histogram NDBI tung moc ==")
    hists = results.get("ndbi_histograms", {})
    for year in gcfg.STUDY_YEARS:
        if str(year) in hists or year in hists:
            print(f"   {year}: da co trong checkpoint, bo qua")
            continue
        h = retry(lambda y=year: ca.ndbi_histogram(y), f"histogram {year}")
        share = retry(lambda y=year: ca.positive_ndbi_share(y), f"positive share {year}")
        h["positive_share_pct"] = share
        hists[year] = h
        results["ndbi_histograms"] = hists
        save(results)
        s = h["stats"]
        print(f"   {year}: mean={s['NDBI_mean']:+.4f} sd={s['NDBI_stdDev']:.4f} "
              f"median={s['NDBI_p50']:+.4f} p95={s['NDBI_p95']:+.4f} | NDBI>0: {share:.2f}%")
    results["ndbi_histograms"] = hists
    save(results)

    # ---- 4. Kiem dinh nguong bien dong --------------------------------
    print("\n== 4. Kiem dinh nguong bien dong ==")
    margin_ha = ci_built["margin95_ha"]
    sig = ca.change_significance(BUILTUP_HA, margin_ha)
    print(f"   Sai so mot uoc luong: +/- {margin_ha:.1f} ha")
    print(f"   Nguong toi thieu de mot bien dong dang tin: {margin_ha*np.sqrt(2):.1f} ha")
    for s in sig:
        verdict = "DANG TIN" if s["significant"] else "trong sai so"
        print(f"   {s['period']}: {s['delta_ha']:+9.1f} ha  "
              f"(gap {s['ratio']:.2f} lan nguong)  -> {verdict}")
    results["change_significance"] = {"margin_single_ha": margin_ha,
                                      "threshold_ha": margin_ha * float(np.sqrt(2)),
                                      "periods": sig,
                                      "builtup_ha": BUILTUP_HA}

    save(results)
    print(f"\n[done] Da luu {OUT_JSON}")


if __name__ == "__main__":
    main()
