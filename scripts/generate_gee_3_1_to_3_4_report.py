#!/usr/bin/env python3
"""
Bao cao task 3.1-3.4: chuyen pipeline sang GEE, xay composite + 9 dac trung,
stratified sampling tu WorldCover, QC truc quan + loc mau Water nham.

Chay:
    python scripts/generate_gee_3_1_to_3_4_report.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches

from src.gee import config as gcfg

BLACK = RGBColor(0, 0, 0)
FONT_NAME = "Times New Roman"
OUT_PATH = gcfg.PROJECT_ROOT / "reports" / "Phase2_Task_3.1_den_3.4_GEE.docx"
FIG_DIR = gcfg.GEE_FIGURES_DIR


def set_run_font(run, size=13, bold=False, italic=False):
    run.font.name = FONT_NAME
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    run.bold = bold
    run.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), FONT_NAME)


def add_heading(doc, text, level=1):
    h = doc.add_heading("", level=level)
    run = h.add_run(text)
    size = {1: 16, 2: 14, 3: 13}.get(level, 13)
    set_run_font(run, size=size, bold=True)
    return h


def add_para(doc, text, size=13, bold=False, italic=False, align=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic)
    return p


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        run = table.rows[0].cells[i].paragraphs[0].add_run(h)
        set_run_font(run, size=12, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            run = cells[i].paragraphs[0].add_run(str(val))
            set_run_font(run, size=12)
    doc.add_paragraph()
    return table


def add_figure(doc, path: Path, caption: str, width_in=6.0):
    if not path.exists():
        add_para(doc, f"[Khong tim thay hinh: {path.name}]", italic=True)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width_in))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(caption)
    set_run_font(run, size=11, italic=True)
    doc.add_paragraph()


def main():
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = FONT_NAME
    normal.font.size = Pt(13)
    normal.font.color.rgb = BLACK

    add_para(
        doc,
        "BÁO CÁO TIẾN ĐỘ PHASE 2 — TASK 3.1 ĐẾN 3.4\n"
        "CHUYỂN PIPELINE SANG GOOGLE EARTH ENGINE, XÂY DỰNG BỘ ĐẶC TRƯNG\n"
        "VÀ LẤY MẪU HUẤN LUYỆN TỪ ESA WORLDCOVER",
        size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    add_para(doc, f"Ngày lập báo cáo: {date.today().strftime('%d/%m/%Y')}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    # 1. Giới thiệu
    add_heading(doc, "1. Giới thiệu", 1)
    add_para(
        doc,
        "Báo cáo này ghi lại 4 task đầu tiên của giai đoạn chuyển sang phân loại Random Forest "
        "(Phase 2) cho dự án khu vực Sân bay Long Thành: chuyển toàn bộ pipeline lấy ảnh từ "
        "AWS/STAC sang Google Earth Engine (GEE), xây dựng bộ 9 đặc trưng phổ, lấy mẫu huấn "
        "luyện từ lớp phủ ESA WorldCover, và rà soát bằng mắt chất lượng nhãn trước khi đưa vào "
        "huấn luyện mô hình."
    )
    add_para(
        doc,
        "AOI (vùng nghiên cứu) trong giai đoạn này dùng đúng polygon do nhóm chốt, thu hẹp và "
        "chính xác hơn AOI hình chữ nhật lớn dùng ở Phase 1, tâm là vị trí sân bay "
        "(107.04111°E, 10.78444°N)."
    )
    add_figure(doc, FIG_DIR / "aoi_rgb_2022.png", "Hình 1. Ảnh RGB tổ hợp (composite mùa khô 2022) toàn bộ AOI chuẩn, lấy qua GEE.")

    # 2. Task 3.1
    add_heading(doc, "2. Task 3.1 — Chuyển pipeline sang GEE", 1)
    add_para(
        doc,
        "Thay vì tải từng ảnh Sentinel-2 đơn lẻ qua AWS/STAC như Phase 1, pipeline mới dùng "
        "bộ sưu tập ảnh Sentinel-2 L2A trên GEE (COPERNICUS/S2_SR_HARMONIZED), lọc theo AOI và "
        "khung thời gian mùa khô (tháng 12 năm trước đến tháng 4 năm sau, ít mây nhất trong "
        "năm ở Nam Bộ), loại các cảnh có mây toàn cảnh trên 60%, sau đó che mây từng pixel bằng "
        "lớp phân loại cảnh SCL (mã 3, 8, 9, 10 = bóng mây, mây, mây mỏng, cirrus mỏng), rồi lấy "
        "giá trị trung vị (median) của các ảnh còn lại làm ảnh đại diện cho từng năm."
    )
    rows = [
        ["2018", "2017-12-01 đến 2018-04-30", "3"],
        ["2020", "2019-12-01 đến 2020-04-30", "52"],
        ["2022", "2021-12-01 đến 2022-04-30", "45"],
        ["2024", "2023-12-01 đến 2024-04-30", "51"],
        ["2026", "2025-12-01 đến 2026-04-30", "46"],
    ]
    add_table(doc, ["Năm", "Khung thời gian mùa khô", "Số ảnh dùng để composite"], rows)
    add_para(
        doc,
        "Đáng chú ý: năm 2018 chỉ có 3 ảnh trong khung mùa khô, ít hơn hẳn các năm khác "
        "(45-52 ảnh), vì Sentinel-2 mới bắt đầu có dữ liệu L2A ổn định cho khu vực này từ cuối "
        "2018. Composite năm 2018 vì vậy kém mượt hơn, cần lưu ý khi phân tích kết quả năm này "
        "(liên quan đến task 3.9)."
    )

    # 3. Task 3.2
    add_heading(doc, "3. Task 3.2 — Bộ 9 đặc trưng", 1)
    add_para(
        doc,
        "Từ composite 6 band gốc (B2, B3, B4, B8, B11, B12, đã quy về phản xạ 0-1), tính thêm "
        "3 chỉ số NDVI, NDBI, NDWI theo đúng công thức chuẩn, tạo thành ảnh 9 band dùng cho toàn "
        "bộ các bước sau. Kiểm tra nhanh trên composite năm 2022:"
    )
    rows = [
        ["B2", "0.059"], ["B3", "0.082"], ["B4", "0.080"], ["B8", "0.285"],
        ["B11", "0.254"], ["B12", "0.161"],
        ["NDVI", "0.571"], ["NDBI", "-0.061"], ["NDWI", "-0.556"],
    ]
    add_table(doc, ["Band/Chỉ số", "Giá trị trung bình toàn AOI"], rows)
    add_para(
        doc,
        "So với ảnh nền 2018 ở báo cáo trước (NDBI trung bình mẫu -0.132), NDBI trung bình toàn "
        "AOI năm 2022 là -0.061, tức đỡ âm hơn — phù hợp với việc khu vực đang xây dựng nhiều "
        "hơn theo thời gian. Đây mới là quan sát sơ bộ, chưa phải kết luận chính thức vì hai con "
        "số tính trên phạm vi khác nhau (mẫu điểm vs toàn AOI)."
    )

    # 4. Task 3.3
    add_heading(doc, "4. Task 3.3 — Lấy mẫu từ WorldCover (stratified sampling)", 1)
    add_para(
        doc,
        "Nhãn lớp phủ lấy từ ESA WorldCover v200 (bản đồ 10m, dữ liệu nền năm 2021), remap từ "
        "11 lớp gốc của WorldCover về 4 lớp của dự án theo bảng sau:"
    )
    rows = [
        ["10 - Tree cover, 20 - Shrubland, 30 - Grassland, 40 - Cropland", "1 - Vegetation"],
        ["50 - Built-up", "3 - Built-up"],
        ["60 - Bare/sparse vegetation", "2 - Bare Soil"],
        ["80 - Permanent water, 90 - Herbaceous wetland, 95 - Mangroves", "0 - Water"],
    ]
    add_table(doc, ["Lớp WorldCover gốc", "Lớp của dự án"], rows)
    add_para(
        doc,
        "Trước khi lấy mẫu, đếm thử số pixel từng lớp trong AOI để kiểm tra tính khả thi của "
        "300 điểm/lớp:"
    )
    rows = [
        ["Water", "1.002", "0.10%"],
        ["Vegetation", "979.874", "93.95%"],
        ["Bare Soil", "18.659", "1.79%"],
        ["Built-up", "43.464", "4.17%"],
    ]
    add_table(doc, ["Lớp", "Số pixel trong AOI", "Tỷ lệ"], rows)
    add_para(
        doc,
        "Lớp Water chỉ chiếm 0.10% AOI (1.002 pixel) — vẫn đủ để lấy 300 điểm nhưng quần thể "
        "rất nhỏ, các điểm sẽ tập trung ở rất ít vị trí thực tế. Đây là điểm cần lưu ý, dẫn tới "
        "phát hiện ở task 3.4 bên dưới."
    )
    add_para(
        doc,
        f"Ảnh dùng để trích đặc trưng tại các điểm mẫu là composite năm "
        f"{gcfg.REFERENCE_YEAR_FOR_SAMPLING} (gần nhất với dữ liệu nền của WorldCover v200 "
        f"~2021). Lấy stratified sampling 300 điểm/lớp, seed=42 (cố định để tái lập được), sau "
        f"đó chia 70/30 train/test."
    )

    # 5. Task 3.4
    add_heading(doc, "5. Task 3.4 — Rà mẫu bằng mắt", 1)
    add_para(
        doc,
        "Thay vì bật nền vệ tinh trong GEE Code Editor để xem thủ công, báo cáo này export ảnh "
        "chip RGB thật (300x300m quanh mỗi điểm, từ composite năm tham chiếu) và xem trực tiếp "
        "20 điểm ngẫu nhiên mỗi lớp (seed=42), có khoanh đỏ vị trí điểm mẫu."
    )
    findings = [
        ("Water", "6/20 (30%)", "Nhiều điểm rơi thẳng vào giao lộ/khu đô thị, không phải nước. Nghi là đường/mái nhà tối màu bị WorldCover gán nhầm \"nước\", hoặc khu vực đã chuyển từ ao/đất ngập nước (lúc WorldCover chụp ~2021) sang xây dựng (composite 2022)."),
        ("Vegetation", "~2/20 (10%)", "Vài điểm dính cụm nhà nhỏ giữa đồng ruộng; phần lớn còn lại hợp lý kể cả ruộng khô trơ đất (vẫn là cropland hợp lệ)."),
        ("Bare Soil", "không sai rõ, nhưng ranh giới mờ", "Đa số là công trường san lấp sân bay (đất trống + đường mới trải), một số điểm nằm ngay trên đường nhựa — ranh giới giữa \"đất trống\" và \"đã xây\" không rõ ràng tại các khu đang thi công."),
        ("Built-up", "~3/20 (15%)", "Vài điểm rơi vào ruộng/đất trống không thấy công trình nào."),
    ]
    add_table(doc, ["Lớp", "Tỷ lệ nghi nhầm (quan sát bằng mắt)", "Ghi chú"], [[a, b, c] for a, b, c in findings])

    add_figure(doc, FIG_DIR / "qc_visual_water.png", "Hình 2. QC trực quan 20 điểm lớp Water — các điểm #6-11 rơi vào khu đô thị, không phải nước.")
    add_figure(doc, FIG_DIR / "qc_visual_vegetation.png", "Hình 3. QC trực quan 20 điểm lớp Vegetation.")
    add_figure(doc, FIG_DIR / "qc_visual_bare_soil.png", "Hình 4. QC trực quan 20 điểm lớp Bare Soil — phần lớn là công trường san lấp sân bay.")
    add_figure(doc, FIG_DIR / "qc_visual_built-up.png", "Hình 5. QC trực quan 20 điểm lớp Built-up.")

    add_heading(doc, "5.1. Xử lý: lọc mẫu Water bằng ngưỡng NDWI", 2)
    add_para(
        doc,
        "Vì lớp Water có tỷ lệ nhầm cao nhất (~30%), tiến hành lọc lại: lấy gần hết quần thể "
        "điểm Water có thể sample được trong AOI (950/1.002 pixel), loại các điểm có NDWI <= 0 "
        "(nước thật theo công thức NDWI thường có giá trị dương), rồi chọn ngẫu nhiên "
        "(seed=42) 300 điểm trong số các điểm còn lại."
    )
    rows = [
        ["Số điểm Water lấy thử (candidates)", "950"],
        ["Số điểm còn lại sau lọc NDWI > 0", "640 (67.4%)"],
        ["Số điểm bị loại", "310 (32.6%)"],
        ["Số điểm Water dùng để train (sau lọc, lấy mẫu lại)", "300"],
    ]
    add_table(doc, ["Chỉ số", "Giá trị"], rows)
    add_para(
        doc,
        "Tỷ lệ loại bỏ tính bằng ngưỡng NDWI (32.6%) khá khớp với tỷ lệ nghi nhầm quan sát bằng "
        "mắt ở trên (~30%), củng cố thêm độ tin cậy của bước lọc này. Sau khi lọc, bộ mẫu cuối "
        "cùng vẫn đủ 300 điểm/lớp cho cả 4 lớp (tổng 1.200 điểm), chia 70/30 cho train (847 "
        "điểm)/test (353 điểm)."
    )
    add_para(
        doc,
        "Lưu ý: đây là cách lọc tự động dựa trên đặc trưng phổ, không phải rà từng điểm bằng "
        "tay. Không loại trừ khả năng vẫn còn một số điểm nhầm sót lại (ví dụ ao nước đục có "
        "NDWI thấp), hoặc loại nhầm vài điểm nước thật có NDWI thấp do bị che một phần bởi cây."
    )

    # 6. Kết luận
    add_heading(doc, "6. Kết luận và bước tiếp theo", 1)
    add_para(
        doc,
        "4 task đầu của Phase 2 đã hoàn thành: pipeline chạy trên GEE ổn định, bộ 9 đặc trưng "
        "tính đúng, bộ mẫu huấn luyện 1.200 điểm (300/lớp) đã qua rà soát và làm sạch riêng cho "
        "lớp Water. Phát hiện đáng chú ý nhất là WorldCover có tỷ lệ nhầm nhãn không nhỏ (đặc "
        "biệt ở lớp Water, ~30%), một phần có thể do sự khác biệt thời điểm giữa dữ liệu nền "
        "WorldCover (~2021) và composite Sentinel-2 dùng để trích đặc trưng (2022) — tức khu vực "
        "này đang biến động nhanh, đúng với bối cảnh dự án."
    )
    add_para(
        doc,
        "Bước tiếp theo (task 3.5-3.9): huấn luyện Random Forest 2 phương án (9 band và 5 band "
        "rút gọn), so sánh Kappa/OA, chọn phương án thắng, áp lên cả 5 mốc thời gian để ra bản "
        "đồ phân loại và diện tích lớp bê tông từng năm, cuối cùng kiểm chứng riêng kết quả năm "
        "2018 vì đây là năm có ít ảnh nhất và là mốc nền trước khi sân bay khởi công."
    )

    doc.save(OUT_PATH)
    print(f"[done] Da ghi {OUT_PATH}")


if __name__ == "__main__":
    main()
