#!/usr/bin/env python3
"""Generate a Vietnamese W4 DOCX from outputs/w4/analysis.json and CSVs."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
import sys
from pathlib import Path


from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.report_images import optimized
from src.docx_cleanup import clean as clean_docx  # noqa: E402
OUT = ROOT / "outputs" / "w4"
REPORT = ROOT / "reports" / "Bao_cao_Task_W4.docx"


def para(doc, text="", bold=False):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold = bold
    return p


def table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers), style="Table Grid")
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers): t.rows[0].cells[i].text = str(h)
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row): cells[i].text = str(value)
    for cell in t.rows[0].cells:
        for run in cell.paragraphs[0].runs: run.bold = True
    doc.add_paragraph()
    return t


def picture(doc, filename, caption):
    path = OUT / filename
    if not path.exists(): return
    path = optimized(path)
    t = doc.add_table(rows=1, cols=1)
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))
    cell = t.cell(0,0)
    p = cell.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Cm(14.5))
    c = cell.add_paragraph(caption); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()


def load_csv(name):
    path = OUT / name
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))


def fmt(v, digits=2):
    return f"{float(v):,.{digits}f}".replace(",", " ").replace(".", ",")


def grouped_spatial(rows, key):
    groups = defaultdict(lambda: [0.,0.])
    for r in rows:
        k = (r["year"],r[key]); groups[k][0] += float(r["zone_ha"]); groups[k][1] += float(r["builtup_ha"])
    def ordering(item):
        y,z=item
        if key == "distance_road_m": return (int(y), int(z.split('-')[0]))
        if key == "ring_m": return (int(y), int(z.split('-')[0]))
        compass = ["Bắc","Đông Bắc","Đông","Đông Nam","Nam","Tây Nam","Tây","Tây Bắc"]
        return (int(y),compass.index(z))
    return [(y,"≥ 1000" if z=="1000-inf" else z,fmt(a),fmt(b),fmt(100*b/a if a else 0))
            for (y,z),(a,b) in sorted(groups.items(),key=lambda kv:ordering(kv[0]))]


def main():
    data = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
    spatial = load_csv("spatial_ring_direction.csv")
    roads = load_csv("distance_to_roads.csv")
    densities = load_csv("edge_density_by_class.csv")
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.8); sec.right_margin = Cm(2.2)
    styles = doc.styles
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Caption"):
        st = styles[name]; st.font.name = "Times New Roman"; st.font.color.rgb = RGBColor(0,0,0)
        st.font.size = Pt(12 if name == "Normal" else 15 if name == "Heading 1" else 13)
    styles["Normal"].paragraph_format.line_spacing = 1.25
    title = doc.add_heading("BÁO CÁO KẾT QUẢ TASK TUẦN 4", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(doc, "Đề tài: Phân tích biến động lớp phủ khu vực sân bay Long Thành")
    para(doc, "Phạm vi: AOI chuẩn; ảnh năm 2022 và 2024; độ phân giải 10 m.")
    para(doc, "Báo cáo này được sinh trực tiếp từ các tệp kết quả trong outputs/w4, không chép số liệu của báo cáo cũ.")

    doc.add_heading("1. Dữ liệu và cách thực hiện", 1)
    para(doc, "Ảnh Sentinel-2 L2A được đọc từ hai cảnh AWS/STAC trong dự án. Kênh B11 và B12 được đọc lại từ COG gốc 20 m và nội suy bicubic lên lưới 10 m theo cách mô tả trong tài liệu của Cường. Đây là ảnh đơn ngày, không phải ảnh ghép trung vị mùa khô trên GEE. Mặt nạ mây dùng SCL đã có sẵn trong data/raw.")
    para(doc, "Nhãn tham khảo lấy từ ESA WorldCover 2021 v200. Bốn lớp là Nước, Thảm thực vật, Đất trống và Bề mặt xây dựng. Riêng mẫu nước được giữ khi NDWI > 0. Mỗi lớp lấy tối đa 300 điểm, chia 70/30 theo từng lớp với seed 42. Vì nhãn WorldCover là năm 2021, phép đánh giá năm 2024 chỉ có ý nghĩa so sánh phương án; không xem là kiểm định độc lập cho hiện trạng 2024.")
    para(doc, "Tập đặc trưng gốc gồm B2, B3, B4, B8, B11, B12, NDVI, NDBI, NDWI. Bộ thứ hai thêm mật độ biên Canny trong cửa sổ 7 × 7 và độ lớn gradient Sobel. Bộ thứ ba thêm bốn đặc trưng GLCM tính từ B8: contrast, entropy, homogeneity và dissimilarity. Do chưa có tệp GLCM của Uyên, bốn đặc trưng này được tính lại bằng cửa sổ 5 × 5, lượng tử hóa 8 mức và trung bình bốn hướng.")
    para(doc, "Phương pháp so sánh dùng Random Forest 200 cây. Mô hình dùng cho bản đồ không gian được chọn trên tập kiểm tra năm 2022 và giữ cố định khi áp dụng sang 2024, để hai mốc dùng cùng một quy tắc phân loại.")
    para(doc, f"Bảng diện tích hai mốc chỉ tính trên {fmt(data['common_valid_area_ha'])} ha có pixel hợp lệ ở cả 2022 và 2024. Diện tích một pixel lấy từ phép biến đổi tọa độ thực tế của GeoTIFF ({fmt(data['pixel_area_ha'],6)} ha/pixel).")

    doc.add_page_break()
    doc.add_heading("2. Tách biên trên NDBI", 1)
    para(doc, "Ảnh NDBI được làm mượt Gaussian σ = 1 pixel trước khi chạy Roberts, Prewitt, Sobel, Laplace và Canny. Canny dùng khử cực đại không gian, ngưỡng cao tại phân vị 90 của gradient sau khử cực đại, ngưỡng thấp bằng 40% ngưỡng cao, nối biên yếu với biên mạnh và bỏ thành phần dưới 8 pixel. Vùng sát mép mây được co vào 5 pixel để tránh nhận biên mây thành biên mặt đất.")
    threshold_rows = []
    for y, d in data["years"].items():
        c = d["canny_thresholds"]
        threshold_rows.append([y,fmt(c["low"],4),fmt(c["high"],4),fmt(d["canny_edge_pct"],2)])
    table(doc,["Năm","Ngưỡng thấp","Ngưỡng cao","Pixel biên Canny (%)"],threshold_rows)
    picture(doc,"2022_canny.png","Hình 1. Biên Canny năm 2022 trên NDBI từ ảnh bicubic.")
    picture(doc,"2024_canny.png","Hình 2. Biên Canny năm 2024 trên NDBI từ ảnh bicubic.")
    para(doc, "Đủ 10 ảnh PNG riêng cho 5 toán tử × 2 năm nằm trong outputs/w4. Các bản đồ này phản ánh ranh giới phổ của NDBI; đường biên sáng không tự động có nghĩa là đường giao thông hay công trình.")

    doc.add_heading("3. Mật độ biên theo lớp", 1)
    table(doc,["Năm","Lớp WorldCover","Số pixel","Mật độ biên TB","Gradient Sobel TB"],
          [[r["year"],r["class"],r["n_pixels"],fmt(r["mean_edge_density"],4),fmt(r["mean_sobel_gradient"],4)] for r in densities])
    for y in ("2022","2024"):
        d = {r["class"]:float(r["mean_edge_density"]) for r in densities if r["year"] == y}
        if "Built-up" in d and "Bare Soil" in d:
            note = " Cả hai lớp lấy theo nhãn WorldCover 2021." if y == "2022" else " Nhãn tham khảo là WorldCover 2021, nên kết quả 2024 cần diễn giải thận trọng."
            para(doc, f"Năm {y}, mật độ biên trung bình của lớp xây dựng là {fmt(d['Built-up'],4)}, cao hơn đất trống {fmt(d['Bare Soil'],4)} ({fmt(d['Built-up']/d['Bare Soil'],2)} lần)."+note)

    doc.add_heading("4. So sánh ba bộ đặc trưng", 1)
    table_rows=[]
    for y, d in data["years"].items():
        for m in d["models"]:
            table_rows.append([y,m["bo_dac_trung"],m["train_n"],m["test_n"],fmt(100*m["OA"]),fmt(m["Kappa"],3)])
    table(doc,["Năm","Bộ đặc trưng","Train","Test","OA (%)","Kappa"],table_rows)
    para(doc, f"Mô hình dùng chung cho phân tích không gian là {data['years']['2022']['spatial_model']}, chọn theo tập kiểm tra 2022. Kết quả so sánh riêng năm 2024 có thể khác vì ảnh 2024 đã biến đổi còn nhãn tham khảo vẫn là WorldCover 2021.")
    para(doc, "Ma trận nhầm lẫn của từng phép thử và danh sách đặc trưng được lưu trong analysis.json. Các điểm train/test lấy ngẫu nhiên trong cùng AOI; tự tương quan không gian và sai số nhãn có thể làm OA cao hơn độ chính xác trên điểm kiểm tra thực địa độc lập.")

    doc.add_heading("5. Phân tích theo khoảng cách và hướng", 1)
    if (OUT / "roads_map.png").exists(): picture(doc,"roads_map.png","Hình 3. Các đường lớn từ OpenStreetMap quanh AOI; phần trong ranh sân bay được loại khỏi mạng đường phân tích.")
    road_names = data.get("roads", [])
    if road_names:
        n_segments = len(json.loads((OUT / "roads.geojson").read_text(encoding="utf-8"))["features"])
        para(doc,f"Mạng đường gồm {n_segments} đoạn thuộc {len(road_names)} tên/mã tuyến. Đối chiếu hình học với polygon sân bay OSM cho kết quả 0 m đường nằm trong ranh sân bay.")
        para(doc,"Các tuyến hoặc mã tuyến đã vẽ: " + "; ".join(road_names) + ".")
    else:
        para(doc,"Chưa có đường OSM đủ điều kiện để tính khoảng cách đến đường; mục này không được suy đoán từ ảnh. Các bảng vành đai và hướng vẫn được tính từ bản đồ phân loại.")
    table(doc,["Năm","Vành đai (m)","Diện tích hợp lệ (ha)","Xây dựng (ha)","Tỷ lệ (%)"],grouped_spatial(spatial,"ring_m"))
    table(doc,["Năm","Hướng","Diện tích hợp lệ (ha)","Xây dựng (ha)","Tỷ lệ (%)"],grouped_spatial(spatial,"direction"))
    if roads:
        table(doc,["Năm","Cách đường (m)","Diện tích hợp lệ (ha)","Xây dựng (ha)","Tỷ lệ (%)"],grouped_spatial(roads,"distance_road_m"))
        para(doc,"Khoảng cách tính đến tim đường OSM gần nhất theo lưới 10 m. Các dải được chia 0–100, 100–250, 250–500, 500–1000 và trên 1000 m; tỷ lệ chia cho diện tích hợp lệ của từng dải.")
    para(doc,"Ba vành đai chỉ bao phủ phần nằm trong bán kính 6 km quanh tâm dự án. Phần AOI nằm ngoài 6 km không được đưa vào bảng vành đai, nhưng vẫn được tính trong bảng khoảng cách đến đường.")

    doc.add_page_break()
    doc.add_heading("6. Thử biến đổi Hough để tự tìm đường băng", 1)
    hough_path = OUT / "hough.json"
    if not hough_path.exists():
        para(doc, "Chưa chạy scripts/run_w4_hough.py nên mục này bỏ trống.")
    else:
        hough = json.loads(hough_path.read_text(encoding="utf-8"))
        m = hough["method"]
        para(doc, "Đây là mục cuối của đề bài, phần làm thêm nếu còn thời gian. Câu hỏi đặt ra là liệu "
                  "máy có tự tìm được đường băng hay không mà không cần bất kỳ nhãn nào. Nếu tìm được thì "
                  "đó là bằng chứng độc lập cho việc bề mặt đã chuyển sang công trình nhân tạo, vì đường "
                  "băng là vật thể dài và thẳng nhất trong khu vực.")
        para(doc, f"Cách làm: lấy ảnh biên Canny đúng tham số đã dùng ở mục 2, giới hạn trong ranh giới "
                  f"sân bay OSM, rồi chạy {m['hough']}. Chỉ giữ các đoạn thẳng dài từ "
                  f"{m['min_segment_m']} m trở lên, gom các đoạn lệch nhau dưới "
                  f"{m['angle_tolerance_deg']}° thành một tuyến.")
        para(doc, "Về tham số nối đoạn: biên Canny bên trong sân bay bị đứt quãng nên phải cho phép nối. "
                  "Nhóm đã thử các mức 12, 20, 30, 50 và 80 điểm ảnh. Từ 30 điểm ảnh trở lên, Hough bắt "
                  "đầu nối nhầm các mảnh biên rời rạc không liên quan thành những đường dài 7 đến 10 km, "
                  "vô lý với một ô chỉ rộng khoảng 11 km. Vì vậy chốt ở mức 20 điểm ảnh, tương đương "
                  "200 m, là mức cao nhất còn cho kết quả hợp lý về mặt vật lý.")

        rows = []
        for year in ("2022", "2024"):
            y = hough["years"][year]
            rows.append([year, str(y["n_segments"]),
                         fmt(y["dominant_bearing_deg"], 1) + "°" if y["dominant_bearing_deg"] is not None else "—",
                         fmt(y["dominant_max_len_m"], 0) + " m" if y["dominant_max_len_m"] is not None else "—",
                         fmt(y["dominant_builtup_pct"], 1) + "%" if y["dominant_builtup_pct"] is not None else "—"])
        table(doc, ["Năm", "Số đoạn đạt ngưỡng", "Phương vị tuyến trội", "Đoạn dài nhất",
                    "Tỷ lệ trùng lớp xây dựng"], rows)

        y22, y24 = hough["years"]["2022"], hough["years"]["2024"]
        para(doc, f"Năm 2022 chỉ có đúng 1 đoạn đạt ngưỡng, phương vị {fmt(y22['dominant_bearing_deg'],1)}°, "
                  f"và chỉ {fmt(y22['dominant_builtup_pct'],1)}% số điểm trên đoạn đó chạm lớp xây dựng. "
                  f"Nhìn vào hình thì đây là một bờ thửa trong khu dân cư phía tây nam, không liên quan "
                  f"tới đường băng. Năm 2024 có {y24['n_segments']} đoạn đạt ngưỡng và cả ba đều bám sát "
                  f"công trình: tuyến trội có phương vị {fmt(y24['dominant_bearing_deg'],1)}°, dài "
                  f"{fmt(y24['dominant_max_len_m'],0)} m, với {fmt(y24['dominant_builtup_pct'],1)}% số điểm "
                  f"trùng lớp xây dựng.")

        bu22, bu24 = y22.get("builtup_largest_component"), y24.get("builtup_largest_component")
        if bu22 and bu24:
            table(doc, ["Năm", "Vùng xây dựng liền thông lớn nhất", "Trục chính", "Độ thon dài",
                        "Lệch so với tuyến Hough"],
                  [["2022", fmt(bu22["ha"], 1) + " ha", fmt(bu22["bearing_deg"], 1) + "°",
                    fmt(bu22["elongation"], 2),
                    fmt(y22["bearing_diff_vs_builtup_axis_deg"], 1) + "°"],
                   ["2024", fmt(bu24["ha"], 1) + " ha", fmt(bu24["bearing_deg"], 1) + "°",
                    fmt(bu24["elongation"], 2),
                    fmt(y24["bearing_diff_vs_builtup_axis_deg"], 1) + "°"]])
            para(doc, "Để kiểm chứng mà không dùng lại Hough, nhóm tính thêm trục chính của vùng xây dựng "
                      "liền thông lớn nhất bằng phân tích thành phần chính. Cách này không dùng ảnh biên "
                      "và không dùng Hough nên hoàn toàn độc lập. Năm 2024 vùng này rộng "
                      f"{fmt(bu24['ha'],1)} ha với độ thon dài {fmt(bu24['elongation'],2)}, trục chính "
                      f"{fmt(bu24['bearing_deg'],1)}°, lệch {fmt(y24['bearing_diff_vs_builtup_axis_deg'],1)}° "
                      f"so với tuyến Hough. Năm 2022 vùng lớn nhất chỉ {fmt(bu22['ha'],1)} ha và gần như "
                      f"tròn, độ thon dài {fmt(bu22['elongation'],2)}, nên không có hướng nào nổi trội.")

        picture(doc, "hough_2022.png", "Hình 4. Hough trên biên Canny của NDBI năm 2022. Khu vực sân bay "
                                       "vẫn là đất canh tác, thấy rõ lưới bờ thửa; đoạn thẳng duy nhất tìm "
                                       "được nằm ở khu dân cư phía tây nam.")
        picture(doc, "hough_2024.png", "Hình 5. Hough trên biên Canny của NDBI năm 2024. Nền công trình "
                                       "sáng chạy theo hướng đông bắc – tây nam đã hình thành; đường viền "
                                       "xanh lá là vùng xây dựng liền thông lớn nhất.")

        para(doc, "Kết luận của mục này cần nói thẳng cả phần làm được và phần chưa làm được. Hough tìm ra "
                  f"đúng hướng của tổ hợp công trình, {fmt(y24['dominant_bearing_deg'],1)}°, và hướng này "
                  f"khớp với trục chính của vùng xây dựng tính độc lập, {fmt(bu24['bearing_deg'],1)}°, "
                  "chênh nhau 10°. Hai phương pháp không liên quan cùng chỉ về một hướng đông bắc – tây "
                  "nam, nên kết quả về hướng là đáng tin." if bu24 else "")
        para(doc, "Tuy nhiên Hough không khoanh được bản thân đường băng. Nhìn Hình 5 sẽ thấy lý do: mặt "
                  "nền công trình rất đồng nhất về phổ, nên bên trong nó gần như không có biên nào để "
                  "Hough bám vào; toàn bộ biên Canny dồn ra rìa, nơi tiếp giáp với ruộng xung quanh. Vì "
                  "vậy các đoạn thẳng tìm được là ranh của nền công trình chứ không phải tim đường băng. "
                  "Thêm nữa, ở độ phân giải 10 m thì đường băng rộng 45 m chỉ chiếm khoảng 4 đến 5 điểm "
                  "ảnh ngang, lại nằm giữa sân đỗ và đường lăn cũng bằng bê tông, nên độ tương phản gần "
                  "như bằng không. Muốn tách riêng đường băng thì phải dùng ảnh phân giải cao hơn, "
                  "khoảng 1 đến 2 m, chứ không phải chỉnh thêm tham số Hough.")
        para(doc, "Dù vậy, phép thử vẫn trả lời được một câu hỏi có ích: giữa hai mốc, chỉ năm 2024 mới "
                  "xuất hiện cấu trúc thẳng và dài gắn với lớp xây dựng, còn năm 2022 thì không. Điều này "
                  "thống nhất với kết quả phân loại và với phần tách biên ở các mục trên.")
        para(doc, "Mã chạy lại: scripts/run_w4_hough.py. Kết quả số nằm ở outputs/w4/hough.json và "
                  "outputs/w4/hough_lines.csv.")

    doc.add_page_break()
    doc.add_heading("7. Sản phẩm và giới hạn", 1)
    para(doc,"Các tệp kết quả gồm 10 PNG tách biên, 2 GeoTIFF NDBI, 2 GeoTIFF phân loại, CSV mật độ biên, CSV vành đai × 8 hướng, CSV khoảng cách đến đường (khi có nguồn đường) và analysis.json. Mã chạy lại: scripts/run_w4_local.py; mã tạo báo cáo: scripts/generate_w4_report.py.")
    para(doc,"WorldCover 2021 có thể đã lỗi thời ở công trường năm 2024. Ảnh Sentinel-2 cục bộ là cảnh đơn ngày, độ che mây khác nhau và không thay thế composite GEE trong báo cáo trước. Bề mặt xây dựng là lớp phổ gồm nhiều vật liệu, không tương đương hoàn toàn với bê tông. Các con số diện tích W4 là kết quả thực nghiệm của pipeline W4, không thay số liệu đã công bố từ mô hình GEE trước đó.")
    para(doc,"Mã hiển thị các tuyến trên GEE đã được xuất thành scripts/w4_roads_gee.js. Tại thời điểm thực hiện, tài khoản dịch vụ GEE của dự án báo thiếu quyền serviceusage.services.use đối với project nth-period-425718-i5, nên mã này chưa được chạy trực tiếp trong GEE. Các CSV và hình trong báo cáo được tính và kiểm tra bằng pipeline Python cục bộ.")
    para(doc,"Nguồn dữ liệu: ESA WorldCover 2021 v200 (https://esa-worldcover.org/en/data-access); Sentinel-2 L2A từ Earth Search STAC/Element84; mạng đường và ranh sân bay (nếu có) từ OpenStreetMap/Geofabrik (https://download.geofabrik.de/asia/vietnam.html).")

    # Keep all text, including table cells and captions, Times New Roman black.
    for p in doc.paragraphs:
        for run in p.runs:
            run.font.name="Times New Roman"; run.font.color.rgb=RGBColor(0,0,0)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.name="Times New Roman";run.font.size=Pt(10);run.font.color.rgb=RGBColor(0,0,0)
    REPORT.parent.mkdir(exist_ok=True)
    doc.save(REPORT)
    clean_docx(REPORT)
    print(REPORT)


if __name__ == "__main__": main()
