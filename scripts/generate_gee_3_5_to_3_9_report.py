#!/usr/bin/env python3
"""
Bao cao task 3.5-3.9: train RF 2 phuong an, so sanh, ap len 5 moc, kiem
chung rieng 2018.

Chay:
    python scripts/generate_gee_3_5_to_3_9_report.py
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
OUT_PATH = gcfg.PROJECT_ROOT / "reports" / "Phase2_Task_3.5_den_3.9_GEE.docx"
FIG_DIR = gcfg.GEE_FIGURES_DIR
MAP_DIR = gcfg.GEE_MAPS_DIR


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
        "BÁO CÁO TIẾN ĐỘ PHASE 2 — TASK 3.5 ĐẾN 3.9\n"
        "HUẤN LUYỆN RANDOM FOREST, SO SÁNH PHƯƠNG ÁN, PHÂN LOẠI 5 MỐC\n"
        "VÀ KIỂM CHỨNG RIÊNG NĂM 2018",
        size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    add_para(doc, f"Ngày lập báo cáo: {date.today().strftime('%d/%m/%Y')}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    add_heading(doc, "1. Giới thiệu", 1)
    add_para(
        doc,
        "Báo cáo này nối tiếp báo cáo task 3.1-3.4 (chuyển pipeline sang GEE, xây bộ 9 đặc "
        "trưng, lấy mẫu từ WorldCover và rà soát nhãn). Nội dung ở đây: huấn luyện Random Forest "
        "với 2 phương án đặc trưng, so sánh và chọn phương án thắng, áp mô hình lên cả 5 mốc "
        "thời gian nghiên cứu để ra bản đồ phân loại và diện tích lớp bê tông/đất xây dựng, và "
        "kiểm chứng riêng kết quả năm 2018 vì đây là năm có ít ảnh nguồn nhất."
    )

    # 3.5 + 3.6
    add_heading(doc, "2. Task 3.5 và 3.6 — Huấn luyện Random Forest, 2 phương án", 1)
    add_para(
        doc,
        "Dùng bộ mẫu đã làm sạch ở task 3.4 (1.200 điểm, 300/lớp, đã lọc lại lớp Water), chia "
        "70/30 thành 847 điểm train và 353 điểm test (seed=42, cố định để tái lập được). Huấn "
        "luyện Random Forest 200 cây (smileRandomForest của GEE) với 2 bộ đặc trưng:"
    )
    add_para(doc, "Phương án A — 9 đặc trưng: B2, B3, B4, B8, B11, B12, NDVI, NDBI, NDWI.")
    add_para(doc, "Phương án B — 5 đặc trưng rút gọn: B4, B8, B11, NDVI, NDBI.")
    add_para(doc, "Kết quả đánh giá trên tập test (353 điểm, không dùng để train):")
    rows = [
        ["Overall Accuracy (OA)", "85.27%", "81.02%"],
        ["Kappa", "0.803", "0.746"],
        ["Producer accuracy - Water", "100.0%", "100.0%"],
        ["Producer accuracy - Vegetation", "80.4%", "70.7%"],
        ["Producer accuracy - Bare Soil", "91.9%", "89.2%"],
        ["Producer accuracy - Built-up", "68.5%", "64.0%"],
    ]
    add_table(doc, ["Chỉ số", "Phương án A (9 band)", "Phương án B (5 band)"], rows)
    add_para(
        doc,
        "Confusion matrix phương án A (hàng = nhãn thật, cột = nhãn dự đoán, thứ tự "
        "Water/Vegetation/Bare Soil/Built-up):"
    )
    add_table(doc, ["", "Water", "Vegetation", "Bare Soil", "Built-up"], [
        ["Water", 98, 0, 0, 0],
        ["Vegetation", 0, 74, 4, 14],
        ["Bare Soil", 0, 0, 68, 6],
        ["Built-up", 0, 16, 12, 61],
    ])
    add_para(
        doc,
        "Nhầm lẫn chính của cả 2 phương án đều là giữa Vegetation/Bare Soil/Built-up (đúng như "
        "quan sát ở task 3.4: ranh giới giữa \"đất trống\" và \"đã xây\" khá mờ tại các khu đang "
        "thi công), lớp Water thì tách biệt hoàn toàn (100% đúng ở cả 2 phương án) nhờ đã lọc "
        "sạch bằng NDWI ở bước trước."
    )

    add_heading(doc, "3. Task 3.7 — So sánh và chọn phương án", 1)
    add_para(
        doc,
        "Phương án A (9 band) thắng rõ ràng trên mọi chỉ số: OA cao hơn 4.25 điểm phần trăm, "
        "Kappa cao hơn 0.057. Đáng chú ý nhất, lớp Built-up (quan trọng nhất với mục tiêu dự án) "
        "cũng chính xác hơn ở phương án A (producer accuracy 68.5% so với 64.0%). Việc dùng "
        "thêm 4 band so với phương án B không tốn thêm chi phí tính toán đáng kể trên GEE, nên "
        "không có lý do để chọn phương án rút gọn. Quyết định: dùng phương án A (9 band) cho "
        "toàn bộ các bước sau."
    )

    # 3.8
    add_heading(doc, "4. Task 3.8 — Áp mô hình lên 5 mốc thời gian", 1)
    add_para(
        doc,
        "Áp phương án A lên composite của cả 5 năm (2018, 2020, 2022, 2024, 2026), sau đó lọc "
        "nhiễu \"muối tiêu\" bằng bộ lọc majority 3x3 (mỗi pixel lấy nhãn phổ biến nhất trong 9 "
        "pixel lân cận — kỹ thuật hậu xử lý chuẩn trong viễn thám, xem chi tiết lý do ở task "
        "3.9). Diện tích từng lớp tính bằng cách đếm pixel trong AOI (mỗi pixel = 100 m²)."
    )
    rows = [
        ["2018", "1.342,0 ha (12,93%)", "8.888,7 ha (85,61%)", "54,1 ha (0,52%)", "98,2 ha (0,95%)"],
        ["2020", "1.178,3 ha (11,30%)", "9.101,6 ha (87,28%)", "127,5 ha (1,22%)", "21,1 ha (0,20%)"],
        ["2022", "1.026,7 ha (9,84%)", "9.027,9 ha (86,57%)", "349,5 ha (3,35%)", "24,5 ha (0,23%)"],
        ["2024", "2.756,8 ha (26,44%)", "6.119,7 ha (58,68%)", "1.481,4 ha (14,20%)", "70,6 ha (0,68%)"],
        ["2026", "2.625,1 ha (25,17%)", "6.354,4 ha (60,93%)", "1.394,7 ha (13,37%)", "54,3 ha (0,52%)"],
    ]
    add_table(doc, ["Năm", "Built-up", "Vegetation", "Bare Soil", "Water"], rows)
    add_para(
        doc,
        "Phát hiện chính: diện tích Built-up gần như không đổi nhiều (9,8%-12,9%) trong giai "
        "đoạn 2018-2022, sau đó tăng vọt lên khoảng 25-26% ở 2024 và 2026 — tăng hơn gấp 2,5 "
        "lần chỉ trong giai đoạn 2022-2024. Điều này khớp với mốc thời gian thực tế của dự án: "
        "sân bay Long Thành khởi công đầu năm 2021 và khai trương tháng 12/2025, nên phần lớn "
        "khối lượng xây dựng lớn (đường băng, nhà ga, đường công vụ) diễn ra chủ yếu trong giai "
        "đoạn 2022-2024."
    )
    for y in gcfg.STUDY_YEARS:
        add_figure(doc, MAP_DIR / f"classified_final_{y}.png",
                   f"Bản đồ phân loại năm {y} (xanh lá=Vegetation, đỏ=Built-up, be=Bare Soil, xanh dương=Water).")
    add_para(
        doc,
        "So sánh trực quan bản đồ 2018 và 2024 cho thấy rõ nhất: vùng lõi trung tâm AOI (đúng vị "
        "trí sân bay) từ chủ yếu màu xanh lá (đất nông nghiệp) ở 2018 chuyển thành một khối đỏ "
        "lớn có hình dáng khớp với đường băng/sân đỗ ở 2024 — bằng chứng trực quan mạnh cho quá "
        "trình xây dựng sân bay."
    )

    # 3.9
    add_heading(doc, "5. Task 3.9 — Kiểm chứng riêng năm 2018", 1)
    add_para(
        doc,
        "Vì composite 2018 chỉ dựng từ 3 ảnh gốc (so với 45-52 ảnh các năm khác — xem báo cáo "
        "3.1-3.4), cần kiểm tra riêng xem kết quả phân loại 2018 có đáng tin không."
    )
    add_heading(doc, "5.1. Phát hiện vấn đề", 2)
    add_para(
        doc,
        "Trước khi xử lý, diện tích Built-up năm 2018 tính được là 16,2% — cao hơn cả 2020 "
        "(13,4%) và 2022 (12,0%), điều này vô lý vì 2018 là mốc trước khi sân bay khởi công, lẽ "
        "ra phải thấp nhất. So sánh bản đồ phân loại với ảnh RGB thật cho thấy: vùng lõi trung "
        "tâm AOI (khu vực sân bay) thực tế vẫn là đất nông nghiệp xanh tốt, KHÔNG bị gán nhầm "
        "toàn bộ thành \"bê tông\" — nhưng có nhiễu đốm đỏ (\"muối tiêu\") rải rác khắp vùng thực "
        "vật, nhiều khả năng do composite chỉ có 3 ảnh nên kém ổn định phổ hơn hẳn các năm khác."
    )

    add_heading(doc, "5.2. Xử lý", 2)
    add_para(doc, "Thực hiện 2 bước xử lý liên tiếp, đo lại diện tích Built-up sau mỗi bước:")
    rows = [
        ["Trước xử lý", "16,2%", "13,4%", "12,0%"],
        ["Sau lọc majority 3x3 (khử nhiễu đốm)", "14,9%", "12,2%", "10,8%"],
        ["Sau khi bổ sung mẫu tay cho 2018 + lọc majority", "12,9%", "11,3%", "9,8%"],
    ]
    add_table(doc, ["Bước xử lý", "2018", "2020", "2022"], rows)
    add_para(
        doc,
        "Bước 1 — lọc majority 3x3: là bước hậu xử lý chuẩn trong viễn thám, mỗi pixel được gán "
        "lại theo nhãn phổ biến nhất trong 9 pixel lân cận (3x3), giúp giảm nhiễu ngẫu nhiên. "
        "Giảm được Built-up ở tất cả các năm nhưng KHÔNG giải quyết được việc 2018 vẫn cao hơn "
        "2020/2022 — cho thấy vấn đề không chỉ là nhiễu ngẫu nhiên đơn thuần mà còn có sai lệch "
        "hệ thống trong composite 2018."
    )
    add_para(
        doc,
        "Bước 2 — bổ sung mẫu tay cho 2018: chọn 1 vùng hình chữ nhật trong AOI mà quan sát bằng "
        "mắt trên ảnh RGB xác nhận chắc chắn là đất nông nghiệp/thực vật (tránh các khu dân cư "
        "đã biết), lấy ngẫu nhiên 80 điểm trong vùng đó (seed=42), trích đặc trưng trực tiếp từ "
        "chính composite 2018 (khác với 1.200 mẫu gốc lấy đặc trưng từ composite 2022), gán nhãn "
        "Vegetation, rồi thêm vào tập train (847 → 927 điểm) và huấn luyện lại. Đây là cách "
        "\"vẽ mẫu tay\" tương đương với việc rà và bổ sung mẫu thủ công mà task đề ra, thực hiện "
        "bằng lấy mẫu ngẫu nhiên trong vùng đã xác nhận thay vì chọn từng điểm bằng tay."
    )
    add_para(
        doc,
        "Sau khi bổ sung, độ chính xác trên tập test giữ nguyên (thậm chí nhích lên: OA 85,8%, "
        "Kappa 0,811 so với 85,3%/0,803 trước đó — vì tập train lớn hơn), và Built-up 2018 giảm "
        "còn 12,9%, gần hơn nhiều với 2020 (11,3%)."
    )
    add_figure(doc, MAP_DIR / "classified_2018.png", "Bản đồ phân loại 2018 trước khi xử lý — nhiễu đốm đỏ rải khắp vùng thực vật.")
    add_figure(doc, MAP_DIR / "classified_final_2018.png", "Bản đồ phân loại 2018 sau khi lọc majority + bổ sung mẫu tay — vùng lõi trung tâm trở lại đúng màu xanh (Vegetation).")

    add_heading(doc, "5.3. Hạn chế còn lại", 2)
    add_para(
        doc,
        "Sau xử lý, Built-up 2018 (12,9%) vẫn cao hơn 2020 (11,3%) khoảng 1,6 điểm phần trăm. "
        "Chênh lệch này CÓ THỂ là thật (một số công trình nông thôn nhỏ lẻ có thể đã bị dỡ bỏ "
        "trong quá trình giải phóng mặt bằng giai đoạn 2018-2020), nhưng cũng CÓ THỂ vẫn còn dư "
        "sai lệch do composite 2018 chỉ có 3 ảnh nguồn. Báo cáo không ép số liệu về một xu hướng "
        "tăng đều hoàn hảo — đây là giới hạn thật của dữ liệu, cần nêu rõ khi trình bày kết quả, "
        "đặc biệt nếu về sau tính \"tốc độ bê tông hóa\" theo giai đoạn 2018-2022 thì nên coi "
        "khoảng dao động 9,8%-12,9% là tương đối ổn định, không có ý nghĩa thống kê mạnh, trong "
        "khi bước nhảy 2022→2024 mới là tín hiệu rõ ràng và đáng tin cậy nhất."
    )

    add_heading(doc, "6. Kết luận", 1)
    add_para(
        doc,
        "Phương án A (9 đặc trưng) được chọn làm mô hình chính thức (OA 85,3-85,8%, Kappa "
        "0,80-0,81 tùy có bổ sung mẫu 2018 hay không). Áp lên cả 5 mốc cho kết quả nhất quán với "
        "bối cảnh thực tế dự án: diện tích built-up ổn định quanh 10-13% trong giai đoạn "
        "2018-2022, sau đó tăng vọt lên 25-26% ở 2024-2026, trùng khớp với tiến độ xây dựng và "
        "khai trương sân bay Long Thành. Vấn đề chất lượng riêng của composite 2018 (do ít ảnh "
        "nguồn) đã được xử lý một phần bằng lọc majority và bổ sung mẫu tay, nhưng vẫn còn giới "
        "hạn cần nêu rõ khi diễn giải xu hướng chi tiết trong giai đoạn 2018-2022."
    )
    add_para(
        doc,
        "Đây vẫn là kết quả mô tả (descriptive), dựa trên 1 composite đại diện mỗi năm và 1 bộ "
        "mẫu tham chiếu duy nhất (2022) — CHƯA phải là phân tích tốc độ bê tông hóa chính thức "
        "theo đúng phạm vi Phase 1 đã thống nhất trước đó; việc đó cần thêm bước change detection "
        "và phân tích vùng đệm (buffer analysis) theo khoảng cách tới sân bay ở giai đoạn sau."
    )

    doc.save(OUT_PATH)
    print(f"[done] Da ghi {OUT_PATH}")


if __name__ == "__main__":
    main()
