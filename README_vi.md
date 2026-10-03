# Biến động Phát triển Khu vực: Đo lường tốc độ "Bê tông hóa" đại dự án Sân bay Long Thành & Vùng phụ cận (2018–2026)

Phân loại lớp phủ bề mặt (land cover) và phân tích tốc độ mở rộng khu vực xây dựng/bê tông hóa quanh **Cảng hàng không quốc tế Long Thành**, tỉnh Đồng Nai, Việt Nam, sử dụng ảnh vệ tinh đa thời gian Sentinel-2 (2018–2026).

Pipeline tổng thể của toàn bộ dự án:

```
Ảnh vệ tinh -> Tiền xử lý dữ liệu -> EDA -> Mẫu huấn luyện ->
Phân loại Random Forest -> Đánh giá độ chính xác -> Phát hiện biến động ->
Phân tích khu vực xây dựng -> Phân tích vùng đệm -> Tốc độ bê tông hóa
```

## Trạng thái hiện tại: Phase 1 (Tiền xử lý dữ liệu + EDA)

Repository này hiện chỉ triển khai **Phase 1**: kiểm tra chất lượng dữ liệu, tiền xử lý (xử lý giá trị thiếu/không hợp lệ, che mây tùy chọn, cắt theo ranh giới khu vực nghiên cứu - AOI), tính toán các chỉ số phổ (NDVI/NDBI/NDWI), và phân tích khám phá dữ liệu (EDA). Việc huấn luyện Random Forest, đánh giá độ chính xác, phát hiện biến động và tính tốc độ bê tông hóa **chưa** thuộc phạm vi của phase này.

**Hiện tại repository chưa có bất kỳ ảnh vệ tinh thực tế nào.** Phần code của pipeline đã hoàn chỉnh và đã được kiểm thử toàn trình (end-to-end) bằng một raster tổng hợp (synthetic) — chạy `pytest tests/test_pipeline_smoke.py` cho kết quả 6/6 test PASSED — nhưng lệnh `python scripts/run_pipeline.py` hiện tại chỉ tạo ra một báo cáo tình trạng (status report) trung thực thay vì số liệu giả định. Xem chi tiết tại [`reports/Phase_1_Data_Preprocessing_and_EDA.md`](reports/Phase_1_Data_Preprocessing_and_EDA.md) và hướng dẫn thêm dữ liệu tại [`data/raw/README.md`](data/raw/README.md).

## Cấu trúc project

```text
project/
│
├── data/
│   ├── raw/            # Ảnh GeoTIFF Sentinel-2 theo từng năm (xem data/raw/README.md); hiện đang trống
│   ├── processed/      # Raster đã cắt theo AOI + feature_dataset.csv, được pipeline sinh ra
│   └── samples/        # Mẫu huấn luyện có nhãn (tùy chọn, xem data/samples/README.md)
│
├── notebooks/
│   └── 01_preprocessing_eda.ipynb   # Notebook trình bày từng bước của pipeline Phase 1
│
├── src/
│   ├── config.py         # Đường dẫn, tên band, năm nghiên cứu, hằng số (nguồn cấu hình duy nhất)
│   ├── validation.py      # Kiểm tra file/metadata, thống kê band theo khối (chunk), sinh báo cáo QC
│   ├── preprocessing.py   # Phân loại tính hợp lệ của pixel, lấy mẫu reservoir, cắt theo AOI
│   ├── features.py        # Tính NDVI/NDBI/NDWI (chia an toàn), tạo bảng dữ liệu đặc trưng
│   └── visualization.py   # Toàn bộ các hàm sinh biểu đồ
│
├── scripts/
│   └── run_pipeline.py    # Điều phối toàn bộ pipeline và tự động sinh lại báo cáo Markdown
│
├── outputs/
│   ├── figures/            # Toàn bộ hình ảnh (PNG) được sinh ra
│   ├── statistics/         # Các bảng thống kê CSV (tổng quan, thống kê band, thống kê đặc trưng, xu hướng theo thời gian)
│   └── reports/             # Báo cáo QC dạng text theo từng năm (QC_<năm>.txt)
│
├── reports/
│   └── Phase_1_Data_Preprocessing_and_EDA.md   # Báo cáo Phase 1 (được sinh tự động)
│
├── tests/
│   └── test_pipeline_smoke.py   # Bộ kiểm thử toàn trình trên dữ liệu tổng hợp
│
├── requirements.txt
└── README.md / README_vi.md
```

## Cài đặt môi trường

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Thêm dữ liệu và chạy pipeline

1. Đọc [`data/raw/README.md`](data/raw/README.md) để biết định dạng file bắt buộc (1 file GeoTIFF 6 band cho mỗi năm, thứ tự band `B2, B3, B4, B8, B11, B12`).
2. Đặt ảnh vào `data/raw/`, có thể bổ sung ranh giới AOI (`data/raw/aoi_boundary.geojson`) và/hoặc điểm mẫu huấn luyện có nhãn trong `data/samples/` (xem [`data/samples/README.md`](data/samples/README.md)).
3. Chạy một trong hai lệnh sau:
   - `python scripts/run_pipeline.py` — tự động sinh lại toàn bộ hình ảnh, thống kê CSV, báo cáo QC theo từng năm, và báo cáo Markdown từ dữ liệu thật, hoặc
   - `jupyter nbconvert --to notebook --execute --inplace notebooks/01_preprocessing_eda.ipynb` — chạy lại notebook để có kết quả thật, hoặc mở bằng Jupyter và chạy từng cell.

Cả hai cách đều dùng chung các module trong `src/` và **không bao giờ tạo số liệu giả**: bất kỳ input nào còn thiếu (ảnh vệ tinh, AOI, mẫu huấn luyện) đều được báo cáo rõ ràng như một giới hạn (limitation) thay vì bị giả định hoặc bịa ra.

## Kiểm thử

```bash
pytest tests/test_pipeline_smoke.py -v
```

Bộ test tự tạo một raster tổng hợp nhỏ + AOI + điểm mẫu huấn luyện trong thư mục tạm, sau đó chạy toàn trình qua validation, tiền xử lý, feature engineering và visualization — đây là cách hiện tại để xác minh tính đúng đắn của pipeline khi chưa có ảnh vệ tinh thật.

## Ghi chú thiết kế

- **Tái sử dụng được cho nhiều năm:** mọi hàm trong `src/` đều nhận `year` làm tham số và được điều khiển bởi `src/config.py`, nên việc thêm một năm mới chỉ cần thêm file `data/raw/<năm>.tif`.
- **Giới hạn bộ nhớ (memory-bounded):** thống kê raster được tính theo khối (chunk/window); bảng dữ liệu đặc trưng được xây dựng từ một mẫu ngẫu nhiên kích thước cố định, lấy bằng thuật toán reservoir sampling dạng streaming (`src/preprocessing.py: ReservoirSampler`), nên không bao giờ phải nạp toàn bộ ảnh độ phân giải gốc nhiều band vào RAM.
- **Có thể tái lập (reproducible):** toàn bộ việc lấy mẫu ngẫu nhiên đều được cố định seed (`src/config.py: RANDOM_SEED`).
- **Không âm thầm mất dữ liệu:** số pixel thiếu/không hợp lệ/bị mây che/nằm ngoài AOI đều được đếm và báo cáo ở từng bước, không bị loại bỏ âm thầm.

## Bước tiếp theo

Khi có ảnh Sentinel-2 thật (và tốt nhất là kèm ranh giới AOI cùng mẫu huấn luyện), chạy lại `python scripts/run_pipeline.py` để pipeline tự động sinh số liệu, hình ảnh và báo cáo thật, làm cơ sở chuyển sang **Phase 2 – Phân loại Random Forest**.
## Phân tích tuần 4 (W4)

Ảnh W4 dùng hai cảnh Sentinel-2 L2A đơn ngày năm 2022 và 2024 trong `data/raw/`. Script đọc lại B11/B12 gốc 20 m từ STAC và nội suy bicubic lên lưới 10 m. Đây là thực nghiệm riêng, không thay thế composite GEE ở các báo cáo trước.

```bash
.venv/bin/python scripts/fetch_w4_osm.py
.venv/bin/python scripts/prepare_w4_roads.py
.venv/bin/python scripts/run_w4_local.py
.venv/bin/python scripts/generate_w4_report.py
```

Kết quả nằm trong `outputs/w4/`, báo cáo tại `reports/Bao_cao_Task_W4.docx`. File `scripts/w4_roads_gee.js` có thể dán vào GEE Code Editor để hiển thị các đường lớn ngoài ranh sân bay OSM. Khóa GEE, ảnh vệ tinh, dữ liệu OSM đã tải và báo cáo đều được loại khỏi Git.
