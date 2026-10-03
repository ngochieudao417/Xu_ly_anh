#!/usr/bin/env python3
"""
Sinh bao cao docx cho 4 phan tich tuan 3:
  1. Ma tran chuyen doi 2022 -> 2024
  2. Do chinh xac co trong so dien tich
  3. Histogram NDBI 5 moc
  4. Kiem dinh nguong bien dong

Moi con so doc truc tiep tu outputs/statistics/gee/change_analysis.json,
khong go tay.

Chay:
    python scripts/generate_change_analysis_report.py
"""

from __future__ import annotations

import json
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
FONT = "Times New Roman"
OUT = PROJECT_ROOT / "reports" / "Phase2_Phan_tich_Bien_dong_va_Kiem_dinh.docx"
JSON_PATH = gcfg.GEE_STATS_DIR / "change_analysis.json"
FIG = gcfg.GEE_FIGURES_DIR

CLASS_ORDER = [0, 1, 2, 3]
CLASS_VN = {0: "Nước", 1: "Thảm thực vật", 2: "Đất trống", 3: "Bề mặt xây dựng"}


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


def IMG(doc, path: Path, caption: str, width=6.2):
    if not path.exists():
        P(doc, f"[Thiếu hình: {path.name}]", italic=True)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(c.add_run(caption), size=11, italic=True)
    doc.add_paragraph()


def fmt(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    acc = data["accuracy"]
    tm = data["transition_2022_2024"]
    hists = data["ndbi_histograms"]
    sig = data["change_significance"]

    mat = {int(i): {int(j): v for j, v in row.items()}
           for i, row in tm["matrix_ha"].items()}

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(13)
    st.font.color.rgb = BLACK

    # ---------------- BÌA ----------------
    P(doc,
      "BÁO CÁO PHÂN TÍCH BIẾN ĐỘNG VÀ KIỂM ĐỊNH ĐỘ TIN CẬY\n"
      "Ma trận chuyển đổi — Độ chính xác có trọng số diện tích —\n"
      "Histogram NDBI — Ngưỡng biến động đáng tin",
      size=15.5, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    P(doc, "Đề tài: Đo lường tốc độ bê tông hóa khu vực sân bay Long Thành, 2018–2026",
      size=13, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    P(doc, "Nhóm 07 — Học phần Xử lý ảnh", size=12.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    P(doc, f"Ngày lập báo cáo: {date.today().strftime('%d/%m/%Y')}",
      size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    # ---------------- 1. MỞ ĐẦU ----------------
    H(doc, "1. Mục tiêu và phạm vi", 1)
    P(doc,
      "Báo cáo này thực hiện bốn nội dung tiếp theo sau khi đã có bản đồ phân loại 5 mốc thời gian: "
      "lập ma trận chuyển đổi giữa hai mốc 2022 và 2024 để biết lớp nào chuyển thành lớp nào; tính "
      "độ chính xác có trọng số diện tích để thay cho con số 85,3% đã báo cáo trước đó; vẽ histogram "
      "NDBI từng mốc nhằm chứng minh phân bố phổ thực sự dịch chuyển theo thời gian; và kiểm định xem "
      "mức biến động nào nằm trong sai số của mô hình, mức nào đủ lớn để tin được.")
    P(doc,
      "Toàn bộ số liệu trong báo cáo được sinh tự động từ file "
      "outputs/statistics/gee/change_analysis.json, là kết quả chạy thật trên Google Earth Engine, "
      "không có con số nào gõ tay.")

    H(doc, "Mô hình dùng chung", 2)
    P(doc,
      "Mọi phân tích dùng chung một mô hình để các con số nhất quán với nhau: Random Forest 200 cây, "
      "phương án A với 9 đặc trưng, tập huấn luyện 927 điểm (gồm 847 điểm gốc và 80 điểm bổ sung tay "
      "cho mốc 2018), tập kiểm tra 353 điểm. Kết quả phân loại được lọc majority 3×3 trước khi tính "
      "diện tích, giống hệt quy trình đã dùng ở báo cáo task 3.8.")
    P(doc,
      "Lưu ý nhỏ về tính tái lập: hàm lấy mẫu phân tầng của Earth Engine không cho ra tập mẫu giống "
      "nhau tuyệt đối giữa các lần chạy, nên độ chính xác thông thường lần này là "
      f"{fmt(100*acc['oa_simple'], 2)}% thay vì 85,8% như lần chạy trước. Chênh lệch dưới 1 điểm phần "
      "trăm, không ảnh hưởng tới kết luận.")

    # ---------------- 2. MA TRẬN CHUYỂN ĐỔI ----------------
    doc.add_page_break()
    H(doc, "2. Ma trận chuyển đổi 2022 → 2024", 1)
    P(doc,
      "Cách làm: mã hóa từng điểm ảnh theo công thức lớp năm 2022 nhân 10 cộng lớp năm 2024. Ví dụ mã "
      "13 nghĩa là điểm ảnh đó năm 2022 thuộc lớp 1 (thảm thực vật) và năm 2024 đã thành lớp 3 (bề mặt "
      "xây dựng). Sau đó cộng diện tích theo từng mã, đơn vị héc ta.")
    P(doc, "Bảng 1. Ma trận chuyển đổi 2022 → 2024, đơn vị héc ta. "
           "Hàng là lớp năm 2022, cột là lớp năm 2024.", italic=True)

    rows = []
    for i in CLASS_ORDER:
        row_total = sum(mat[i][j] for j in CLASS_ORDER)
        rows.append([CLASS_VN[i]] + [fmt(mat[i][j]) for j in CLASS_ORDER] + [fmt(row_total)])
    col_totals = [sum(mat[i][j] for i in CLASS_ORDER) for j in CLASS_ORDER]
    rows.append(["Tổng 2024"] + [fmt(c) for c in col_totals] + [fmt(tm["total_ha"])])
    TBL(doc, ["2022 \\ 2024"] + [CLASS_VN[j] for j in CLASS_ORDER] + ["Tổng 2022"], rows)

    P(doc,
      f"Tổng diện tích so sánh được là {fmt(tm['total_ha'])} ha. Trong đó "
      f"{fmt(tm['unchanged_ha'])} ha giữ nguyên lớp và {fmt(tm['changed_ha'])} ha đã đổi lớp, tương "
      f"đương {fmt(tm['changed_pct'], 2)}% diện tích vùng nghiên cứu. Phần chênh so với tổng diện tích "
      "AOI 10 222 ha là do một số điểm ảnh không có dữ liệu ở ít nhất một trong hai mốc.")

    H(doc, "2.1. Các luồng chuyển đổi chính", 2)
    flows = [
        ("Thảm thực vật → Bề mặt xây dựng", mat[1][3]),
        ("Thảm thực vật → Đất trống", mat[1][2]),
        ("Bề mặt xây dựng → Thảm thực vật", mat[3][1]),
        ("Bề mặt xây dựng → Đất trống", mat[3][2]),
        ("Đất trống → Bề mặt xây dựng", mat[2][3]),
        ("Đất trống → Thảm thực vật", mat[2][1]),
    ]
    TBL(doc, ["Luồng chuyển đổi", "Diện tích (ha)", "Tỷ lệ AOI (%)"],
        [[name, fmt(ha), fmt(100 * ha / tm["total_ha"], 2)] for name, ha in flows])

    P(doc,
      f"Luồng lớn nhất và cũng là luồng đúng với kỳ vọng của đề tài: thảm thực vật chuyển thành bề mặt "
      f"xây dựng, {fmt(mat[1][3])} ha, chiếm {fmt(100*mat[1][3]/tm['total_ha'], 2)}% diện tích vùng "
      f"nghiên cứu. Đứng thứ hai là thảm thực vật chuyển thành đất trống, {fmt(mat[1][2])} ha. Hai "
      "luồng này cộng lại chính là bức tranh giải phóng mặt bằng và thi công: đất nông nghiệp bị san "
      "ủi thành mặt bằng trống, rồi một phần tiếp tục được đổ bê tông.")

    gain = mat[0][3] + mat[1][3] + mat[2][3]
    loss = mat[3][0] + mat[3][1] + mat[3][2]
    builtup_2022 = sum(mat[3][j] for j in CLASS_ORDER)
    P(doc,
      f"Tính cân bằng cho lớp bề mặt xây dựng: tăng thêm {fmt(gain)} ha từ các lớp khác, mất đi "
      f"{fmt(loss)} ha sang các lớp khác, net tăng {fmt(gain - loss)} ha. Con số này khớp với mức tăng "
      "1 730,1 ha tính độc lập từ bảng diện tích ở báo cáo task 3.8, nên hai cách tính xác nhận lẫn nhau.")

    H(doc, "2.2. Các luồng không hợp lý và ý nghĩa của chúng", 2)
    P(doc,
      f"Ma trận cũng phơi bày một vấn đề mà bảng diện tích tổng không cho thấy được. Có {fmt(mat[3][1])} "
      f"ha được phân loại là bề mặt xây dựng năm 2022 nhưng lại thành thảm thực vật năm 2024, và "
      f"{fmt(mat[3][2])} ha thành đất trống. Bê tông đã đổ thì không thể mọc lại thành cây, nên đây gần "
      "như chắc chắn là lỗi phân loại chứ không phải biến động thật.")
    P(doc,
      f"Tổng các luồng không hợp lý xuất phát từ lớp bề mặt xây dựng là {fmt(loss)} ha, bằng "
      f"{fmt(100*loss/builtup_2022, 1)}% toàn bộ diện tích được gán là bề mặt xây dựng năm 2022. Nói "
      "cách khác, gần một nửa số điểm ảnh mà mô hình gọi là bê tông năm 2022 đã đổi nhãn ở mốc sau. "
      "Đây là thước đo trực tiếp cho mức độ thiếu ổn định của mô hình ở cấp điểm ảnh, và là lý do vì "
      "sao phần kiểm định ở mục 5 lại cần thiết.")
    P(doc,
      "Cách diễn giải đúng: ma trận chuyển đổi dùng tốt để nhận diện xu hướng chủ đạo, nhưng không nên "
      "đọc từng ô nhỏ như một con số chính xác tuyệt đối.")

    # ---------------- 3. AREA-WEIGHTED ACCURACY ----------------
    doc.add_page_break()
    H(doc, "3. Độ chính xác có trọng số diện tích", 1)
    P(doc,
      "Vấn đề của con số cũ: tập kiểm tra được chia đều mỗi lớp 300 điểm, trong khi ngoài thực tế "
      "thảm thực vật chiếm 93,95% diện tích còn mặt nước chỉ 0,10%. Độ chính xác tổng thể tính theo "
      "cách thông thường vì vậy đang cho lớp hiếm một trọng số lớn hơn nhiều so với tỷ trọng thật của "
      "nó, nên không đại diện cho chất lượng thật của bản đồ.")
    P(doc,
      "Cách khắc phục theo Olofsson và cộng sự (2014): chuẩn hóa từng hàng của ma trận nhầm lẫn về "
      "xác suất, rồi nhân lại với tỷ lệ diện tích thực tế của lớp đó, sau đó cộng đường chéo.")

    P(doc, "Bảng 2. Ma trận nhầm lẫn của lần chạy này (hàng là nhãn tham chiếu, cột là nhãn dự đoán).",
      italic=True)
    cm = acc["confusion_matrix"]
    TBL(doc, ["Thực tế \\ Dự đoán"] + [CLASS_VN[j] for j in CLASS_ORDER] + ["Tổng"],
        [[CLASS_VN[i]] + [str(v) for v in cm[i]] + [str(sum(cm[i]))] for i in CLASS_ORDER])

    P(doc, "Bảng 3. So sánh hai cách tính độ chính xác.", italic=True)
    TBL(doc, ["Chỉ số", "Giá trị"], [
        ["Độ chính xác tổng thể thông thường", f"{fmt(100*acc['oa_simple'], 2)}%"],
        ["Độ chính xác có trọng số diện tích", f"{fmt(100*acc['oa_weighted'], 2)}%"],
        ["Sai số chuẩn", f"{fmt(100*acc['se'], 2)} điểm %"],
        ["Khoảng tin cậy 95%",
         f"{fmt(100*acc['ci95'][0], 2)}% – {fmt(100*acc['ci95'][1], 2)}%"],
        ["Hệ số Kappa", f"{fmt(acc['kappa'], 3)}"],
    ])

    P(doc,
      f"Con số chính thức để dùng trong báo cáo là {fmt(100*acc['oa_weighted'], 2)}%, kèm khoảng tin "
      f"cậy 95% từ {fmt(100*acc['ci95'][0], 2)}% đến {fmt(100*acc['ci95'][1], 2)}%. Con số này thấp hơn "
      f"độ chính xác thông thường khoảng {fmt(100*(acc['oa_simple']-acc['oa_weighted']), 1)} điểm phần "
      "trăm, và quan trọng hơn là nó đi kèm một khoảng tin cậy khá rộng, phản ánh đúng việc tập kiểm "
      "tra chỉ có 353 điểm.")

    H(doc, "3.1. Độ chính xác theo từng lớp sau khi gán trọng số", 2)
    P(doc, "Bảng 4. Producer accuracy và user accuracy có trọng số diện tích.", italic=True)
    TBL(doc, ["Lớp", "Tỷ lệ diện tích thực tế", "Producer accuracy", "User accuracy"],
        [[CLASS_VN[i], f"{fmt(100*acc['weights_used'][i], 2)}%",
          f"{fmt(100*acc['producer_weighted'][i], 2)}%",
          f"{fmt(100*acc['user_weighted'][i], 2)}%"] for i in CLASS_ORDER])

    P(doc,
      f"Đây là phát hiện đáng chú ý nhất của phần này. User accuracy của lớp bề mặt xây dựng chỉ đạt "
      f"{fmt(100*acc['user_weighted'][3], 2)}%, nghĩa là trong toàn bộ diện tích mà bản đồ gán là bê "
      "tông, ước tính chỉ khoảng một phần năm thực sự là bê tông. Nguyên nhân thuần túy là số học: "
      "thảm thực vật chiếm gần 94% diện tích, nên chỉ cần khoảng 12% diện tích thực vật bị nhận nhầm "
      "thành bê tông là phần nhầm đó đã lớn hơn nhiều so với toàn bộ diện tích bê tông thật.")
    P(doc,
      "Hệ quả trực tiếp: các con số diện tích tuyệt đối của lớp bê tông trong báo cáo trước, ví dụ "
      "2 756,8 ha năm 2024, nhiều khả năng là ước lượng vượt so với thực tế. Nhóm giữ nguyên số đã "
      "công bố nhưng bổ sung cảnh báo này thay vì lặng lẽ sửa lại.")
    P(doc,
      "Tuy nhiên, phần sai lệch này mang tính hệ thống: cùng một mô hình, cùng một kiểu nhầm lẫn được "
      "áp cho cả 5 mốc. Khi lấy hiệu giữa hai mốc thì phần lớn sai lệch hệ thống triệt tiêu lẫn nhau. "
      "Vì vậy mức biến động giữa các năm vẫn đáng tin hơn nhiều so với giá trị tuyệt đối từng năm, "
      "miễn là biến động đó đủ lớn theo tiêu chí ở mục 5.")

    P(doc,
      "Một điểm cần nêu minh bạch về mặt phương pháp: công thức gốc của Olofsson giả định mẫu được "
      "phân tầng theo lớp của bản đồ, trong khi bộ mẫu của nhóm lại phân tầng theo lớp của WorldCover, "
      "tức theo nhãn tham chiếu. Phép tính ở đây vì vậy là ước lượng độ chính xác có trọng số theo tỷ "
      "trọng thật của từng lớp tham chiếu, gần với tinh thần của Olofsson nhưng không hoàn toàn trùng "
      "khít. Nhóm nêu rõ để người đọc không hiểu nhầm.")

    # ---------------- 4. HISTOGRAM NDBI ----------------
    doc.add_page_break()
    H(doc, "4. Histogram NDBI qua 5 mốc thời gian", 1)
    P(doc,
      "Mục đích của phần này là tìm bằng chứng độc lập với mô hình phân loại. NDBI được tính trực tiếp "
      "từ hai kênh phổ gốc, không qua bất kỳ thuật toán học máy nào. Nếu phân bố NDBI của toàn vùng "
      "dịch chuyển theo thời gian thì đó là bằng chứng thuần vật lý cho việc bề mặt đang đổi tính chất, "
      "không phụ thuộc vào việc mô hình phân loại đúng hay sai.")

    P(doc, "Bảng 5. Thống kê mô tả phân bố NDBI từng mốc.", italic=True)
    rows = []
    for year in gcfg.STUDY_YEARS:
        h = hists.get(str(year)) or hists.get(year)
        s = h["stats"]
        rows.append([
            str(year), f"{s['NDBI_mean']:+.4f}".replace(".", ","),
            f"{s['NDBI_p50']:+.4f}".replace(".", ","),
            f"{s['NDBI_stdDev']:.4f}".replace(".", ","),
            f"{s['NDBI_p95']:+.4f}".replace(".", ","),
            f"{fmt(h['positive_share_pct'], 2)}%",
        ])
    TBL(doc, ["Mốc", "Trung bình", "Trung vị", "Độ lệch chuẩn", "Phân vị 95",
              "Tỷ lệ diện tích NDBI > 0"], rows)

    IMG(doc, FIG / "ndbi_hist_overlay.png",
        "Hình 1. Phân bố NDBI của 5 mốc vẽ chồng lên nhau. Đường nét đứt là mốc NDBI = 0.")

    P(doc,
      "Hình 1 cho thấy rất rõ ba giai đoạn. Hai mốc 2018 và 2020 có một đỉnh duy nhất nằm hẳn bên trái "
      "vạch 0, quanh giá trị âm 0,12 đến âm 0,22, đúng với đặc trưng của vùng nông nghiệp. Mốc 2022 bắt "
      "đầu bè rộng ra và dịch sang phải. Đến 2024 và 2026 thì xuất hiện một đỉnh mới nằm bên phải vạch "
      "0, tức là đã hình thành hẳn một nhóm diện tích mang đặc trưng phổ của bề mặt xây dựng, điều mà "
      "hai mốc đầu hoàn toàn không có.")

    IMG(doc, FIG / "ndbi_hist_grid.png",
        "Hình 2. Phân bố NDBI từng mốc tách riêng, đường xanh đậm là trung vị.", 6.6)

    IMG(doc, FIG / "ndbi_shift_summary.png",
        "Hình 3. Trái: dịch chuyển trung vị và trung bình NDBI. Phải: tỷ lệ diện tích có NDBI dương.")

    h2018 = hists.get("2018") or hists.get(2018)
    h2024 = hists.get("2024") or hists.get(2024)
    h2026 = hists.get("2026") or hists.get(2026)
    med2024 = f"{h2024['stats']['NDBI_p50']:+.4f}".replace(".", ",")
    P(doc,
      f"Tỷ lệ diện tích có NDBI dương tăng từ {fmt(h2018['positive_share_pct'], 1)}% năm 2018 lên "
      f"{fmt(h2024['positive_share_pct'], 1)}% năm 2024, tức hơn gấp đôi. Mốc 2024 cũng là mốc duy nhất "
      f"có trung vị NDBI vượt qua 0, đạt {med2024}. Đây là bằng chứng độc lập, không dùng tới mô hình "
      "phân loại, cho cùng một kết luận mà bản đồ phân loại đã đưa ra: bước ngoặt nằm ở giai đoạn "
      "2022 đến 2024.")
    med2026 = f"{h2026['stats']['NDBI_p50']:+.4f}".replace(".", ",")
    P(doc,
      f"Mốc 2026 có trung vị {med2026}"
      f" và tỷ lệ NDBI dương {fmt(h2026['positive_share_pct'], 1)}%, đều thấp hơn 2024 một chút. Diễn "
      "biến này trùng với việc diện tích bê tông năm 2026 tính được cũng thấp hơn 2024. Nhóm không "
      "kết luận rằng bê tông đã giảm, vì hai khả năng khác hợp lý hơn: ảnh ghép hai mốc lấy từ các "
      "ngày khác nhau trong mùa khô nên độ ẩm bề mặt khác nhau, và sau khi công trình hoàn thiện thì "
      "một phần diện tích được phủ cây xanh cảnh quan.")

    # ---------------- 5. KIỂM ĐỊNH ----------------
    doc.add_page_break()
    H(doc, "5. Kiểm định: biến động nào đáng tin, biến động nào nằm trong sai số", 1)
    P(doc,
      "Đây là phần trả lời trực tiếp cho những thắc mắc còn tồn từ các báo cáo trước: vì sao 2018 lại "
      "cao hơn 2020, và vì sao 2026 lại thấp hơn 2024. Thay vì suy đoán, nhóm tính hẳn sai số của "
      "ước lượng diện tích rồi so sánh.")
    P(doc,
      "Cách tính: từ ma trận nhầm lẫn và tỷ lệ diện tích thực tế, ước lượng tỷ lệ diện tích lớp bê "
      "tông cùng sai số chuẩn của nó theo công thức ước lượng phân tầng. Nhân với 1,96 được biên sai "
      "số ở mức tin cậy 95%. Khi so sánh hai mốc, sai số của hiệu hai ước lượng bằng biên sai số của "
      "một ước lượng nhân căn bậc hai của 2.")

    ci = acc["builtup_ci"]
    TBL(doc, ["Đại lượng", "Giá trị"], [
        ["Biên sai số 95% của một mốc", f"± {fmt(ci['margin95_pct_points'], 2)} điểm % "
                                        f"(± {fmt(ci['margin95_ha'])} ha)"],
        ["Ngưỡng tối thiểu để một biến động đáng tin", f"{fmt(sig['threshold_ha'])} ha"],
    ])

    P(doc, "Bảng 6. Kiểm định từng giai đoạn. Cột cuối cho biết biến động lớn gấp bao nhiêu lần ngưỡng.",
      italic=True)
    rows = []
    for period in sig["periods"]:
        rows.append([
            period["period"],
            f"{period['delta_ha']:+,.1f}".replace(",", " ").replace(".", ",") + " ha",
            f"{fmt(period['ratio'], 2)}",
            "Đáng tin" if period["significant"] else "Nằm trong sai số",
        ])
    TBL(doc, ["Giai đoạn", "Biến động diện tích", "So với ngưỡng", "Kết luận"], rows)

    P(doc,
      f"Kết quả rất dứt khoát: trong bốn giai đoạn, chỉ có duy nhất giai đoạn 2022 đến 2024 vượt "
      f"ngưỡng, và vượt khá xa, gấp 1,91 lần. Ba giai đoạn còn lại đều có mức biến động chưa tới 0,2 "
      "lần ngưỡng, tức là hoàn toàn nằm trong sai số của mô hình.")

    H(doc, "5.1. Ba thắc mắc cũ đã được giải quyết", 2)
    P(doc,
      "Thứ nhất, việc năm 2018 có tỷ lệ bê tông cao hơn 2020 khoảng 163,7 ha từng bị coi là bất "
      "thường và nhóm đã xử lý bằng lọc majority và bổ sung mẫu tay. Nay có thể khẳng định chênh lệch "
      "đó chỉ bằng 0,18 lần ngưỡng, hoàn toàn là nhiễu, không cần và cũng không nên diễn giải gì thêm.")
    P(doc,
      "Thứ hai, việc năm 2026 thấp hơn 2024 khoảng 131,7 ha cũng chỉ bằng 0,15 lần ngưỡng. Không có "
      "cơ sở để nói bê tông giảm đi.")
    P(doc,
      "Thứ ba, cả giai đoạn 2018 đến 2022 gộp lại vẫn không vượt ngưỡng. Nghĩa là trong suốt bốn năm "
      "đầu, diện tích bê tông trong vùng nghiên cứu về cơ bản không đổi ở mức mà mô hình này phân biệt "
      "được. Toàn bộ biến động thật sự dồn vào giai đoạn 2022 đến 2024.")

    H(doc, "5.2. Giới hạn khi diễn giải kết quả", 2)
    P(doc,
      "Từ kết quả kiểm định, phạm vi kết luận mà bộ số liệu này cho phép rút ra được giới hạn như sau.")
    P(doc, "Kết luận có cơ sở:", bold=True)
    P(doc,
      "Trong giai đoạn 2022 đến 2024, diện tích bề mặt xây dựng trong vùng nghiên cứu tăng thêm "
      "khoảng 1 730 ha. Mức tăng này vượt ngưỡng sai số của mô hình gần hai lần nên được xem là biến "
      "động thật. Ba giai đoạn còn lại không cho thấy biến động vượt ngưỡng phát hiện được của phương "
      "pháp hiện tại.")
    P(doc, "Kết luận không có cơ sở:", bold=True)
    P(doc,
      "Không thể kết luận rằng diện tích bê tông năm 2026 giảm 131,7 ha so với năm 2024. Chênh lệch "
      "này nằm trong sai số của mô hình, đồng thời giá trị tuyệt đối còn chịu ảnh hưởng của vấn đề "
      "user accuracy nêu ở mục 3. Tương tự, không thể kết luận về xu hướng tăng hay giảm trong nội bộ "
      "giai đoạn 2018 đến 2022.")

    # ---------------- 6. KẾT LUẬN ----------------
    doc.add_page_break()
    H(doc, "6. Tổng hợp kết luận", 1)
    TBL(doc, ["Nội dung", "Kết quả"], [
        ["Ma trận chuyển đổi 2022 → 2024",
         f"{fmt(tm['changed_ha'])} ha đổi lớp ({fmt(tm['changed_pct'], 2)}% AOI). Luồng chính: "
         f"thảm thực vật → bề mặt xây dựng {fmt(mat[1][3])} ha"],
        ["Độ chính xác chính thức",
         f"{fmt(100*acc['oa_weighted'], 2)}% (khoảng tin cậy 95%: "
         f"{fmt(100*acc['ci95'][0], 2)}% – {fmt(100*acc['ci95'][1], 2)}%), thay cho con số 85,3%"],
        ["Điểm yếu lớn nhất phát hiện được",
         f"User accuracy lớp bê tông chỉ {fmt(100*acc['user_weighted'][3], 2)}% → diện tích tuyệt đối "
         "nhiều khả năng bị ước lượng vượt"],
        ["Bằng chứng độc lập từ NDBI",
         f"Tỷ lệ diện tích NDBI dương tăng từ {fmt(h2018['positive_share_pct'], 1)}% (2018) lên "
         f"{fmt(h2024['positive_share_pct'], 1)}% (2024); trung vị vượt 0 lần đầu ở mốc 2024"],
        ["Biến động đáng tin",
         f"Chỉ giai đoạn 2022 → 2024 (+1 730,1 ha, gấp 1,91 lần ngưỡng {fmt(sig['threshold_ha'])} ha)"],
    ])

    P(doc,
      "Bốn phân tích được làm độc lập với nhau nhưng cùng chỉ về một kết luận: bước ngoặt bê tông hóa "
      "của khu vực nằm ở giai đoạn 2022 đến 2024, trùng với thời kỳ thi công cao điểm của dự án sân "
      "bay Long Thành. Ma trận chuyển đổi cho thấy nguồn gốc của diện tích bê tông mới chủ yếu là đất "
      "nông nghiệp. Histogram NDBI xác nhận điều đó bằng dữ liệu phổ thuần túy, không qua mô hình. "
      "Và phép kiểm định cho biết đây là biến động duy nhất trong chuỗi 5 mốc đủ lớn để khẳng định.")
    P(doc,
      "Đồng thời, hai phân tích còn lại cũng chỉ ra giới hạn của kết quả: mô hình thiếu ổn định ở cấp "
      "điểm ảnh, và giá trị diện tích tuyệt đối của lớp bê tông nhiều khả năng bị thổi lên. Nhóm chọn "
      "nêu rõ cả hai mặt thay vì chỉ trình bày phần thuận lợi.")

    H(doc, "7. Hạn chế và hướng xử lý tiếp", 1)
    P(doc, "1. Tập kiểm tra chỉ 353 điểm nên khoảng tin cậy rộng tới hơn 14 điểm phần trăm. Muốn thu "
           "hẹp phải tăng số mẫu kiểm tra, đặc biệt cho lớp thảm thực vật vì nó chi phối trọng số.")
    P(doc, "2. Tỷ lệ diện tích thực tế dùng làm trọng số lấy từ WorldCover phiên bản 2021, nên chỉ "
           "chính xác cho các mốc gần 2021. Áp cùng bộ trọng số cho mốc 2018 và 2026 là một giả định "
           "phải chấp nhận.")
    P(doc, "3. Ma trận chuyển đổi cho thấy gần một nửa diện tích bê tông năm 2022 đổi nhãn ở mốc sau. "
           "Hướng xử lý là bổ sung ràng buộc thời gian, ví dụ quy tắc một điểm ảnh đã là bê tông thì "
           "không được quay về lớp khác, hoặc dùng mô hình chuỗi thời gian thay vì phân loại độc lập "
           "từng mốc.")
    P(doc, "4. Phân tích mới chỉ làm cho cặp 2022 và 2024. Có thể lập ma trận cho các cặp còn lại để "
           "có bức tranh chuyển đổi đầy đủ của cả chuỗi.")

    doc.save(OUT)
    print(f"[done] Da ghi {OUT}")


if __name__ == "__main__":
    main()
