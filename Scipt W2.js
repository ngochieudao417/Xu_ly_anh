// Đo lường tốc độ bê tông hóa khu vực sân bay Long Thành giai đoạn 2018 tới 2026
// Nhóm 07, học phần Xử lý ảnh
// Script tổng hợp toàn bộ quy trình hai tuần đầu, chạy được từ trên xuống dưới


// Bước 1. Khai báo vùng nghiên cứu và các hằng số dùng chung

// Tâm dự án lấy tại tọa độ chính thức của sân bay Long Thành.
// Tọa độ này đã được kiểm chứng lại sau khi phát hiện giá trị dùng ban đầu
// lệch khoảng bốn tới năm ki lô mét về phía đông.
var SAN_BAY = ee.Geometry.Point([107.04111, 10.78444]);

// Vùng nghiên cứu cố định bằng tọa độ tuyệt đối thay vì khoanh vẽ thủ công.
// Cách này bảo đảm ranh giới của năm mốc thời gian khớp khít tới từng điểm ảnh,
// là điều kiện bắt buộc để phép so sánh biến động giữa các năm có ý nghĩa.
// Kích thước thực tế là 11,87 nhân 8,64 ki lô mét, diện tích khoảng 102 ki lô mét vuông.
var AOI = ee.Geometry.Polygon(
  [[[106.98849946776265, 10.814327243656404],
    [106.98849946776265, 10.736755380981812],
    [107.09698945799703, 10.736755380981812],
    [107.09698945799703, 10.814327243656404]]], null, false);

var MOC_THOI_GIAN = [2018, 2020, 2022, 2024, 2026];

// Landsat 8 chỉ dùng cho bốn mốc vì mốc 2026 chưa đủ dữ liệu tại thời điểm nghiên cứu.
var NAM_KIEM_CHUNG = [2018, 2020, 2022, 2024];

// Bảng màu dùng chung cho mọi bản đồ trong báo cáo và slide.
// Thứ tự màu phải khớp đúng mã lớp, nếu đảo thứ tự bản đồ sẽ bị tô sai.
// Mã lớp là 0 cho mặt nước, 1 cho thảm thực vật, 2 cho đất trống, 3 cho bề mặt xây dựng.
var PALETTE = ['#1E90FF', '#2E8B57', '#D2B48C', '#D7301F'];

// Ngưỡng mây đặt ở mức rộng vì việc che mây chi tiết được làm ở mức từng điểm ảnh
// bằng lớp phân loại cảnh, chặt quá ở bước này sẽ loại oan nhiều ảnh dùng được.
var NGUONG_MAY = 60;
var SCALE = 10;
var SEED = 42;

// Ranh giới các vành đai khoảng cách tính bằng mét.
// Kế hoạch ban đầu dùng vòng đệm 5, 10 và 15 ki lô mét nhưng phải thu nhỏ lại
// vì cạnh bắc của vùng nghiên cứu chỉ cách tâm dự án 3,33 ki lô mét.
var VANH_DAI = [0, 2000, 4000, 6000];

Map.centerObject(AOI, 12);
Map.addLayer(AOI, {color: 'red'}, 'Vung nghien cuu');
Map.addLayer(SAN_BAY, {color: 'black'}, 'Tam du an');
print('Dien tich vung nghien cuu tinh bang ki lo met vuong:', AOI.area(1).divide(1e6));


// Bước 2. Ghép ảnh Sentinel-2 theo khung mùa khô

// Khung mùa khô Nam Bộ chạy từ tháng mười hai năm trước tới hết tháng tư năm sau.
// Cách chọn này giải quyết cùng lúc hai vấn đề, vừa tránh mùa mưa nhiều mây,
// vừa bảo đảm mốc 2026 có đủ dữ liệu tại thời điểm thực hiện nghiên cứu.
function khungMuaKho(nam) {
  return { batDau: (nam - 1) + '-12-01', ketThuc: nam + '-04-30' };
}

// Lớp phân loại cảnh SCL của Sentinel-2 đánh dấu sẵn từng điểm ảnh thuộc loại gì.
// Mã 3 là bóng mây, mã 8 là mây trung bình, mã 9 là mây dày, mã 10 là mây ti mỏng.
// Sau khi loại các điểm ảnh này, giá trị được chia cho mười nghìn để quy về
// thang phản xạ bề mặt từ không tới một.
function maskMayS2(img) {
  var scl = img.select('SCL');
  var sach = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10));
  return img.updateMask(sach).divide(10000)
            .copyProperties(img, ['system:time_start']);
}

// Bộ dữ liệu dùng ở mức Level-2A đã hiệu chỉnh khí quyển sẵn.
// Trước đây nhóm từng dùng nhầm bộ Level-1C chưa hiệu chỉnh, khiến giá trị phổ
// giữa các thành viên không so sánh được với nhau.
function layComposite(nam) {
  var k = khungMuaKho(nam);
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(AOI)
    .filterDate(k.batDau, k.ketThuc)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', NGUONG_MAY))
    .map(maskMayS2)
    .median()
    .clip(AOI);
}

// Đếm số ảnh nguồn của từng mốc để đánh giá chất lượng dữ liệu đầu vào.
// Mốc 2018 sẽ ra khoảng ba ảnh, ít hơn hẳn các mốc khác, do Sentinel-2 mới có
// dữ liệu Level-2A ổn định cho khu vực này từ cuối năm 2018.
MOC_THOI_GIAN.forEach(function(nam) {
  var k = khungMuaKho(nam);
  var soAnh = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(AOI)
    .filterDate(k.batDau, k.ketThuc)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', NGUONG_MAY))
    .size();
  print('So anh nguon mua kho nam ' + nam, soAnh);
});


// Bước 3. Tạo bộ đặc trưng chín kênh

// Ngoài sáu kênh phổ gốc, thêm ba chỉ số phổ chuyên dụng.
// NDVI phản ánh mật độ thảm thực vật, NDBI phản ánh bề mặt xây dựng,
// NDWI phản ánh mặt nước.
function taoDacTrung(anh) {
  var ndvi = anh.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndbi = anh.normalizedDifference(['B11', 'B8']).rename('NDBI');
  var ndwi = anh.normalizedDifference(['B3', 'B8']).rename('NDWI');
  return anh.select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12'])
            .addBands(ndvi).addBands(ndbi).addBands(ndwi);
}

var BANDS_A = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12', 'NDVI', 'NDBI', 'NDWI'];
var BANDS_B = ['B4', 'B8', 'B11', 'NDVI', 'NDBI'];

// Ảnh tham chiếu để lấy mẫu chọn năm 2022 vì gần với dữ liệu nền của WorldCover.
var dacTrung2022 = taoDacTrung(layComposite(2022));


// Bước 4. Lấy mẫu huấn luyện từ bản đồ lớp phủ ESA WorldCover

// WorldCover phân mười một lớp, gộp lại thành bốn lớp của dự án.
// Chú ý mã lớp sau khi gộp phải khớp với thứ tự bảng màu khai báo ở bước một.
var worldCover = ee.ImageCollection('ESA/WorldCover/v200')
                   .first()
                   .select('Map')
                   .clip(AOI);
var nhanLop = worldCover.remap(
  [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
  [ 1,  1,  1,  1,  3,  2,  2,  0,  0,  0,   1]
).rename('class');

// Lấy mẫu ba lớp thảm thực vật, đất trống và bề mặt xây dựng theo cách thông thường.
var mau3Lop = dacTrung2022.addBands(nhanLop).stratifiedSample({
  numPoints: 0,
  classBand: 'class',
  classValues: [1, 2, 3],
  classPoints: [300, 300, 300],
  region: AOI, scale: SCALE, seed: SEED, geometries: true
});

// Lớp mặt nước phải xử lý riêng.
// Khi rà soát trực quan hai mươi điểm ngẫu nhiên, khoảng ba mươi phần trăm số điểm
// rơi vào giao lộ hoặc mái nhà tối màu chứ không phải mặt nước thật.
// Cách khắc phục là lấy dư số điểm rồi lọc lại bằng ngưỡng chỉ số nước,
// vì mặt nước thật gần như luôn cho giá trị NDWI dương.
var mauWaterTho = dacTrung2022.addBands(nhanLop).stratifiedSample({
  numPoints: 0,
  classBand: 'class',
  classValues: [0],
  classPoints: [950],
  region: AOI, scale: SCALE, seed: SEED, geometries: true
});

var mauWater = mauWaterTho
  .filter(ee.Filter.gt('NDWI', 0))
  .randomColumn('rnd_w', SEED)
  .sort('rnd_w')
  .limit(300);

var mauHuanLuyen = mau3Lop.merge(mauWater);
print('Tong so mau, ky vong mot nghin hai tram', mauHuanLuyen.size());
print('So mau moi lop', mauHuanLuyen.aggregate_histogram('class'));

// Chia bảy phần huấn luyện ba phần kiểm tra.
// Số ngẫu nhiên cố định để kết quả tái lập được ở những lần chạy sau.
var mauRandom = mauHuanLuyen.randomColumn('rnd', SEED);
var trainSet = mauRandom.filter(ee.Filter.lt('rnd', 0.7));
var testSet  = mauRandom.filter(ee.Filter.gte('rnd', 0.7));


// Bước 5. Huấn luyện và so sánh hai phương án đặc trưng

// Phương án A dùng đủ chín đặc trưng.
// Phương án B rút gọn còn năm đặc trưng, xuất phát từ nhận xét ở bước khảo sát
// rằng các kênh khả kiến tương quan cao với nhau và cặp NDVI với NDWI gần như
// đối xứng nghịch, nên có khả năng thông tin bị dư thừa.
function chayPhanLoai(bandList, tenPhuongAn) {
  var clf = ee.Classifier.smileRandomForest(200).train({
    features: trainSet,
    classProperty: 'class',
    inputProperties: bandList
  });
  var cm = testSet.classify(clf).errorMatrix('class', 'classification');

  print(tenPhuongAn + ' voi ' + bandList.length + ' dac trung');
  print('Ma tran nham lan', cm);
  print('Do chinh xac tong the', cm.accuracy());
  print('He so Kappa', cm.kappa());
  print('Producer accuracy', cm.producersAccuracy());
  print('Consumer accuracy', cm.consumersAccuracy());
  return clf;
}

var clfA = chayPhanLoai(BANDS_A, 'Phuong an A');
var clfB = chayPhanLoai(BANDS_B, 'Phuong an B');

// Kết quả thực tế cho thấy phương án A vượt trội trên mọi chỉ số,
// độ chính xác tổng thể cao hơn hơn bốn điểm phần trăm và Kappa cao hơn 0,057.
// Quan trọng hơn, lớp bề mặt xây dựng là đối tượng nghiên cứu chính cũng
// cho kết quả tốt hơn. Vì vậy phương án A được chọn làm mô hình chính thức.
var clfChon = clfA;
var bandChon = BANDS_A;


// Bước 6. Tính độ chính xác có trọng số theo diện tích

// Tập kiểm tra chia đều số điểm cho bốn lớp, trong khi ngoài thực tế
// thảm thực vật chiếm gần chín mươi tư phần trăm còn mặt nước chỉ chiếm một phần nghìn.
// Do đó độ chính xác tổng thể tính theo cách thông thường không phản ánh
// độ chính xác thật của bản đồ. Phép tính dưới đây theo khuyến nghị của
// Olofsson và cộng sự năm 2014, gán lại trọng số cho từng lớp theo diện tích thực tế.
var TY_LE_DIEN_TICH = [0.0010, 0.9395, 0.0179, 0.0417];

function doChinhXacTrongSo(confusionMatrix, tyLeDienTich) {
  var cm = ee.Array(confusionMatrix.array());
  var Wi = ee.Array([tyLeDienTich]).transpose();
  var tongHang = cm.reduce(ee.Reducer.sum(), [1]);
  var chuanHoa = cm.divide(tongHang.repeat(1, 4)).multiply(Wi.repeat(1, 4));
  var duongCheo = chuanHoa.matrixDiagonal();
  return duongCheo.reduce(ee.Reducer.sum(), [0]).get([0, 0]);
}

var cmChon = testSet.classify(clfChon).errorMatrix('class', 'classification');
print('Do chinh xac co trong so dien tich, dung so nay trong bao cao',
      doChinhXacTrongSo(cmChon, TY_LE_DIEN_TICH));


// Bước 7. Áp mô hình lên năm mốc thời gian

// Bộ lọc majority ba nhân ba là bước hậu xử lý chuẩn trong viễn thám.
// Mỗi điểm ảnh được gán lại theo nhãn phổ biến nhất trong chín điểm ảnh lân cận,
// nhờ đó khử được nhiễu ngẫu nhiên dạng muối tiêu.
function locMajority(anhPhanLoai) {
  return anhPhanLoai.focalMode({
    radius: 1, kernelType: 'square', units: 'pixels', iterations: 1
  });
}

var ketQuaPhanLoai = {};

MOC_THOI_GIAN.forEach(function(nam) {
  var kq = locMajority(
    taoDacTrung(layComposite(nam)).select(bandChon).classify(clfChon)
  );
  ketQuaPhanLoai[nam] = kq;
  Map.addLayer(kq, {min: 0, max: 3, palette: PALETTE}, 'Phan loai ' + nam, false);
});

// Cách kiểm tra bảng màu có bị đảo thứ tự hay không.
// Bật lớp phân loại năm 2024 lên, vùng lõi trung tâm phải hiện màu đỏ.
// Nếu ra màu xanh dương nghĩa là thứ tự trong biến PALETTE bị ghép sai.


// Bước 8. Tính diện tích từng lớp qua các mốc

function tinhDienTich(anhPhanLoai, vung) {
  return ee.Image.pixelArea().divide(10000)
    .addBands(anhPhanLoai.rename('lop'))
    .reduceRegion({
      reducer: ee.Reducer.sum().group({groupField: 1, groupName: 'lop'}),
      geometry: vung, scale: SCALE, maxPixels: 1e13
    });
}

MOC_THOI_GIAN.forEach(function(nam) {
  print('Dien tich cac lop nam ' + nam + ' tinh bang hec ta',
        tinhDienTich(ketQuaPhanLoai[nam], AOI));
});


// Bước 9. Phân tích theo vành đai khoảng cách

// Kế hoạch ban đầu dùng vòng đệm tròn 5, 10 và 15 ki lô mét quanh tâm dự án.
// Khi kiểm tra lại mới thấy vùng nghiên cứu quá nhỏ để chứa các vòng đệm này,
// và tâm dự án còn lệch lên phía bắc nên cạnh bắc chỉ cách tâm 3,33 ki lô mét.
// Vì vậy chuyển sang vành đai khoảng cách nhỏ hơn, và đo bằng tỷ lệ phần trăm
// thay cho diện tích tuyệt đối, vì tỷ lệ không bị ảnh hưởng khi vành đai bị cắt.
var khoangCach = ee.FeatureCollection([ee.Feature(SAN_BAY)])
  .distance(20000)
  .clip(AOI)
  .rename('dist');

// Hàm này định lượng luôn phần vành đai bị cắt để nêu minh bạch trong báo cáo,
// thay vì chỉ nói chung chung rằng vành ngoài không đầy đủ.
function docheVanhDai() {
  for (var i = 0; i < VANH_DAI.length - 1; i++) {
    var trong = VANH_DAI[i], ngoai = VANH_DAI[i + 1];
    var maskVanh = khoangCach.gte(trong).and(khoangCach.lt(ngoai));

    var dtThucTe = maskVanh.multiply(ee.Image.pixelArea()).reduceRegion({
      reducer: ee.Reducer.sum(), geometry: AOI, scale: SCALE, maxPixels: 1e13
    }).getNumber('dist');

    var dtLyThuyet = Math.PI * (ngoai * ngoai - trong * trong);

    print('Vanh dai tu ' + (trong / 1000) + ' toi ' + (ngoai / 1000) + ' ki lo met',
          'dien tich thuc te', dtThucTe,
          'dien tich ly thuyet', dtLyThuyet,
          'ty le che phu', dtThucTe.divide(dtLyThuyet));
  }
}
docheVanhDai();

function tyLeBeTongTheoVanh(anhPhanLoai, nam) {
  for (var i = 0; i < VANH_DAI.length - 1; i++) {
    var trong = VANH_DAI[i], ngoai = VANH_DAI[i + 1];
    var maskVanh = khoangCach.gte(trong).and(khoangCach.lt(ngoai));

    var tongVanh = maskVanh.multiply(ee.Image.pixelArea()).reduceRegion({
      reducer: ee.Reducer.sum(), geometry: AOI, scale: SCALE, maxPixels: 1e13
    }).getNumber('dist');

    var tongBeTong = anhPhanLoai.eq(3).and(maskVanh)
      .multiply(ee.Image.pixelArea()).reduceRegion({
        reducer: ee.Reducer.sum(), geometry: AOI, scale: SCALE, maxPixels: 1e13
      }).getNumber('classification');

    print('Nam ' + nam + ' vanh dai ' + (trong / 1000) + ' toi ' + (ngoai / 1000),
          'ty le be tong tinh bang phan tram', tongBeTong.divide(tongVanh).multiply(100),
          'dien tich be tong tinh bang hec ta', tongBeTong.divide(10000));
  }
}

MOC_THOI_GIAN.forEach(function(nam) {
  tyLeBeTongTheoVanh(ketQuaPhanLoai[nam], nam);
});


// Bước 10. Kiểm chứng chéo với vệ tinh Landsat 8

// Mục đích của bước này là xác nhận kết quả không phụ thuộc vào một nguồn
// dữ liệu duy nhất. Landsat phải dùng đúng khung mùa khô như Sentinel-2,
// nếu lấy khung cả năm thì hệ số tương quan sẽ phản ánh cả sai khác mùa vụ
// chứ không riêng sai khác giữa hai cảm biến.
function landsatComposite(nam) {
  var k = khungMuaKho(nam);
  return ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .filterBounds(AOI)
    .filterDate(k.batDau, k.ketThuc)
    .filter(ee.Filter.lt('CLOUD_COVER', 30))
    .map(function(img) {
      // Áp hệ số hiệu chỉnh của Collection 2 Level-2 để đưa giá trị số nguyên
      // về đúng thang phản xạ bề mặt.
      var quangHoc = img.select('SR_B.').multiply(0.0000275).add(-0.2);
      // Che mây bằng bit mask trên kênh đánh giá chất lượng,
      // bit thứ ba đánh dấu mây và bit thứ tư đánh dấu bóng mây.
      var qa = img.select('QA_PIXEL');
      var sach = qa.bitwiseAnd(1 << 3).eq(0).and(qa.bitwiseAnd(1 << 4).eq(0));
      return img.addBands(quangHoc, null, true).updateMask(sach);
    })
    .median()
    .clip(AOI);
}

NAM_KIEM_CHUNG.forEach(function(nam) {
  var ndbiS2 = layComposite(nam).normalizedDifference(['B11', 'B8']).rename('x');
  var ndbiLS = landsatComposite(nam).normalizedDifference(['SR_B6', 'SR_B5']).rename('y');

  // Hạ Sentinel-2 từ lưới mười mét xuống lưới ba mươi mét để khớp điểm ảnh
  // với Landsat, nếu không thì hai bên không cùng đơn vị so sánh.
  var s2At30m = ndbiS2
    .setDefaultProjection(ee.Projection('EPSG:32648').atScale(10))
    .reduceResolution({reducer: ee.Reducer.mean(), maxPixels: 1024})
    .reproject({crs: 'EPSG:32648', scale: 30});

  print('Tuong quan chi so be tong hai ve tinh nam ' + nam,
    s2At30m.addBands(ndbiLS).reduceRegion({
      reducer: ee.Reducer.pearsonsCorrelation(),
      geometry: AOI, scale: 30, maxPixels: 1e13, bestEffort: true
    }));

  Map.addLayer(s2At30m.subtract(ndbiLS),
    {min: -0.2, max: 0.2, palette: ['blue', 'white', 'red']},
    'Chenh lech chi so be tong ' + nam, false);
});

// Cách diễn giải hệ số tương quan trong báo cáo.
// Trên 0,85 là nhất quán cao. Từ 0,70 tới 0,85 là nhất quán khá, sai khác
// chủ yếu do chênh lệch độ phân giải tại ranh giới các lớp phủ.
// Dưới 0,70 thì cần rà lại quy trình.
// Lưu ý bình phương hệ số tương quan mới là phần phương sai giải thích được,
// nên hệ số 0,714 chỉ tương ứng khoảng năm mươi mốt phần trăm.


// Bước 11. Xuất kết quả

MOC_THOI_GIAN.forEach(function(nam) {
  Export.image.toDrive({
    image: ketQuaPhanLoai[nam].toByte(),
    description: 'PhanLoai_' + nam,
    folder: 'GEE_LongThanh_Nhom',
    region: AOI,
    scale: SCALE,
    maxPixels: 1e13
  });
});

Export.table.toDrive({
  collection: ee.FeatureCollection([ee.Feature(AOI)]),
  description: 'VungNghienCuu',
  folder: 'GEE_LongThanh_Nhom',
  fileFormat: 'GeoJSON'
});
