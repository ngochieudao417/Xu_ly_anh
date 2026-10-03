#!/usr/bin/env python3
"""
Sinh tai lieu giai thich phuong phap va kien truc pipeline:
tung file lam gi, input gi, output gi, tai sao chon phuong phap do,
muc dich la gi, ung dung thuc te ra sao.

Chay:
    python scripts/generate_methodology_doc.py
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

BLACK = RGBColor(0, 0, 0)
FONT = "Times New Roman"
OUT = PROJECT_ROOT / "reports" / "Giai_thich_Phuong_phap_va_Pipeline.docx"


def font(run, size=13, bold=False, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    run.bold = bold
    run.italic = italic
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.append(rFonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(a), FONT)


def H(doc, text, level=1):
    h = doc.add_heading("", level=level)
    font(h.add_run(text), size={1: 15, 2: 13.5, 3: 13}.get(level, 13), bold=True)
    return h


def P(doc, text, size=13, bold=False, italic=False, align=None, after=6):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(after)
    font(p.add_run(text), size=size, bold=bold, italic=italic)
    return p


def KV(doc, label, value):
    """Dong dang 'Nhan: gia tri', nhan in dam."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(0.25)
    font(p.add_run(label + ": "), size=12.5, bold=True)
    font(p.add_run(value), size=12.5)
    return p


def TBL(doc, headers, rows, fsize=11.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        font(t.rows[0].cells[i].paragraphs[0].add_run(str(h)), size=fsize, bold=True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            font(cells[i].paragraphs[0].add_run(str(v)), size=fsize)
    doc.add_paragraph()
    return t


def FILEBLOCK(doc, filename, role, inp, out, why):
    P(doc, filename, size=13, bold=True, after=3)
    KV(doc, "Vai trò", role)
    KV(doc, "Đầu vào", inp)
    KV(doc, "Đầu ra", out)
    KV(doc, "Vì sao tách riêng file này", why)
    doc.add_paragraph()


def METHOD(doc, name, what, inp, out, why, purpose, app):
    H(doc, name, 2)
    KV(doc, "Là gì", what)
    KV(doc, "Đầu vào", inp)
    KV(doc, "Đầu ra", out)
    KV(doc, "Vì sao nhóm chọn cách này", why)
    KV(doc, "Mục đích trong bài toán", purpose)
    KV(doc, "Ứng dụng thực tế ngoài đề tài", app)
    doc.add_paragraph()


def main():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(13)
    st.font.color.rgb = BLACK

    # ---------------- BÌA ----------------
    P(doc,
      "GIẢI THÍCH PHƯƠNG PHÁP VÀ KIẾN TRÚC PIPELINE\n"
      "Đề tài: Đo lường tốc độ bê tông hóa khu vực sân bay Long Thành, 2018–2026",
      size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    P(doc, "Nhóm 07 — Học phần Xử lý ảnh", size=13, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    P(doc, f"Ngày lập: {date.today().strftime('%d/%m/%Y')}", size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    P(doc,
      "Tài liệu này trả lời bốn câu hỏi cho từng thành phần của hệ thống: file đó nhận đầu vào gì, "
      "trả ra đầu ra gì, vì sao chọn phương pháp đó thay vì cách khác, và phương pháp đó có ứng dụng "
      "thực tế nào ngoài phạm vi đề tài. Bố cục gồm năm phần: bảng thuật ngữ, tổng quan kiến trúc, chi tiết "
      "từng file, giải thích từng phương pháp kỹ thuật, và luồng dữ liệu xuyên suốt từ đầu tới cuối.")

    # ================= PHẦN I — THUẬT NGỮ =================
    doc.add_page_break()
    H(doc, "PHẦN I — BẢNG THUẬT NGỮ", 1)
    P(doc,
      "Phần này giải thích mọi thuật ngữ viết tắt và khái niệm chuyên ngành xuất hiện trong đề tài, "
      "chia theo bốn nhóm. Người đọc chưa quen viễn thám nên xem phần này trước.")

    H(doc, "I.1. Nhóm thuật ngữ về ảnh vệ tinh và dữ liệu", 2)
    TBL(doc, ["Thuật ngữ", "Nguyên gốc / viết tắt", "Giải thích"], [
        ["Viễn thám", "Remote sensing",
         "Ngành thu thập thông tin về bề mặt Trái Đất từ xa, chủ yếu bằng vệ tinh hoặc máy bay, không "
         "cần chạm trực tiếp vào đối tượng."],
        ["Điểm ảnh", "Pixel",
         "Ô vuông nhỏ nhất của ảnh số. Ảnh vệ tinh là một lưới điểm ảnh, mỗi điểm mang một giá trị đo được."],
        ["Độ phân giải không gian", "Spatial resolution",
         "Kích thước thực tế trên mặt đất mà một điểm ảnh phủ. Sentinel-2 là 10 m, nghĩa là mỗi điểm "
         "ảnh tương ứng một ô đất 10 × 10 m, tức 100 m²."],
        ["Kênh phổ", "Spectral band",
         "Vệ tinh không chụp một ảnh màu duy nhất mà chụp nhiều ảnh cùng lúc, mỗi ảnh ghi lại một dải "
         "bước sóng ánh sáng riêng. Mỗi ảnh đó gọi là một kênh phổ."],
        ["B2, B3, B4", "Blue, Green, Red",
         "Ba kênh ánh sáng nhìn thấy được: xanh dương, xanh lục, đỏ. Ghép ba kênh này lại được ảnh màu "
         "giống mắt người nhìn."],
        ["B8", "NIR — Near Infrared",
         "Kênh cận hồng ngoại, mắt người không thấy được. Cây xanh khỏe phản xạ rất mạnh ở kênh này, "
         "còn nước thì hấp thụ gần hết. Đây là kênh quan trọng nhất để phân biệt thực vật và nước."],
        ["B11, B12", "SWIR — Short-Wave Infrared",
         "Hai kênh hồng ngoại sóng ngắn. Bê tông, mái tôn, đất khô phản xạ mạnh ở đây, còn cây và nước "
         "thì yếu. Là kênh chủ lực để nhận diện bề mặt xây dựng."],
        ["Phản xạ bề mặt", "Surface reflectance",
         "Tỷ lệ ánh sáng bị bề mặt phản xạ lại, giá trị từ 0 đến 1. Ví dụ 0,25 nghĩa là bề mặt hắt lại "
         "25% lượng ánh sáng chiếu tới."],
        ["Level-1C", "Top-of-atmosphere reflectance",
         "Mức xử lý ảnh thô, giá trị đo ở đỉnh khí quyển, còn lẫn ảnh hưởng của bụi và hơi nước trong "
         "không khí. Nhóm KHÔNG dùng mức này."],
        ["Level-2A", "Bottom-of-atmosphere reflectance",
         "Mức đã hiệu chỉnh khí quyển, phản ánh đúng bề mặt đất. Nhóm dùng mức này để hai ảnh chụp hai "
         "ngày khác nhau có thể so sánh trực tiếp."],
        ["Hiệu chỉnh khí quyển", "Atmospheric correction",
         "Bước tính toán loại bỏ phần nhiễu do khí quyển gây ra, để giá trị còn lại đúng là của mặt đất."],
        ["SCL", "Scene Classification Layer",
         "Một kênh phụ đi kèm ảnh Level-2A, do chính ESA tạo bằng thuật toán Sen2Cor, gán sẵn mỗi điểm "
         "ảnh thuộc loại gì. Các mã nhóm quan tâm: 3 là bóng mây, 8 là mây trung bình, 9 là mây dày, "
         "10 là mây ti mỏng. Nhóm dùng kênh này để che mây."],
        ["Ảnh ghép", "Composite",
         "Một ảnh tổng hợp được tạo ra từ nhiều ảnh chụp ở các thời điểm khác nhau, nhằm loại mây và "
         "có được ảnh sạch đại diện cho cả một khoảng thời gian."],
        ["Trung vị", "Median",
         "Giá trị nằm giữa khi sắp xếp dãy số theo thứ tự. Khác trung bình ở chỗ không bị kéo lệch bởi "
         "vài giá trị bất thường, nên chống nhiễu mây tốt hơn."],
        ["AOI", "Area of Interest",
         "Vùng nghiên cứu, tức phần diện tích được khoanh lại để phân tích. AOI của nhóm rộng khoảng "
         "102 km² quanh sân bay Long Thành."],
        ["NoData", "—",
         "Điểm ảnh không có dữ liệu, thường nằm ngoài rìa ảnh hoặc bị lỗi cảm biến. Phải đếm và loại "
         "riêng chứ không được coi là giá trị 0."],
        ["CRS / EPSG", "Coordinate Reference System",
         "Hệ tọa độ dùng để định vị ảnh trên mặt đất. Nhóm dùng EPSG:32648, tức hệ UTM múi 48 Bắc, phù "
         "hợp cho khu vực Nam Bộ vì tính diện tích theo mét chính xác hơn hệ kinh vĩ độ."],
        ["GeoTIFF", "—",
         "Định dạng file ảnh có gắn kèm thông tin tọa độ địa lý, nhờ đó phần mềm biết mỗi điểm ảnh nằm "
         "ở đâu trên bản đồ thật."],
        ["COG", "Cloud Optimized GeoTIFF",
         "Biến thể GeoTIFF cho phép tải về đúng phần vùng cần dùng thay vì tải cả file. Nhờ đó nhóm chỉ "
         "tải phần AOI chứ không tải nguyên cảnh 110 × 110 km."],
        ["STAC", "SpatioTemporal Asset Catalog",
         "Chuẩn danh mục dữ liệu không gian, cho phép tìm ảnh theo tọa độ, ngày chụp và tỷ lệ mây bằng "
         "câu lệnh thay vì tìm thủ công."],
        ["GEE", "Google Earth Engine",
         "Nền tảng đám mây của Google chứa sẵn kho ảnh vệ tinh toàn cầu và cho phép tính toán ngay trên "
         "máy chủ, không cần tải ảnh về máy cá nhân."],
        ["WorldCover", "ESA WorldCover",
         "Bản đồ lớp phủ toàn cầu độ phân giải 10 m do Cơ quan Vũ trụ châu Âu phát hành, phân 11 lớp. "
         "Nhóm dùng làm nguồn nhãn huấn luyện, dữ liệu nền năm 2021."],
        ["BSQ", "Band Sequential",
         "Một cách sắp xếp dữ liệu ảnh nhiều kênh trong file: lưu hết kênh 1 rồi mới tới kênh 2. Dùng "
         "để tính dung lượng lưu trữ."],
    ], fsize=10.5)

    H(doc, "I.2. Nhóm thuật ngữ về chỉ số phổ", 2)
    TBL(doc, ["Thuật ngữ", "Công thức", "Giải thích"], [
        ["NDVI", "(B8 − B4) / (B8 + B4)",
         "Chỉ số thực vật chuẩn hóa (Normalized Difference Vegetation Index). Dựa vào việc cây xanh "
         "phản xạ mạnh cận hồng ngoại nhưng hấp thụ ánh sáng đỏ để quang hợp. Giá trị càng gần 1 thì "
         "thực vật càng dày. Cây khỏe thường trên 0,6; đất trống quanh 0,1–0,2; nước cho giá trị âm."],
        ["NDBI", "(B11 − B8) / (B11 + B8)",
         "Chỉ số xây dựng chuẩn hóa (Normalized Difference Built-up Index). Bê tông và mái nhà phản xạ "
         "mạnh hồng ngoại sóng ngắn nhưng yếu hơn ở cận hồng ngoại, ngược hẳn với cây xanh. Giá trị "
         "dương thường ứng với bề mặt đã xây dựng."],
        ["NDWI", "(B3 − B8) / (B3 + B8)",
         "Chỉ số nước chuẩn hóa (Normalized Difference Water Index). Nước hấp thụ gần hết cận hồng "
         "ngoại nên kênh xanh lục luôn lớn hơn, cho giá trị dương. Nhóm dùng chính đặc điểm này để lọc "
         "ra các mẫu nước bị gán sai nhãn."],
        ["Dạng hiệu chia tổng", "(A − B) / (A + B)",
         "Cấu trúc chung của cả ba chỉ số. Ưu điểm là kết quả luôn nằm trong khoảng −1 đến 1 và tự "
         "triệt tiêu phần lớn ảnh hưởng của điều kiện chiếu sáng, nên ảnh chụp hai ngày khác nhau vẫn "
         "so sánh được với nhau."],
    ], fsize=10.5)

    H(doc, "I.3. Nhóm thuật ngữ về học máy và đánh giá mô hình", 2)
    TBL(doc, ["Thuật ngữ", "Nguyên gốc", "Giải thích"], [
        ["Học máy", "Machine learning",
         "Cách để máy tự rút ra quy luật từ dữ liệu mẫu thay vì được lập trình sẵn từng trường hợp."],
        ["Đặc trưng", "Feature",
         "Một con số mô tả đối tượng, dùng làm đầu vào cho mô hình. Ở đây mỗi điểm ảnh có 9 đặc trưng: "
         "6 kênh phổ và 3 chỉ số."],
        ["Nhãn", "Label / class",
         "Câu trả lời đúng gắn với mỗi mẫu. Ở đây là 4 lớp: 0 nước, 1 thảm thực vật, 2 đất trống, 3 bề "
         "mặt xây dựng."],
        ["Mẫu huấn luyện", "Training sample",
         "Tập điểm đã biết nhãn, dùng để mô hình học. Nhóm có 1.200 điểm, chia 847 để học."],
        ["Tập kiểm tra", "Test set",
         "Phần dữ liệu giữ riêng, không cho mô hình thấy khi học, dùng để chấm điểm khách quan. Nhóm "
         "giữ 353 điểm."],
        ["Chia 70/30", "Train/test split",
         "Cách chia dữ liệu: 70% để học, 30% để chấm điểm. Nếu chấm điểm trên chính dữ liệu đã học thì "
         "kết quả sẽ đẹp giả tạo."],
        ["Lấy mẫu phân tầng", "Stratified sampling",
         "Lấy số mẫu bằng nhau cho mỗi lớp thay vì lấy ngẫu nhiên toàn vùng. Cần thiết vì thực tế thảm "
         "thực vật chiếm gần 94% còn nước chỉ 0,10%."],
        ["Cây quyết định", "Decision tree",
         "Mô hình dạng chuỗi câu hỏi có hoặc không. Ví dụ: NDVI lớn hơn 0,5 không? Nếu có thì hỏi tiếp "
         "NDBI, cứ thế cho tới khi ra kết luận."],
        ["Random Forest", "Rừng ngẫu nhiên",
         "Tập hợp nhiều cây quyết định, mỗi cây học trên một phần dữ liệu và một phần đặc trưng khác "
         "nhau, kết quả cuối lấy theo bình chọn đa số. Nhóm dùng 200 cây."],
        ["Seed", "Random seed",
         "Số khởi tạo cho bộ sinh số ngẫu nhiên. Cố định seed bằng 42 để mọi lần chạy đều ra đúng kết "
         "quả cũ, tức là kết quả tái lập được."],
        ["Ma trận nhầm lẫn", "Confusion matrix",
         "Bảng đối chiếu nhãn thật với nhãn mô hình đoán. Đường chéo là số đoán đúng, các ô ngoài đường "
         "chéo cho biết mô hình hay nhầm lớp nào với lớp nào."],
        ["OA", "Overall Accuracy",
         "Độ chính xác tổng thể: tỷ lệ số điểm đoán đúng trên tổng số điểm kiểm tra. Mô hình của nhóm "
         "đạt 85,27% và tăng lên 85,8% sau khi bổ sung mẫu."],
        ["Kappa", "Cohen's Kappa",
         "Chỉ số đo mức đồng thuận sau khi đã trừ đi phần đúng do may rủi. Cần thiết vì với 4 lớp thì "
         "đoán bừa cũng đúng khoảng 25%. Trên 0,8 được coi là rất tốt; nhóm đạt 0,803–0,811."],
        ["Producer accuracy", "Độ chính xác của người lập bản đồ",
         "Trong số các điểm THỰC TẾ thuộc một lớp, bao nhiêu phần trăm được mô hình gán đúng. Đo mức độ "
         "bỏ sót của lớp đó."],
        ["Consumer accuracy", "Độ chính xác của người dùng bản đồ",
         "Trong số các điểm mô hình GÁN vào một lớp, bao nhiêu phần trăm thực sự đúng. Đo mức độ báo "
         "nhầm của lớp đó."],
        ["Mất cân bằng lớp", "Class imbalance",
         "Tình trạng một lớp chiếm phần lớn dữ liệu còn lớp khác rất hiếm, khiến chỉ số đánh giá dễ gây "
         "hiểu nhầm nếu không xử lý."],
        ["OA có trọng số diện tích", "Area-weighted accuracy",
         "Cách tính độ chính xác gán lại trọng số cho từng lớp theo tỷ lệ diện tích thực tế, theo khuyến "
         "nghị của Olofsson và cộng sự năm 2014, để con số phản ánh đúng chất lượng bản đồ."],
    ], fsize=10.5)

    H(doc, "I.4. Nhóm thuật ngữ về xử lý ảnh và kỹ thuật", 2)
    TBL(doc, ["Thuật ngữ", "Nguyên gốc", "Giải thích"], [
        ["Che mây", "Cloud masking",
         "Đánh dấu và loại bỏ các điểm ảnh bị mây che, để chúng không tham gia vào tính toán."],
        ["Mặt nạ", "Mask",
         "Một lớp ảnh nhị phân đánh dấu điểm nào được dùng, điểm nào bị loại."],
        ["Nhiễu muối tiêu", "Salt-and-pepper noise",
         "Các đốm lẻ rải rác sai màu trên bản đồ phân loại, do mô hình xét từng điểm ảnh độc lập mà "
         "không nhìn các điểm xung quanh."],
        ["Lọc majority", "Majority / mode filter",
         "Gán lại mỗi điểm ảnh theo nhãn phổ biến nhất trong 9 điểm lân cận (cửa sổ 3 × 3), nhằm khử "
         "nhiễu muối tiêu. Dựa trên thực tế là đối tượng thật thường liền khối."],
        ["Cắt theo vùng", "Clip",
         "Giữ lại phần ảnh nằm trong ranh giới AOI, bỏ phần ngoài."],
        ["Tái lấy mẫu", "Resampling",
         "Đổi độ phân giải của ảnh. Nhóm hạ Sentinel-2 từ 10 m xuống 30 m để so sánh được với Landsat 8."],
        ["Đọc theo cửa sổ", "Windowed reading",
         "Chỉ đọc đúng phần ảnh cần dùng thay vì nạp cả file vào bộ nhớ, giúp xử lý ảnh lớn trên máy "
         "cấu hình thường."],
        ["Lấy mẫu reservoir", "Reservoir sampling",
         "Thuật toán lấy ngẫu nhiên đúng k phần tử từ một luồng dữ liệu dài không biết trước độ dài, "
         "chỉ duyệt một lần và giữ trong bộ nhớ đúng k phần tử."],
        ["Tương quan Pearson", "Pearson correlation",
         "Hệ số r đo mức độ hai dãy số biến thiên cùng nhau, giá trị từ −1 đến 1. Bình phương của nó "
         "mới là phần phương sai giải thích được: r bằng 0,714 chỉ tương ứng khoảng 51%."],
        ["Vành đai khoảng cách", "Distance ring / buffer",
         "Các vòng đồng tâm quanh một điểm, dùng để xét xem hiện tượng có thay đổi theo khoảng cách hay "
         "không. Nhóm dùng các vành 0–2, 2–4 và 4–6 km quanh tâm dự án."],
        ["QA_PIXEL", "Quality Assessment band",
         "Kênh đánh giá chất lượng của Landsat, mỗi bit đánh dấu một loại vấn đề. Bit thứ 3 là mây, bit "
         "thứ 4 là bóng mây."],
        ["Hệ số hiệu chỉnh", "Scale factor",
         "Hệ số quy đổi giá trị số nguyên trong file về giá trị phản xạ thật. Sentinel-2 chia cho "
         "10.000; Landsat Collection 2 nhân 0,0000275 rồi cộng −0,2."],
    ], fsize=10.5)

    # ================= PHẦN II =================
    doc.add_page_break()
    H(doc, "PHẦN II — TỔNG QUAN KIẾN TRÚC", 1)

    P(doc,
      "Hệ thống có hai pipeline chạy song song, ra đời ở hai giai đoạn khác nhau của đề tài. Điều này "
      "là cố ý chứ không phải làm trùng lặp.")

    TBL(doc, ["", "Pipeline 1 — Python cục bộ", "Pipeline 2 — Google Earth Engine"], [
        ["Giai đoạn", "Phase 1: khảo sát và tiền xử lý", "Phase 2: phân loại và đo biến động"],
        ["Nơi chạy", "Máy cá nhân, thư mục src/", "Máy chủ Google, thư mục src/gee/ và Scipt W2.js"],
        ["Nguồn ảnh", "AWS Open Data (sentinel-cogs), qua STAC API", "Kho ảnh sẵn có trên GEE"],
        ["Dữ liệu tải về", "Có — 5 ảnh GeoTIFF (~65 MB/ảnh)", "Không — chỉ tải kết quả cuối"],
        ["Mục đích chính", "Hiểu dữ liệu, kiểm tra chất lượng, EDA", "Huấn luyện mô hình, phân loại, tính diện tích"],
        ["Ưu điểm", "Kiểm soát hoàn toàn, chạy được offline", "Không tốn dung lượng máy, tính toán rất nhanh"],
        ["Nhược điểm", "Tải ảnh chậm, tốn ổ cứng", "Phụ thuộc mạng và hạn mức tài khoản"],
    ])

    P(doc,
      "Lý do có hai pipeline: giai đoạn đầu nhóm cần nhìn tận mắt từng điểm ảnh, đếm pixel thiếu, vẽ "
      "biểu đồ phân bố, nên tải hẳn ảnh về máy để chủ động. Đến giai đoạn phân loại thì phải chạy trên "
      "5 mốc thời gian và thử nhiều phương án mô hình, nếu vẫn tải ảnh về máy thì mỗi lần đổi tham số "
      "lại phải chờ rất lâu, nên chuyển hẳn lên Google Earth Engine để tính toán ngay trên máy chủ.")

    # ================= PHẦN II =================
    doc.add_page_break()
    H(doc, "PHẦN III — CHI TIẾT TỪNG FILE TRONG PIPELINE", 1)

    H(doc, "III.1. Pipeline 1 — Python cục bộ (thư mục src/)", 2)

    FILEBLOCK(doc, "src/config.py",
              "Nơi khai báo tập trung mọi hằng số: đường dẫn thư mục, danh sách 6 kênh phổ, 5 mốc thời "
              "gian, mã 4 lớp lớp phủ, hệ số quy đổi phản xạ 10.000, seed ngẫu nhiên 42.",
              "Không có (chỉ là khai báo).",
              "Các biến hằng số để mọi file khác import.",
              "Nếu rải hằng số khắp nơi thì sửa một chỗ phải nhớ sửa cả chục chỗ khác. Gom về một file "
              "giúp thêm một mốc thời gian mới chỉ cần sửa đúng một dòng.")

    FILEBLOCK(doc, "src/validation.py",
              "Kiểm tra chất lượng ảnh: đọc metadata (số kênh, kích thước, hệ tọa độ, độ phân giải), "
              "tính thống kê từng kênh, đếm pixel NoData, kiểm tra tính nhất quán giữa các năm, sinh "
              "báo cáo QC dạng văn bản.",
              "Đường dẫn tới file ảnh GeoTIFF.",
              "Từ điển metadata, bảng thống kê min/max/mean/std từng kênh, số pixel lỗi, file QC_<năm>.txt.",
              "Nguyên tắc của nhóm là không tin dữ liệu cho tới khi kiểm tra. File này chạy trước mọi "
              "bước khác, nếu ảnh hỏng thì dừng ngay chứ không để lỗi lan xuống dưới.")

    FILEBLOCK(doc, "src/preprocessing.py",
              "Xử lý ảnh thô: phân loại từng pixel là hợp lệ hay thiếu/ngoài ngưỡng/bị mây/ngoài vùng "
              "nghiên cứu; quy đổi giá trị số về thang phản xạ 0–1; cắt ảnh theo ranh giới AOI; lấy mẫu "
              "ngẫu nhiên pixel bằng thuật toán reservoir sampling; đọc ảnh giảm độ phân giải để vẽ hình.",
              "Ảnh GeoTIFF gốc, mặt nạ mây (nếu có), ranh giới AOI dạng GeoJSON.",
              "Mảng NumPy các pixel hợp lệ đã lấy mẫu, bảng đếm pixel theo từng loại, ảnh đã cắt.",
              "Đây là phần dễ sai nhất và cũng nặng nhất về bộ nhớ, tách riêng để kiểm thử độc lập được "
              "và để phần còn lại của chương trình không phải quan tâm chuyện đọc file ảnh.")

    FILEBLOCK(doc, "src/features.py",
              "Tính ba chỉ số phổ NDVI, NDBI, NDWI bằng phép chia an toàn (mẫu số bằng 0 thì trả về "
              "NaN thay vì lỗi), và ghép thành bảng dữ liệu dạng cột.",
              "Từ điển các mảng giá trị 6 kênh phổ.",
              "Bảng DataFrame: năm, 6 kênh phổ, 3 chỉ số, và cột nhãn lớp nếu có.",
              "Công thức chỉ số là phần dễ chép nhầm dấu nhất trong cả dự án. Tách riêng và viết test "
              "cho nó thì chỉ cần đúng một lần là dùng chung cho mọi nơi.")

    FILEBLOCK(doc, "src/visualization.py",
              "Sinh toàn bộ biểu đồ: ảnh tổ hợp màu RGB, biểu đồ phân bố từng kênh, phân bố chỉ số, "
              "boxplot, ma trận tương quan, bản đồ không gian NDVI/NDBI/NDWI, biểu đồ xu hướng theo năm.",
              "Bảng DataFrame đặc trưng hoặc mảng ảnh 2 chiều.",
              "File PNG độ phân giải 200 DPI lưu trong outputs/figures/.",
              "Mọi hàm đều tự lưu file và tự đóng hình, nhờ đó gọi trong vòng lặp 5 năm không bị tràn "
              "bộ nhớ, và hình luôn có tiêu đề, nhãn trục thống nhất để đưa thẳng vào báo cáo.")

    FILEBLOCK(doc, "scripts/fetch_sentinel2_data.py",
              "Tải ảnh Sentinel-2 thật từ kho công khai trên AWS thông qua STAC API, đọc theo cửa sổ "
              "nên chỉ tải đúng phần AOI chứ không tải nguyên cảnh 110 × 110 km; đồng thời tạo mặt nạ "
              "mây từ lớp SCL.",
              "Danh sách mã ảnh đã chọn sẵn cho từng năm, tọa độ AOI.",
              "5 file data/raw/<năm>.tif (6 kênh) + 5 file mặt nạ mây + file ranh giới AOI.",
              "Mã ảnh được ghim cứng trong file thay vì tìm động, để lần chạy sau vẫn tải đúng những "
              "ảnh đó, bảo đảm kết quả tái lập được.")

    FILEBLOCK(doc, "scripts/run_pipeline.py",
              "Chạy toàn bộ Phase 1 theo thứ tự: kiểm tra ảnh, tiền xử lý, tính đặc trưng, sinh thống "
              "kê, vẽ hình, rồi tự động ghép số liệu thật vào báo cáo Markdown.",
              "Thư mục data/raw/ chứa ảnh.",
              "outputs/statistics/*.csv, outputs/figures/*.png, outputs/reports/QC_*.txt, "
              "reports/Phase_1_Data_Preprocessing_and_EDA.md.",
              "Toàn bộ báo cáo được sinh tự động từ số liệu vừa chạy, nên không có chuyện số trong báo "
              "cáo lệch với số trong dữ liệu. Thêm dữ liệu mới thì chạy lại một lệnh là báo cáo tự cập nhật.")

    FILEBLOCK(doc, "tests/test_pipeline_smoke.py",
              "Bộ kiểm thử tự động 6 test: tạo một ảnh giả nhỏ trong thư mục tạm rồi chạy toàn bộ chuỗi "
              "xử lý để xác nhận code chạy đúng.",
              "Không có (tự tạo dữ liệu thử).",
              "Kết quả pass/fail.",
              "Viết ở thời điểm chưa có ảnh thật, để chắc chắn code đúng trước khi đổ dữ liệu thật vào. "
              "Test kiểm tra cả tính tái lập: chạy hai lần với cùng seed phải ra cùng kết quả.")

    H(doc, "III.2. Pipeline 2 — Google Earth Engine (thư mục src/gee/)", 2)

    FILEBLOCK(doc, "src/gee/config.py",
              "Khai báo tập trung cho pipeline GEE: khóa xác thực tài khoản dịch vụ, tọa độ AOI chuẩn, "
              "khung thời gian mùa khô, danh sách đặc trưng phương án A và B, bảng ánh xạ 11 lớp "
              "WorldCover về 4 lớp của đề tài.",
              "Không có.",
              "Hằng số và hàm khởi tạo kết nối GEE.",
              "Bảng ánh xạ lớp phủ nằm ở đây nên khi muốn đổi cách gộp lớp chỉ sửa một từ điển, không "
              "phải lục lại code phân loại.")

    FILEBLOCK(doc, "src/gee/composite.py",
              "Ghép ảnh: lọc ảnh theo AOI, theo khung mùa khô và theo ngưỡng mây; che mây từng pixel "
              "bằng lớp SCL; lấy trung vị; cắt theo AOI; tính thêm 3 chỉ số phổ.",
              "Số năm cần ghép.",
              "Một ảnh 9 kênh trên máy chủ GEE, đã sạch mây, đại diện cho năm đó.",
              "Toàn bộ logic ghép ảnh gom về một hàm duy nhất, nên 5 mốc thời gian chắc chắn được xử lý "
              "y hệt nhau. Nếu mỗi mốc xử lý khác nhau thì so sánh biến động sẽ vô nghĩa.")

    FILEBLOCK(doc, "src/gee/sampling.py",
              "Lấy mẫu huấn luyện: đọc bản đồ WorldCover, gộp về 4 lớp, đếm số pixel từng lớp, lấy mẫu "
              "phân tầng 300 điểm mỗi lớp, lọc riêng lớp Water bằng ngưỡng NDWI, chia 70/30.",
              "Ảnh 9 kênh của năm tham chiếu và bản đồ WorldCover.",
              "Tập điểm mẫu có nhãn kèm giá trị 9 đặc trưng, đã chia train/test.",
              "Trong file có ghi chú rõ một cái bẫy: hàm lấy mẫu phân tầng của GEE vẫn lấy cả các lớp "
              "không được liệt kê, gây lẫn mẫu. Nhóm đã gặp lỗi này thật và phải lọc cứng lại theo nhãn.")

    FILEBLOCK(doc, "src/gee/qc_visual.py",
              "Rà mẫu bằng mắt: cắt ảnh chip 300 × 300 m quanh từng điểm mẫu, đánh dấu vị trí điểm, "
              "ghép 20 chip thành một tấm để xem một lượt.",
              "Tập điểm mẫu và ảnh nền của năm tham chiếu.",
              "4 file PNG contact sheet, mỗi file 20 chip cho một lớp.",
              "Đây là bước duy nhất trong cả hệ thống mà con người phải nhìn và tự đánh giá. Chính bước "
              "này phát hiện ra 30% mẫu lớp Water bị gán sai nhãn.")

    FILEBLOCK(doc, "src/gee/classify.py",
              "Huấn luyện Random Forest 200 cây và đánh giá: tính ma trận nhầm lẫn, độ chính xác tổng "
              "thể, hệ số Kappa, producer/consumer accuracy, mức quan trọng của từng đặc trưng.",
              "Tập train, tập test, danh sách đặc trưng cần dùng.",
              "Bộ phân loại đã huấn luyện và bảng chỉ số đánh giá.",
              "Hàm nhận danh sách đặc trưng làm tham số, nhờ đó so sánh phương án A và B chỉ là gọi "
              "cùng một hàm hai lần với danh sách khác nhau, bảo đảm so sánh công bằng.")

    FILEBLOCK(doc, "src/gee/apply_model.py",
              "Áp mô hình đã huấn luyện lên từng năm, tính diện tích từng lớp bằng cách nhân số pixel "
              "với diện tích một pixel, và xuất bản đồ phân loại ra ảnh PNG có tô màu theo lớp.",
              "Bộ phân loại đã huấn luyện và danh sách các năm.",
              "5 bản đồ phân loại PNG và bảng diện tích theo héc ta cho từng lớp từng năm.",
              "Đây là bước biến kết quả mô hình thành con số dùng được cho báo cáo, tách riêng để lúc "
              "đổi mô hình không phải viết lại phần tính diện tích.")

    FILEBLOCK(doc, "Scipt W2.js (chạy trực tiếp trên GEE Code Editor)",
              "Bản tổng hợp toàn bộ quy trình hai tuần thành một script JavaScript duy nhất, 11 bước, "
              "chạy được từ trên xuống dưới, gồm cả phân tích vành đai khoảng cách và kiểm chứng chéo "
              "với Landsat 8 mà bản Python chưa có.",
              "Không có (mọi thứ khai báo bên trong).",
              "Bản đồ hiển thị trực tiếp trên trình duyệt, các bảng số in ra Console, và lệnh xuất kết "
              "quả ra Google Drive.",
              "Bản JavaScript để cả nhóm và giảng viên mở trên trình duyệt là chạy được ngay, không cần "
              "cài đặt gì. Bản Python để tự động sinh báo cáo và kiểm thử. Hai bản dùng cùng tham số nên "
              "cho cùng kết quả.")

    H(doc, "III.3. Nhóm file sinh tài liệu (thư mục scripts/)", 2)
    P(doc,
      "Toàn bộ báo cáo, slide và tài liệu của đề tài đều được sinh bằng code chứ không gõ tay, nhằm "
      "bảo đảm số liệu trong tài liệu luôn khớp với số liệu chạy ra.")
    TBL(doc, ["File", "Đầu ra"], [
        ["generate_2018_analysis_report.py", "Báo cáo phân tích riêng mốc 2018 (docx)"],
        ["generate_gee_3_1_to_3_4_report.py", "Báo cáo task 3.1–3.4 (docx)"],
        ["generate_gee_3_5_to_3_9_report.py", "Báo cáo task 3.5–3.9 (docx)"],
        ["generate_presentation_script.py", "Kịch bản thuyết trình đầy đủ (docx)"],
        ["generate_slides.py", "Bộ 20 slide có chèn ảnh thật (pptx)"],
        ["generate_readme_docx.py", "Bản Word của tài liệu tổng quan dự án"],
        ["generate_methodology_doc.py", "Chính tài liệu bạn đang đọc"],
    ])

    # ================= PHẦN III =================
    doc.add_page_break()
    H(doc, "PHẦN IV — GIẢI THÍCH TỪNG PHƯƠNG PHÁP", 1)
    P(doc, "Mỗi phương pháp được trình bày theo cùng một khuôn: là gì, vào gì ra gì, vì sao chọn, "
           "mục đích trong bài toán, và ứng dụng thực tế ngoài đề tài.")

    METHOD(doc, "IV.1. Ghép ảnh trung vị theo khung mùa khô (median composite)",
           "Gom tất cả ảnh chụp cùng một vùng trong một khoảng thời gian, rồi với mỗi vị trí điểm ảnh "
           "lấy giá trị trung vị của các ảnh.",
           "Nhiều chục ảnh Sentinel-2 chụp rải rác trong khung 01/12 đến 30/04.",
           "Một ảnh duy nhất, gần như sạch mây, đại diện cho năm đó.",
           "Một ảnh chụp một ngày rất dễ dính mây, mà Nam Bộ mùa mưa thì mây gần như quanh năm. Nhóm "
           "chọn trung vị chứ không phải trung bình vì trung bình bị kéo lệch bởi giá trị bất thường: "
           "một điểm ảnh mây sót lại có phản xạ rất cao sẽ kéo trung bình lên, còn trung vị thì không "
           "bị ảnh hưởng nếu số điểm mây ít hơn một nửa. Chọn khung mùa khô vừa để tránh mây, vừa để "
           "mốc 2026 có đủ dữ liệu tại thời điểm nghiên cứu.",
           "Tạo ra 5 ảnh nền có chất lượng tương đương nhau để so sánh biến động giữa các năm cho có ý nghĩa.",
           "Đây là cách làm tiêu chuẩn của mọi hệ thống giám sát bề mặt Trái Đất quy mô lớn: theo dõi "
           "mất rừng, giám sát mùa vụ nông nghiệp, lập bản đồ lớp phủ quốc gia đều dùng ảnh ghép theo mùa.")

    METHOD(doc, "IV.2. Che mây bằng lớp phân loại cảnh SCL",
           "Sentinel-2 mức Level-2A đi kèm một kênh phụ tên SCL, trong đó ESA đã gán sẵn mỗi điểm ảnh "
           "thuộc loại gì: mây dày, mây mỏng, bóng mây, nước, thực vật, đất trống...",
           "Ảnh Sentinel-2 kèm kênh SCL.",
           "Ảnh đã bị che (mask) tại các điểm ảnh mang mã 3, 8, 9, 10.",
           "Nhóm có thể tự viết thuật toán dò mây, nhưng SCL do chính ESA tạo bằng thuật toán Sen2Cor "
           "đã được kiểm định trên toàn cầu, chính xác hơn nhiều so với tự làm. Việc lọc ở hai mức là "
           "cố ý: mức cảnh lọc thô với ngưỡng rộng 60% để không loại oan ảnh dùng được, còn lọc tinh "
           "thì làm ở mức từng điểm ảnh.",
           "Loại bỏ mây trước khi ghép ảnh, để giá trị trung vị phản ánh đúng bề mặt đất chứ không phải đỉnh mây.",
           "Mọi ứng dụng viễn thám quang học đều phải xử lý mây. Với vùng nhiệt đới như Việt Nam thì "
           "đây gần như là bước bắt buộc, nếu bỏ qua thì kết quả phân loại sai hoàn toàn ở các vùng có mây.")

    METHOD(doc, "IV.3. Ba chỉ số phổ NDVI, NDBI, NDWI",
           "Các chỉ số chuẩn hóa dạng hiệu chia tổng của hai kênh phổ: "
           "NDVI = (B8 − B4)/(B8 + B4), NDBI = (B11 − B8)/(B11 + B8), NDWI = (B3 − B8)/(B3 + B8).",
           "Các kênh phổ gốc B3, B4, B8, B11.",
           "Ba ảnh chỉ số, giá trị nằm trong khoảng −1 đến 1.",
           "Ba chỉ số này đều là công thức kinh điển đã công bố: NDVI của Rouse và cộng sự năm 1974, "
           "NDBI của Zha và cộng sự năm 2003. Ưu điểm của dạng hiệu chia tổng là tự triệt tiêu phần lớn "
           "ảnh hưởng của điều kiện chiếu sáng, nên hai ảnh chụp hai ngày khác nhau vẫn so sánh được. "
           "Nhóm dùng phép chia an toàn, mẫu số bằng 0 thì trả về NaN thay vì gây lỗi hoặc ra vô cực.",
           "Cung cấp cho mô hình những đặc trưng có ý nghĩa vật lý rõ ràng: thực vật cho NDVI cao, bề "
           "mặt xây dựng cho NDBI cao, mặt nước cho NDWI dương. Nhờ vậy mô hình học nhanh hơn và giải "
           "thích được kết quả.",
           "NDVI được dùng để theo dõi hạn hán, dự báo năng suất mùa vụ, đánh giá sức khỏe cây trồng. "
           "NDBI dùng trong quy hoạch đô thị và nghiên cứu đảo nhiệt đô thị. NDWI dùng để lập bản đồ "
           "ngập lụt và theo dõi mực nước hồ chứa.")

    METHOD(doc, "IV.4. Lấy mẫu phân tầng từ ESA WorldCover",
           "Dùng bản đồ lớp phủ toàn cầu có sẵn làm nguồn nhãn, lấy ngẫu nhiên đúng 300 điểm cho mỗi "
           "lớp thay vì lấy ngẫu nhiên toàn vùng.",
           "Bản đồ WorldCover 10 m và ranh giới AOI.",
           "1.200 điểm mẫu có nhãn, mỗi điểm kèm 9 giá trị đặc trưng.",
           "Nếu lấy ngẫu nhiên đều trên toàn vùng thì với tỷ lệ thực tế Vegetation chiếm 93,95% còn "
           "Water chỉ 0,10%, trong 1.200 điểm sẽ chỉ có khoảng một điểm nước, mô hình không học được "
           "lớp đó. Lấy phân tầng bảo đảm mỗi lớp đều đủ mẫu. Dùng WorldCover thay vì tự khoanh tay "
           "giúp tiết kiệm rất nhiều thời gian, đổi lại phải chấp nhận nhãn có sai sót và phải kiểm tra lại.",
           "Tạo bộ dữ liệu huấn luyện cho Random Forest mà không phải khoanh thủ công hàng nghìn điểm.",
           "Lấy mẫu phân tầng là kỹ thuật cơ bản trong thống kê và học máy, dùng bất cứ khi nào dữ liệu "
           "mất cân bằng lớp: phát hiện gian lận thẻ tín dụng, chẩn đoán bệnh hiếm, phân loại email rác.")

    METHOD(doc, "IV.5. Lọc mẫu sai bằng ngưỡng NDWI",
           "Sau khi phát hiện khoảng 30% mẫu lớp Water bị gán sai, nhóm lấy dư 950 điểm rồi loại các "
           "điểm có NDWI nhỏ hơn hoặc bằng 0, sau đó chọn lại 300 điểm.",
           "950 điểm mẫu lớp Water thô kèm giá trị NDWI.",
           "300 điểm mẫu Water đã làm sạch (loại bỏ 32,6%).",
           "Ngưỡng NDWI dương là tiêu chí vật lý rõ ràng: mặt nước hấp thụ mạnh tia cận hồng ngoại nên "
           "kênh xanh lục luôn lớn hơn kênh cận hồng ngoại. Điểm quan trọng nhất là tỷ lệ loại bỏ tính "
           "bằng công thức, 32,6%, trùng khớp với tỷ lệ đếm bằng mắt, khoảng 30%. Hai cách kiểm tra "
           "hoàn toàn độc lập cùng ra một kết quả nên nhóm tin bước lọc này đúng.",
           "Giảm nhiễu nhãn trước khi huấn luyện, vì mô hình học từ nhãn sai thì kết quả cũng sai theo.",
           "Làm sạch nhãn là công đoạn chiếm phần lớn thời gian trong mọi dự án học máy thực tế. Nguyên "
           "tắc chung là dữ liệu sạch quan trọng hơn mô hình phức tạp.")

    METHOD(doc, "IV.6. Rà mẫu bằng mắt trên ảnh chip",
           "Cắt một ô ảnh 300 × 300 m quanh mỗi điểm mẫu, đánh dấu vị trí điểm ở giữa, ghép 20 ô thành "
           "một tấm rồi nhìn xem nhãn có khớp với thực tế trên ảnh không.",
           "20 điểm mẫu ngẫu nhiên mỗi lớp và ảnh nền năm tham chiếu.",
           "4 tấm contact sheet, kèm tỷ lệ nghi nhầm ước lượng cho từng lớp.",
           "Không có cách tự động nào phát hiện được lỗi nhãn kiểu này, vì bản thân nhãn mới là thứ "
           "đang bị nghi ngờ. Chỉ có nhìn tận mắt mới thấy điểm mẫu 'mặt nước' đang nằm giữa ngã tư.",
           "Kiểm định chất lượng nguồn nhãn trước khi tin tưởng nó. Đây là bước phát hiện ra lỗi nghiêm "
           "trọng nhất của cả đề tài.",
           "Trong công nghiệp gọi là kiểm tra chất lượng dữ liệu gán nhãn. Mọi bộ dữ liệu lớn đều có "
           "quy trình lấy mẫu ngẫu nhiên để rà tay, vì không ai đủ nguồn lực rà toàn bộ.")

    METHOD(doc, "IV.7. Random Forest",
           "Thuật toán học máy dựa trên tập hợp nhiều cây quyết định. Nhóm dùng 200 cây, mỗi cây học "
           "trên một tập con dữ liệu và một tập con đặc trưng, kết quả cuối lấy theo bình chọn đa số.",
           "847 điểm mẫu huấn luyện, mỗi điểm có 9 đặc trưng và 1 nhãn lớp.",
           "Mô hình phân loại, gán được nhãn cho bất kỳ điểm ảnh nào từ 9 giá trị đặc trưng của nó.",
           "Ba lý do. Một, Random Forest chạy tốt với dữ liệu ít, 1.200 điểm là quá ít cho mạng nơ-ron "
           "nhưng vừa đủ cho thuật toán này. Hai, nó cho biết đặc trưng nào quan trọng nên nhóm giải "
           "thích được kết quả chứ không phải hộp đen. Ba, nó chạy sẵn trên Google Earth Engine nên "
           "không phải tải hàng chục GB ảnh về máy.",
           "Biến 9 con số phổ của mỗi điểm ảnh thành một trong bốn nhãn lớp phủ, từ đó tạo ra bản đồ "
           "phân loại cho cả 5 mốc thời gian.",
           "Random Forest được dùng rộng rãi: chấm điểm tín dụng ngân hàng, dự đoán rời bỏ khách hàng, "
           "chẩn đoán y tế, và đặc biệt phổ biến trong phân loại ảnh viễn thám vì độ chính xác cao mà "
           "không cần điều chỉnh nhiều tham số.")

    METHOD(doc, "IV.8. So sánh hai phương án đặc trưng A và B",
           "Huấn luyện hai mô hình trên cùng tập dữ liệu, cùng tham số, chỉ khác danh sách đặc trưng: "
           "phương án A dùng đủ 9, phương án B rút gọn còn 5.",
           "Cùng một tập train và test.",
           "Bảng so sánh OA, Kappa và producer accuracy từng lớp: A đạt 85,27% và 0,803, B đạt 81,02% "
           "và 0,746.",
           "Ở bước khảo sát dữ liệu nhóm thấy ba kênh khả kiến tương quan với nhau trên 0,9, còn cặp "
           "NDVI và NDWI gần như đối xứng nghịch với hệ số âm 0,97, nên nghi ngờ thông tin bị dư thừa "
           "và bỏ bớt vẫn được. Thực nghiệm bác bỏ giả thuyết đó. Điểm quan trọng về phương pháp là "
           "nhóm kiểm chứng bằng số liệu chứ không chọn theo cảm tính.",
           "Chọn ra cấu hình mô hình tốt nhất một cách có căn cứ, và chứng minh việc dùng đủ 9 đặc trưng "
           "là cần thiết chứ không thừa.",
           "Đây chính là bài toán chọn đặc trưng trong học máy. Ở các hệ thống thực tế, giảm số đặc "
           "trưng giúp giảm chi phí thu thập dữ liệu và tăng tốc độ, nên luôn đáng thử.")

    METHOD(doc, "IV.9. Ma trận nhầm lẫn, độ chính xác tổng thể và hệ số Kappa",
           "Ma trận nhầm lẫn là bảng đối chiếu nhãn thật với nhãn mô hình đoán. Từ đó tính độ chính xác "
           "tổng thể (tỷ lệ đoán đúng) và hệ số Kappa (mức đồng thuận sau khi trừ đi phần đúng do may rủi).",
           "353 điểm của tập test, hoàn toàn không dùng khi huấn luyện.",
           "Ma trận 4 × 4, OA 85,27%, Kappa 0,803.",
           "Chỉ nhìn độ chính xác tổng thể thì không biết mô hình sai ở đâu. Ma trận nhầm lẫn cho thấy "
           "cụ thể 16 điểm Built-up bị đoán thành Vegetation và 12 điểm bị đoán thành Bare Soil, khớp "
           "đúng với quan sát rằng ranh giới đất san lấp và bê tông rất mờ ở công trường. Hệ số Kappa "
           "được thêm vào vì với 4 lớp thì đoán bừa cũng đúng khoảng 25%, cần một chỉ số trừ đi phần đó.",
           "Đo và trình bày trung thực chất lượng mô hình, đồng thời chỉ ra chỗ cần cải thiện.",
           "Ma trận nhầm lẫn là công cụ đánh giá chuẩn của mọi bài toán phân loại, từ lọc thư rác đến "
           "chẩn đoán hình ảnh y tế. Trong y tế, phân biệt giữa bỏ sót bệnh và báo động nhầm chính là "
           "đọc hai ô khác nhau của ma trận này.")

    METHOD(doc, "IV.10. Độ chính xác có trọng số theo diện tích (Olofsson và cộng sự, 2014)",
           "Gán lại trọng số cho từng lớp trong ma trận nhầm lẫn theo tỷ lệ diện tích thực tế của lớp "
           "đó ngoài thực địa, thay vì theo số điểm trong tập test.",
           "Ma trận nhầm lẫn và tỷ lệ diện tích thực tế bốn lớp (0,10% / 93,95% / 1,79% / 4,17%).",
           "Một con số độ chính xác phản ánh đúng chất lượng bản đồ trên toàn vùng.",
           "Tập test của nhóm chia đều mỗi lớp 300 điểm, trong khi thực tế Vegetation chiếm gần 94% còn "
           "Water chỉ 0,1%. Nghĩa là lớp Water đang được tính trọng số cao gấp cả nghìn lần so với tỷ "
           "trọng thật của nó. Con số 85,27% vì vậy không đại diện cho độ chính xác thật của bản đồ. "
           "Nhóm bổ sung phép tính này theo khuyến nghị đã công bố thay vì tự nghĩ ra cách hiệu chỉnh.",
           "Báo cáo con số trung thực thay vì con số đẹp nhưng gây hiểu nhầm.",
           "Bắt buộc trong các báo cáo kiểm kê chính thức, ví dụ kiểm kê rừng quốc gia hay báo cáo phát "
           "thải các-bon, vì ở đó sai số diện tích quy trực tiếp thành sai số tiền và chính sách.")

    METHOD(doc, "IV.11. Lọc majority 3 × 3 sau phân loại",
           "Mỗi điểm ảnh được gán lại theo nhãn phổ biến nhất trong 9 điểm ảnh lân cận.",
           "Bản đồ phân loại thô có nhiễu đốm.",
           "Bản đồ phân loại mượt hơn, các đốm lẻ bị xóa.",
           "Mô hình phân loại từng điểm ảnh độc lập, không biết gì về hàng xóm, nên hay tạo ra các đốm "
           "lẻ dạng muối tiêu. Trong thực tế, một mái nhà 10 m vuông đơn độc giữa cánh đồng gần như "
           "chắc chắn là nhiễu. Bộ lọc này khai thác đúng đặc điểm đó: các đối tượng thật thường liền khối.",
           "Giảm nhiễu trên bản đồ 5 mốc, đặc biệt cần cho mốc 2018 vốn kém ổn định do chỉ có 3 ảnh nguồn.",
           "Cùng nguyên lý với bộ lọc trung vị trong xử lý ảnh nói chung, dùng để khử nhiễu muối tiêu "
           "trong ảnh chụp, ảnh y tế, ảnh quét tài liệu.")

    METHOD(doc, "IV.12. Lấy mẫu reservoir (chỉ dùng ở pipeline Python)",
           "Thuật toán lấy ngẫu nhiên đúng k phần tử từ một luồng dữ liệu dài không biết trước độ dài, "
           "chỉ cần duyệt qua một lần và giữ trong bộ nhớ đúng k phần tử.",
           "Luồng các pixel hợp lệ đọc theo từng khối từ ảnh GeoTIFF.",
           "20.000 pixel mẫu ngẫu nhiên đều, dùng cho phân tích thống kê.",
           "Một ảnh 5 mốc, mỗi ảnh vài triệu điểm ảnh nhân 6 kênh, nếu nạp hết vào RAM để lấy mẫu thì "
           "máy không chịu nổi. Thuật toán này bảo đảm mẫu vẫn ngẫu nhiên đều mà bộ nhớ dùng không đổi "
           "dù ảnh lớn tới đâu.",
           "Cho phép làm EDA trên ảnh lớn bằng máy cá nhân bình thường.",
           "Dùng trong xử lý dữ liệu luồng thời gian thực: lấy mẫu log hệ thống, lấy mẫu giao dịch để "
           "giám sát, khảo sát khi tổng thể quá lớn không đếm hết được.")

    METHOD(doc, "IV.13. Kiểm chứng chéo bằng vệ tinh Landsat 8",
           "Tính chỉ số NDBI song song trên hai vệ tinh khác nhau rồi đo hệ số tương quan Pearson giữa "
           "hai kết quả.",
           "Ảnh ghép Sentinel-2 (10 m) và Landsat 8 (30 m) cùng khung mùa khô, Sentinel-2 được hạ về "
           "lưới 30 m để khớp điểm ảnh.",
           "Hệ số r cho 4 năm: 0,714 / 0,836 / 0,733 / 0,901 và 4 bản đồ hiệu số.",
           "Nếu chỉ dùng một nguồn dữ liệu thì không có cách nào biết kết quả có bị lệch do đặc thù cảm "
           "biến hay không. Hai vệ tinh khác nhau, khác cả độ phân giải lẫn thiết kế kênh phổ, mà cho "
           "cùng xu hướng thì độ tin cậy cao hơn hẳn. Nhóm bắt buộc dùng đúng cùng khung mùa khô cho cả "
           "hai, vì nếu lấy khung cả năm thì hệ số tương quan sẽ phản ánh cả sai khác mùa vụ.",
           "Trả lời câu hỏi nghiên cứu thứ tư về độ tin cậy. Kết quả còn cho thêm một phát hiện: mốc "
           "2018 có tương quan thấp nhất, trùng với phát hiện độc lập rằng ảnh ghép 2018 kém ổn định.",
           "Nguyên tắc dùng nhiều nguồn độc lập để xác nhận cùng một kết luận áp dụng ở mọi ngành: đo "
           "đạc khí tượng, kiểm toán tài chính, chẩn đoán y khoa bằng nhiều phương pháp.")

    METHOD(doc, "IV.14. Phân tích theo vành đai khoảng cách",
           "Chia vùng nghiên cứu thành các vành theo khoảng cách tới tâm dự án rồi tính tỷ lệ bê tông "
           "trong từng vành.",
           "Bản đồ phân loại và tọa độ tâm dự án.",
           "Tỷ lệ và diện tích bê tông theo từng vành 0–2, 2–4, 4–6 km.",
           "Chỉ biết tổng diện tích bê tông thì chưa biết nó tập trung hay lan đều. Kế hoạch ban đầu "
           "dùng vòng đệm 5, 10, 15 km nhưng vùng nghiên cứu chỉ 102 km vuông, cạnh bắc cách tâm có "
           "3,33 km nên phải thu nhỏ lại. Vành từ 4 km trở ra chỉ là cung tròn thiếu phần phía bắc, nên "
           "nhóm so sánh bằng tỷ lệ phần trăm thay cho diện tích tuyệt đối, và viết hẳn một hàm tính "
           "phần vành bị cắt để nêu minh bạch trong báo cáo.",
           "Trả lời câu hỏi nghiên cứu thứ ba về quan hệ giữa mức độ bê tông hóa và khoảng cách tới sân bay.",
           "Phân tích theo vành đai là công cụ chuẩn trong nghiên cứu đô thị: đánh giá tác động lan tỏa "
           "của hạ tầng, định giá đất theo khoảng cách tới trung tâm, quy hoạch vùng ảnh hưởng sân bay "
           "và tuyến giao thông lớn.")

    # ================= PHẦN IV =================
    doc.add_page_break()
    H(doc, "PHẦN V — LUỒNG DỮ LIỆU TỪ ĐẦU TỚI CUỐI", 1)

    P(doc, "Tóm tắt toàn bộ hệ thống dưới dạng chuỗi biến đổi dữ liệu, để thấy rõ đầu vào ban đầu là "
           "gì và sản phẩm cuối cùng là gì.")

    TBL(doc, ["Bước", "Đầu vào", "Xử lý", "Đầu ra"], [
        ["1", "Kho ảnh Sentinel-2 công khai", "Lọc theo AOI, mùa khô, ngưỡng mây", "Vài chục ảnh thô mỗi mốc"],
        ["2", "Ảnh thô + kênh SCL", "Che mây từng điểm ảnh, lấy trung vị, cắt AOI", "5 ảnh ghép 6 kênh"],
        ["3", "Ảnh ghép 6 kênh", "Tính NDVI, NDBI, NDWI", "5 ảnh 9 kênh"],
        ["4", "Ảnh 9 kênh (2022) + WorldCover", "Lấy mẫu phân tầng, rà bằng mắt, lọc NDWI", "1.200 điểm mẫu sạch"],
        ["5", "1.200 điểm mẫu", "Chia 70/30, huấn luyện Random Forest, so sánh A và B", "Mô hình phương án A"],
        ["6", "Mô hình + 353 điểm test", "Ma trận nhầm lẫn, OA, Kappa, OA có trọng số", "Bộ chỉ số đánh giá"],
        ["7", "Mô hình + 5 ảnh 9 kênh", "Phân loại từng điểm ảnh, lọc majority 3×3", "5 bản đồ phân loại"],
        ["8", "5 bản đồ phân loại", "Đếm pixel × diện tích pixel", "Bảng diện tích 4 lớp × 5 mốc"],
        ["9", "Bản đồ + tâm dự án", "Chia vành đai, tính tỷ lệ từng vành", "Bảng bê tông theo khoảng cách"],
        ["10", "Sentinel-2 và Landsat 8", "Tính NDBI hai bên, hạ về 30 m, tương quan Pearson", "Hệ số r 4 năm"],
        ["11", "Toàn bộ kết quả trên", "Sinh báo cáo, slide, bản đồ bằng code", "docx, pptx, png, csv"],
    ])

    H(doc, "Sản phẩm cuối cùng", 2)
    P(doc, "Sau toàn bộ chuỗi trên, đề tài tạo ra bốn nhóm sản phẩm:")
    P(doc, "1. Số liệu định lượng: tỷ lệ bê tông hóa 12,93% năm 2018 tăng lên 25,17% năm 2026, với "
           "bước nhảy rõ rệt nhất từ 9,84% (2022) lên 26,44% (2024).")
    P(doc, "2. Bản đồ: 5 bản đồ phân loại lớp phủ, trong đó bản đồ 2024 hiện rõ hình dạng đường băng "
           "và sân đỗ do mô hình tự phân loại ra.")
    P(doc, "3. Chỉ số chất lượng: OA 85,8%, Kappa 0,811, kèm kiểm chứng chéo Landsat 8 với hệ số tương "
           "quan trung bình trên 0,79.")
    P(doc, "4. Quy trình tái lập được: toàn bộ mã nguồn cố định seed, ghim mã ảnh, gom hằng số về một "
           "chỗ, nên bất kỳ ai chạy lại cũng ra đúng những con số trong báo cáo.")

    H(doc, "Vì sao cách làm này có giá trị thực tế", 2)
    P(doc, "Toàn bộ chi phí dữ liệu của đề tài bằng không, vì cả ba nguồn Sentinel-2, Landsat 8 và "
           "WorldCover đều mở và miễn phí. Thời gian xử lý cho một khu vực khoảng 102 km vuông qua 5 "
           "mốc thời gian chỉ tính bằng phút trên nền tảng đám mây. So với khảo sát thực địa hay thuê "
           "ảnh hàng không thì chênh lệch chi phí là rất lớn.")
    P(doc, "Quan trọng hơn, quy trình này không gắn cứng vào sân bay Long Thành. Chỉ cần đổi tọa độ "
           "vùng nghiên cứu và danh sách mốc thời gian trong file cấu hình là chạy được cho bất kỳ khu "
           "vực nào khác: theo dõi mở rộng khu công nghiệp, giám sát lấn chiếm đất rừng, đánh giá tiến "
           "độ giải phóng mặt bằng của một dự án hạ tầng, hay lập bản đồ ngập lụt sau bão.")

    doc.save(OUT)
    print(f"[done] Da ghi {OUT}")


if __name__ == "__main__":
    main()
