"""Nen anh truoc khi nhung vao DOCX.

Hinh matplotlib luu o dang PNG RGBA thuong nang 2 den 2,5 MB moi tam. Mot bao
cao vai hinh nhu vay de len toi 8 MB, va Google Docs hay bao loi khi nhap
nhung tep nang. Chuyen sang JPEG chat luong 90, gioi han be ngang 1500 diem
anh thi nho hon khoang 5 lan ma in ra o kho 14,5 cm van du net.

Dung chung cho moi script sinh bao cao de khoi lap lai code.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

MAX_WIDTH_PX = 1500
JPEG_QUALITY = 90
CACHE_DIRNAME = "_docx_img"


def optimized(path: str | Path, cache_dir: str | Path | None = None) -> Path:
    """Tra ve duong dan ban JPEG da nen cua `path`, dung de nhung vao DOCX.

    Ban nen duoc cache canh anh goc; chi tao lai khi anh goc moi hon.
    Anh khong doc duoc thi tra ve nguyen duong dan goc.
    """
    path = Path(path)
    if not path.exists():
        return path

    cache = Path(cache_dir) if cache_dir else path.parent / CACHE_DIRNAME
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / (path.stem + ".jpg")
    if dst.exists() and dst.stat().st_mtime >= path.stat().st_mtime:
        return dst

    try:
        im = Image.open(path)
    except Exception:
        return path

    # JPEG khong co kenh trong suot, nen phai dan nen trang truoc.
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")

    if im.width > MAX_WIDTH_PX:
        im = im.resize((MAX_WIDTH_PX, round(im.height * MAX_WIDTH_PX / im.width)),
                       Image.LANCZOS)

    im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return dst
