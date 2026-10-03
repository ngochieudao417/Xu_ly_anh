"""
Phan tich bien dong va kiem dinh do tin cay (task tuan 3):

1. Ma tran chuyen doi from-to giua hai moc thoi gian (don vi hec ta)
2. Do chinh xac co trong so dien tich (Olofsson va cong su, 2014)
3. Histogram NDBI tung moc, de chung minh phan bo pho dich chuyen theo thoi gian
4. Kiem dinh: nguong bien dong nao nam trong sai so mo hinh, nguong nao dang tin

Dung chung mot mo hinh cuoi cung voi cac bao cao truoc (phuong an A, 9 dac
trung, co bo sung 80 mau tay cho moc 2018) de moi con so nhat quan voi nhau.
"""

from __future__ import annotations

import ee
import numpy as np

from src.gee import config as gcfg
from src.gee import composite as gcomp
from src.gee import sampling as gsamp
from src.gee import classify as gcls
from src.gee import apply_model as gapply

# Vung "ve tay" da xac nhan bang mat la dat nong nghiep, dung de bo sung
# mau rieng cho moc 2018 (xem bao cao task 3.9).
HAND_REGION_2018 = [107.0211, 10.7662, 107.0623, 10.8050]
HAND_N_POINTS = 80

# Ty le dien tich thuc te bon lop trong AOI, lay tu ESA WorldCover.
# Thu tu khop ma lop: 0 Water, 1 Vegetation, 2 Bare Soil, 3 Built-up.
AREA_PROPORTIONS_WORLDCOVER = [0.0010, 0.9395, 0.0179, 0.0417]

PIXEL_AREA_HA = 0.01  # 10 m x 10 m = 100 m2 = 0,01 ha


# ---------------------------------------------------------------------------
# Mo hinh cuoi cung (dung chung cho moi phan tich)
# ---------------------------------------------------------------------------
def build_final_model():
    """
    Dung lai dung cong thuc mo hinh cuoi cung da bao cao:
    mau da lam sach + 80 mau tay trich tu composite 2018.

    Tra ve (classifier, train_fc, test_fc).
    """
    gcfg.init_ee()
    combined, _ = gsamp.build_labeled_samples_cleaned()
    train, test = gsamp.train_test_split(combined)

    hand_region = ee.Geometry.Rectangle(HAND_REGION_2018)
    composite_2018 = gcomp.build_composite(2018)
    hand_pts = composite_2018.sample(
        region=hand_region, scale=10, numPixels=HAND_N_POINTS,
        seed=gcfg.SAMPLE_SEED, geometries=True, dropNulls=True,
    ).map(lambda f: f.set(gcfg.CLASS_COL, 1)
                     .set("reference_year", 2018)
                     .set("source", "hand_2018"))

    train_aug = train.merge(hand_pts)
    clf = gcls.train_rf(train_aug, gcfg.FEATURE_NAMES_9)
    return clf, train_aug, test


def classified_filtered(clf, year: int) -> "ee.Image":
    """Anh phan loai da loc majority 3x3 (giong quy trinh dung o bao cao truoc)."""
    classified = gapply.classify_year(clf, year, gcfg.FEATURE_NAMES_9)
    return classified.reduceNeighborhood(
        reducer=ee.Reducer.mode(), kernel=ee.Kernel.square(1)
    ).rename("class")


# ---------------------------------------------------------------------------
# 1. Ma tran chuyen doi from-to
# ---------------------------------------------------------------------------
def transition_matrix(clf, year_from: int, year_to: int) -> dict:
    """
    Ma tran chuyen doi giua hai moc, don vi hec ta.

    Ma hoa cap lop: lopTruoc * 10 + lopSau. Vi du ma 13 nghia la mot diem
    anh nam 'year_from' thuoc lop 1 (Vegetation) da chuyen sang lop 3
    (Built-up) o nam 'year_to'.

    Tra ve dict gom ma tran 4x4 (ha), tong chuyen doi, va cac dong ke chi tiet.
    """
    gcfg.init_ee()
    aoi = gcfg.get_aoi()

    img_from = classified_filtered(clf, year_from)
    img_to = classified_filtered(clf, year_to)
    cap_lop = img_from.multiply(10).add(img_to).rename("cap")

    grouped = (
        ee.Image.pixelArea().divide(10000)
        .addBands(cap_lop)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="cap"),
            geometry=aoi, scale=gcfg.__dict__.get("SCALE", 10),
            maxPixels=int(1e13),
        )
        .getInfo()
    )

    classes = sorted(gcfg.CLASS_MAP)
    matrix = {i: {j: 0.0 for j in classes} for i in classes}
    for item in grouped.get("groups", []):
        code = int(item["cap"])
        area_ha = float(item["sum"])
        i, j = divmod(code, 10)
        if i in matrix and j in matrix[i]:
            matrix[i][j] = area_ha

    total = sum(matrix[i][j] for i in classes for j in classes)
    unchanged = sum(matrix[i][i] for i in classes)
    changed = total - unchanged

    return {
        "year_from": year_from,
        "year_to": year_to,
        "matrix_ha": matrix,
        "total_ha": total,
        "unchanged_ha": unchanged,
        "changed_ha": changed,
        "changed_pct": 100 * changed / total if total else 0.0,
    }


def transition_rows(result: dict, min_ha: float = 0.0) -> list[tuple[str, float, float]]:
    """Liet ke cac luong chuyen doi (tru duong cheo), sap theo dien tich giam dan."""
    classes = sorted(gcfg.CLASS_MAP)
    rows = []
    for i in classes:
        for j in classes:
            if i == j:
                continue
            ha = result["matrix_ha"][i][j]
            if ha >= min_ha:
                label = f"{gcfg.CLASS_MAP[i]} → {gcfg.CLASS_MAP[j]}"
                rows.append((label, ha, 100 * ha / result["total_ha"]))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 2. Do chinh xac co trong so dien tich
# ---------------------------------------------------------------------------
def area_weighted_accuracy(cm: np.ndarray, area_proportions: list[float]) -> dict:
    """
    Tinh do chinh xac co trong so dien tich theo Olofsson va cong su (2014).

    cm: ma tran nham lan, hang = nhan tham chieu, cot = nhan mo hinh doan.
    area_proportions: ty le dien tich thuc te cua tung lop, cung thu tu hang.

    Y tuong: tap kiem tra chia deu moi lop 300 diem, trong khi ngoai thuc te
    ty le rat lech (Vegetation ~94%, Water ~0,1%). Neu tinh OA thong thuong
    thi lop hiem bi tinh trong so qua lon. Phep tinh nay chuan hoa tung hang
    ve xac suat roi nhan lai voi ty le dien tich that.
    """
    cm = np.asarray(cm, dtype=float)
    n = cm.shape[0]
    W = np.asarray(area_proportions, dtype=float)
    if W.sum() > 0:
        W = W / W.sum()

    row_totals = cm.sum(axis=1)
    # p(j|i): xac suat mo hinh doan lop j khi thuc te la lop i
    cond = np.divide(cm, row_totals[:, None], out=np.zeros_like(cm), where=row_totals[:, None] > 0)
    # p_ij: ty le dien tich uoc luong
    p = cond * W[:, None]

    oa_weighted = float(np.trace(p))
    oa_simple = float(cm.trace() / cm.sum()) if cm.sum() else float("nan")

    # Phuong sai cua OA co trong so (Olofsson 2014, cong thuc 5)
    var = 0.0
    for i in range(n):
        n_i = row_totals[i]
        if n_i > 1:
            p_ii = cond[i, i]
            var += (W[i] ** 2) * p_ii * (1 - p_ii) / (n_i - 1)
    se = float(np.sqrt(var))

    # Producer accuracy co trong so cho tung lop
    col_weighted = p.sum(axis=0)
    pa_weighted = np.divide(np.diag(p), W, out=np.zeros(n), where=W > 0)
    ua_weighted = np.divide(np.diag(p), col_weighted, out=np.zeros(n), where=col_weighted > 0)

    return {
        "oa_simple": oa_simple,
        "oa_weighted": oa_weighted,
        "se": se,
        "ci95": (oa_weighted - 1.96 * se, oa_weighted + 1.96 * se),
        "margin95": 1.96 * se,
        "producer_weighted": pa_weighted.tolist(),
        "user_weighted": ua_weighted.tolist(),
        "estimated_area_proportion": col_weighted.tolist(),
        "weights_used": W.tolist(),
        "n_per_class": row_totals.tolist(),
    }


def class_area_confidence(cm: np.ndarray, area_proportions: list[float],
                          total_area_ha: float, class_index: int = 3) -> dict:
    """
    Khoang tin cay 95% cho dien tich uoc luong cua mot lop (mac dinh lop 3 =
    Built-up), theo uoc luong phan tang cua Olofsson va cong su (2014).

    Dung de tra loi cau hoi: chenh lech dien tich bao nhieu thi moi vuot ra
    ngoai sai so cua mo hinh.
    """
    cm = np.asarray(cm, dtype=float)
    n = cm.shape[0]
    W = np.asarray(area_proportions, dtype=float)
    if W.sum() > 0:
        W = W / W.sum()
    row_totals = cm.sum(axis=1)

    p_hat = 0.0
    var = 0.0
    for i in range(n):
        n_i = row_totals[i]
        if n_i <= 1:
            continue
        share = cm[i, class_index] / n_i
        p_hat += W[i] * share
        var += (W[i] ** 2) * share * (1 - share) / (n_i - 1)

    se = float(np.sqrt(var))
    margin = 1.96 * se
    return {
        "class_index": class_index,
        "class_name": gcfg.CLASS_MAP[class_index],
        "p_hat": float(p_hat),
        "se": se,
        "margin95_pct_points": 100 * margin,
        "margin95_ha": margin * total_area_ha,
        "ci95_pct": (100 * (p_hat - margin), 100 * (p_hat + margin)),
        "ci95_ha": ((p_hat - margin) * total_area_ha, (p_hat + margin) * total_area_ha),
    }


# ---------------------------------------------------------------------------
# 3. Histogram NDBI theo tung moc
# ---------------------------------------------------------------------------
def ndbi_histogram(year: int, n_bins: int = 60, vmin: float = -0.6, vmax: float = 0.6) -> dict:
    """
    Lay histogram NDBI cua mot moc thoi gian tren toan AOI, cung voi cac
    thong ke mo ta (trung binh, do lech chuan, phan vi).
    """
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    ndbi = gcomp.build_composite(year).select("NDBI")

    hist = ndbi.reduceRegion(
        reducer=ee.Reducer.fixedHistogram(vmin, vmax, n_bins),
        geometry=aoi, scale=10, maxPixels=int(1e13), bestEffort=True,
    ).getInfo().get("NDBI")

    stats = ndbi.reduceRegion(
        reducer=(ee.Reducer.mean()
                 .combine(ee.Reducer.stdDev(), sharedInputs=True)
                 .combine(ee.Reducer.percentile([5, 25, 50, 75, 95]), sharedInputs=True)),
        geometry=aoi, scale=10, maxPixels=int(1e13), bestEffort=True,
    ).getInfo()

    arr = np.asarray(hist, dtype=float)  # (n_bins, 2): [gia tri bin, so pixel]
    return {
        "year": year,
        "bin_centers": arr[:, 0].tolist(),
        "counts": arr[:, 1].tolist(),
        "stats": stats,
    }


def positive_ndbi_share(year: int) -> float:
    """Ty le phan tram dien tich co NDBI > 0 (thien ve be mat xay dung)."""
    gcfg.init_ee()
    aoi = gcfg.get_aoi()
    ndbi = gcomp.build_composite(year).select("NDBI")
    share = ndbi.gt(0).reduceRegion(
        reducer=ee.Reducer.mean(), geometry=aoi, scale=10,
        maxPixels=int(1e13), bestEffort=True,
    ).getInfo().get("NDBI")
    return 100 * float(share) if share is not None else float("nan")


# ---------------------------------------------------------------------------
# 4. Kiem dinh nguong bien dong
# ---------------------------------------------------------------------------
def change_significance(area_by_year: dict[int, float], margin_ha: float) -> list[dict]:
    """
    Voi tung cap moc lien tiep, so sanh do lon bien dong voi sai so cua mo hinh.

    Sai so cua hieu hai uoc luong doc lap lay theo cong thuc lan truyen sai so:
    margin_diff = margin * can bac hai cua 2.
    """
    years = sorted(area_by_year)
    margin_diff = margin_ha * np.sqrt(2)
    out = []
    for a, b in zip(years, years[1:]):
        delta = area_by_year[b] - area_by_year[a]
        out.append({
            "period": f"{a} → {b}",
            "delta_ha": float(delta),
            "margin_diff_ha": float(margin_diff),
            "ratio": float(abs(delta) / margin_diff) if margin_diff else float("inf"),
            "significant": bool(abs(delta) > margin_diff),
        })
    return out
