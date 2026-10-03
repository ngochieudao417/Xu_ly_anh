"""Don goi DOCX truoc khi nop len cac dich vu ngoai.

python-docx dung mot tep mau co san tu thoi Word 2007, nen moi tep sinh ra deu
keo theo may phan khong he duoc dung den: customXml, stylesWithEffects.xml va
anh thumbnail. Word bo qua chung, nhung mot so trinh nhap ben ngoai (Google
Docs chang han) lai bao "khong ho tro tep da tai len".

Module nay go dung nhung phan thua do va don sach moi tham chieu toi chung,
giu nguyen tuyet doi phan noi dung va dinh dang. Khac voi cach luu lai bang
LibreOffice, cach nay khong dich font tu run sang style nen ban in ra khong
doi mot ly nao.
"""

from __future__ import annotations

import posixpath
import re
import shutil
import zipfile
from pathlib import Path

# Cac phan khong bao gio duoc dung toi trong bao cao cua du an.
DROP_PREFIXES = ("customXml/",)
DROP_PARTS = ("word/stylesWithEffects.xml", "docProps/thumbnail.jpeg")


def _should_drop(name: str) -> bool:
    return name in DROP_PARTS or name.startswith(DROP_PREFIXES)


def _strip_content_types(xml: str, dropped: set[str]) -> str:
    for part in dropped:
        xml = re.sub(rf'<Override PartName="/{re.escape(part)}"[^>]*/>', "", xml)
    # Khong con anh thumbnail thi khai bao duoi jpeg co the thua, nhung giu lai
    # cung vo hai vi cac hinh nhung vao deu la JPEG.
    return xml


def _resolve(target: str, base: str) -> str:
    """Doi Target cua mot quan he thanh duong dan tuyet doi trong goi.

    Target co the la tuyet doi (/word/...), tuong doi (media/x.png) hoac co
    chua .. (../customXml/item1.xml). Phai chuan hoa thi moi so khop duoc.
    """
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(base, target)).lstrip("/")


def _strip_rels(xml: str, dropped: set[str], base: str = "") -> str:
    def drop(match: str) -> bool:
        target = re.search(r'Target="([^"]+)"', match)
        if not target:
            return False
        return _resolve(target.group(1), base) in dropped

    return "".join(
        "" if (m.startswith("<Relationship") and drop(m)) else m
        for m in re.split(r"(<Relationship\b[^>]*/>)", xml)
    )


def clean(path: str | Path, backup: bool = False) -> dict:
    """Go cac phan thua khoi tep DOCX tai cho. Tra ve thong ke da go gi."""
    path = Path(path)
    src = zipfile.ZipFile(path)
    names = src.namelist()
    dropped = {n for n in names if _should_drop(n)}
    if not dropped:
        src.close()
        return {"file": path.name, "dropped": [], "before_mb": path.stat().st_size / 1e6,
                "after_mb": path.stat().st_size / 1e6}

    before = path.stat().st_size
    tmp = path.with_suffix(".docx.tmp")

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename in dropped:
                continue
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = _strip_content_types(data.decode("utf-8"), dropped).encode("utf-8")
            elif item.filename == "_rels/.rels":
                data = _strip_rels(data.decode("utf-8"), dropped).encode("utf-8")
            elif item.filename == "word/_rels/document.xml.rels":
                data = _strip_rels(data.decode("utf-8"), dropped, base="word/").encode("utf-8")
            dst.writestr(item, data)
    src.close()

    if backup:
        shutil.copy2(path, path.with_suffix(".docx.bak"))
    tmp.replace(path)
    return {"file": path.name, "dropped": sorted(dropped),
            "before_mb": before / 1e6, "after_mb": path.stat().st_size / 1e6}


if __name__ == "__main__":
    import sys
    targets = sys.argv[1:] or sorted(
        (Path(__file__).resolve().parents[1] / "reports").glob("*.docx"))
    for t in targets:
        info = clean(t)
        print(f"{info['file']}: go {len(info['dropped'])} phan, "
              f"{info['before_mb']:.2f} -> {info['after_mb']:.2f} MB")
