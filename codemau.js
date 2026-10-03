//WorldCover chỉ phản ánh thực trạng 2020-2021=>các điểm mẫu "bê tông" tại vị trí sân bay hiện nay thì  2018 vẫn là cây+đất trồng. train trên 2021 rồi áp lên 2018 vẫn đúng về mặt phương pháp (mô hình học đặc trưng phổ, không học vị trí), Hiếu nên kiểm chứng bằng mắt kết quả phân loại 2018 trên nền ảnh RGB => thấy vùng sân bay bị gán nhầm là bê tông năm 2018 thì phải bổ sung mẫu vẽ tay riêng cho năm đó.
// ============================================================
// TASK 2, 3, 4: Đặc trưng → Mẫu huấn luyện → Random Forest
// ============================================================

var sanBayCenter = ee.Geometry.Point([107.04111, 10.78444]);
var aoi = sanBayCenter.buffer(15000).bounds();

// ---------- TASK 2: Tạo bộ đặc trưng ----------
function taoDacTrung(anh) {
  var ndvi = anh.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var ndbi = anh.normalizedDifference(['B11', 'B8']).rename('NDBI');
  var ndwi = anh.normalizedDifference(['B3', 'B8']).rename('NDWI');
  return anh.select(['B2','B3','B4','B8','B11','B12'])
    .addBands(ndvi).addBands(ndbi).addBands(ndwi);
}

function layAnhNam(nam) {
  return ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(nam + '-01-01', nam + '-12-31')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
    .median()
    .clip(aoi);
}

// Dùng năm 2021 để lấy mẫu (khớp thời điểm WorldCover v200)
var anh2021 = layAnhNam(2021);
var features2021 = taoDacTrung(anh2021);

// ---------- TASK 3: Lấy mẫu tự động từ ESA WorldCover ----------
var worldCover = ee.Image('ESA/WorldCover/v200').select('Map').clip(aoi);

// Gộp 11 lớp gốc WorldCover → 4 lớp của đề cương
// 0 = Bê tông/xây dựng | 1 = Thực vật | 2 = Đất trống | 3 = Mặt nước
var nhanLop = worldCover.remap(
  [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100],
  [ 1,  1,  1,  1,  0,  2,  2,  3,  1,  1,  1]
).rename('class');

var mauHuanLuyen = features2021.addBands(nhanLop).stratifiedSample({
  numPoints: 300,
  classBand: 'class',
  region: aoi,
  scale: 10,
  seed: 42,          // cố định seed để tái lập kết quả
  geometries: true
});

print('Tổng số mẫu:', mauHuanLuyen.size());
print('Số mẫu mỗi lớp:', mauHuanLuyen.aggregate_histogram('class'));

// Chia 70% train / 30% test
var mauRandom = mauHuanLuyen.randomColumn('rnd', 42);
var trainSet = mauRandom.filter(ee.Filter.lt('rnd', 0.7));
var testSet  = mauRandom.filter(ee.Filter.gte('rnd', 0.7));

// ---------- TASK 4: So sánh 2 phương án đặc trưng ----------
var bandsA = ['B2','B3','B4','B8','B11','B12','NDVI','NDBI','NDWI']; // 9 band
var bandsB = ['B4','B8','B11','NDVI','NDBI'];                        // 5 band rút gọn

function chayPhanLoai(bandList, tenPA) {
  var clf = ee.Classifier.smileRandomForest(100).train({
    features: trainSet,
    classProperty: 'class',
    inputProperties: bandList
  });

  var cm = testSet.classify(clf).errorMatrix('class', 'classification');

  print('===== ' + tenPA + ' (' + bandList.length + ' band) =====');
  print('Ma trận nhầm lẫn:', cm);
  print('Overall Accuracy:', cm.accuracy());
  print('Kappa:', cm.kappa());
  print('Producer Accuracy:', cm.producersAccuracy());
  print('Consumer Accuracy:', cm.consumersAccuracy());

  return clf;
}

var clfA = chayPhanLoai(bandsA, 'Phương án A - đầy đủ');
var clfB = chayPhanLoai(bandsB, 'Phương án B - rút gọn');

// ---------- Áp mô hình thắng cuộc lên cả 5 mốc thời gian ----------
// Sau khi xem Kappa ở Console, đổi biến này thành clfB nếu B thắng
var clfChon = clfA;
var bandChon = bandsA;

var mocThoiGian = [2018, 2020, 2022, 2024, 2026];
var palette = ['#e31a1c', '#33a02c', '#d9a441', '#1f78b4']; // bê tông/thực vật/đất trống/nước

mocThoiGian.forEach(function(nam) {
  var kq = taoDacTrung(layAnhNam(nam)).select(bandChon).classify(clfChon);
  Map.addLayer(kq, {min: 0, max: 3, palette: palette}, 'Phân loại ' + nam, false);

  // Diện tích lớp bê tông (class 0) - phục vụ Tuần 3
  var dienTich = kq.eq(0).multiply(ee.Image.pixelArea())
    .reduceRegion({
      reducer: ee.Reducer.sum(), geometry: aoi, scale: 10, maxPixels: 1e13
    });
  print('Diện tích bê tông năm ' + nam + ' (m2):', dienTich);
});

Map.centerObject(aoi, 11);

// KIỂM CHỨNG CHÉO: NDBI từ Sentinel-2 (10m) vs Landsat 8 (30m)
// Cường (dữ liệu) + Hiếu (đối chiếu kết quả)


var sanBayCenter = ee.Geometry.Point([107.04111, 10.78444]);
var aoi = sanBayCenter.buffer(15000).bounds();
var mocThoiGian = [2018, 2020, 2022, 2024];  // 2026 chưa đủ dữ liệu Landsat cả năm

// ---------- Sentinel-2: NDBI = (B11 - B8) / (B11 + B8) ----------
function ndbiSentinel(nam) {
  var img = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(nam + '-01-01', nam + '-12-31')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
    .median()
    .clip(aoi);
  return img.normalizedDifference(['B11', 'B8']).rename('NDBI_S2');
}

// ---------- Landsat 8: NDBI = (SR_B6 - SR_B5) / (SR_B6 + SR_B5) ----------
function ndbiLandsat(nam) {
  var col = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .filterBounds(aoi)
    .filterDate(nam + '-01-01', nam + '-12-31')
    .filter(ee.Filter.lt('CLOUD_COVER', 20))
    .map(function(img) {
      // Áp scale factor Collection 2 Level-2 + mask mây từ QA_PIXEL
      var optical = img.select('SR_B.').multiply(0.0000275).add(-0.2);
      var qa = img.select('QA_PIXEL');
      var mask = qa.bitwiseAnd(1 << 3).eq(0)      // không phải mây
                 .and(qa.bitwiseAnd(1 << 4).eq(0)); // không phải bóng mây
      return img.addBands(optical, null, true).updateMask(mask);
    });
  var img = col.median().clip(aoi);
  return img.normalizedDifference(['SR_B6', 'SR_B5']).rename('NDBI_LS');
}

// ---------- So sánh định lượng theo từng năm ----------
mocThoiGian.forEach(function(nam) {
  var s2 = ndbiSentinel(nam);
  var ls = ndbiLandsat(nam);

  // Đưa Sentinel-2 về lưới 30m để so sánh cùng đơn vị pixel
  var s2At30m = s2
    .setDefaultProjection(ee.Projection('EPSG:32648').atScale(10))
    .reduceResolution({reducer: ee.Reducer.mean(), maxPixels: 1024})
    .reproject({crs: 'EPSG:32648', scale: 30});

  // 1. Thống kê mô tả 2 nguồn
  var thongKe = s2At30m.rename('NDBI_S2').addBands(ls).reduceRegion({
    reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
    geometry: aoi, scale: 30, maxPixels: 1e13, bestEffort: true
  });
  print('--- Nam ' + nam + ' - Thong ke NDBI 2 nguon:', thongKe);

  // 2. Hệ số tương quan Pearson giữa 2 nguồn (chỉ số then chốt)
  var tuongQuan = s2At30m.rename('x').addBands(ls.rename('y')).reduceRegion({
    reducer: ee.Reducer.pearsonsCorrelation(),
    geometry: aoi, scale: 30, maxPixels: 1e13, bestEffort: true
  });
  print('Nam ' + nam + ' - Tuong quan S2 vs Landsat (r):', tuongQuan);

  // 3. Bản đồ hiệu số - xem sai khác tập trung ở đâu
  var hieuSo = s2At30m.subtract(ls).rename('chenh_lech');
  Map.addLayer(hieuSo, {min:-0.2, max:0.2, palette:['blue','white','red']},
               'Chenh lech NDBI ' + nam, false);
});

// ---------- Biểu đồ scatter đối chiếu (năm đại diện) ----------
var namMau = 2022;
var mauDiem = ndbiSentinel(namMau)
  .setDefaultProjection(ee.Projection('EPSG:32648').atScale(10))
  .reduceResolution({reducer: ee.Reducer.mean(), maxPixels: 1024})
  .reproject({crs: 'EPSG:32648', scale: 30})
  .rename('NDBI_S2')
  .addBands(ndbiLandsat(namMau))
  .sample({region: aoi, scale: 30, numPixels: 3000, seed: 42, geometries: false});

print(ui.Chart.feature.byFeature(mauDiem, 'NDBI_S2', ['NDBI_LS'])
  .setChartType('ScatterChart')
  .setOptions({
    title: 'Doi chieu NDBI: Sentinel-2 vs Landsat 8 (nam ' + namMau + ')',
    hAxis: {title: 'NDBI Sentinel-2 (resample 30m)'},
    vAxis: {title: 'NDBI Landsat 8 (30m goc)'},
    pointSize: 2,
    trendlines: {0: {showR2: true, visibleInLegend: true}}
  }));

Map.centerObject(aoi, 11);
