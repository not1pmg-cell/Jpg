"""PDF vositalari (PyMuPDF, bepul, tashqi API yo'q)."""
import io, zipfile
from fastapi import HTTPException

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

PDF = "application/pdf"
NAMES = ["merge", "extract", "delete", "split", "rotate", "protect", "unlock", "images", "text", "compress", "numbers"]


def _open(d, pw=None):
    try:
        doc = fitz.open(stream=d, filetype="pdf")
    except Exception:
        raise HTTPException(400, "PDF faylni o'qib bo'lmadi")
    if doc.needs_pass and not (pw and doc.authenticate(pw)):
        raise HTTPException(400, "PDF parol bilan himoyalangan. «PDF parolni olib tashlash» vositasida parolni kiriting")
    return doc


def _pages(spec, n):
    spec = (spec or "").replace(" ", "")
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a, b = int(a or 1), int(b or n)
                rng = range(a, b + 1) if a <= b else range(a, b - 1, -1)
            else:
                rng = [int(part)]
        except ValueError:
            raise HTTPException(400, "Sahifalar noto'g'ri yozilgan. Masalan: 1-3,5")
        for x in rng:
            if x < 1 or x > n:
                raise HTTPException(400, f"{x}-sahifa yo'q (jami {n} ta)")
            out.append(x - 1)
    return out


def _save(doc):
    return doc.tobytes(garbage=3, deflate=True), "pdf", PDF


def _zip(items):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in items:
            z.writestr(n, d)
    return b.getvalue(), "zip", "application/zip"


def run(action, datas, p):
    if fitz is None:
        raise HTTPException(500, "PyMuPDF o'rnatilmagan (requirements.txt ni tekshiring)")
    a = action[4:]
    if a == "merge":
        if len(datas) < 2:
            raise HTTPException(400, "Birlashtirish uchun kamida 2 ta PDF tanlang")
        out = fitz.open()
        for d in datas:
            out.insert_pdf(_open(d))
        return _save(out)

    doc = _open(datas[0], p.get("password") if a == "unlock" else None)
    n = len(doc)
    if a == "extract":
        doc.select(_pages(p.get("pages"), n))
        return _save(doc)
    if a == "delete":
        rm = set(_pages(p.get("pages"), n))
        keep = [i for i in range(n) if i not in rm]
        if not keep:
            raise HTTPException(400, "Hamma sahifani o'chirib bo'lmaydi")
        doc.select(keep)
        return _save(doc)
    if a == "split":
        items = []
        for i in range(min(n, 200)):
            d2 = fitz.open()
            d2.insert_pdf(doc, from_page=i, to_page=i)
            items.append((f"page_{i + 1}.pdf", d2.tobytes(garbage=3, deflate=True)))
        return _zip(items)
    if a == "rotate":
        ang = int(p.get("angle", 90))
        for i in _pages(p.get("pages"), n):
            doc[i].set_rotation((doc[i].rotation + ang) % 360)
        return _save(doc)
    if a == "protect":
        pw = str(p.get("password") or "")
        if len(pw) < 1:
            raise HTTPException(400, "Parol kiriting")
        return doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw=pw, owner_pw=pw), "pdf", PDF
    if a == "unlock":
        return doc.tobytes(encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True), "pdf", PDF
    if a == "images":
        dpi, fmt = max(50, min(int(p.get("dpi", 110)), 200)), str(p.get("format", "PNG")).upper()
        if n > 30:
            raise HTTPException(400, "Bir martada 30 sahifagacha. Avval «PDF sahifa ajratish» dan foydalaning")
        ext, kind = ("jpg", "jpeg") if fmt in ("JPG", "JPEG") else ("png", "png")
        return _zip([(f"page_{i + 1}.{ext}", pg.get_pixmap(dpi=dpi).tobytes(kind)) for i, pg in enumerate(doc)])
    if a == "text":
        txt = "\n\n".join(f"--- {i + 1}-sahifa ---\n{pg.get_text().strip()}" for i, pg in enumerate(doc))
        if len(txt.replace("-", "").replace("sahifa", "").strip()) < n * 10:
            raise HTTPException(400, "PDF da matn topilmadi (u skaner qilingan rasm bo'lishi mumkin). Sahifani rasmga aylantirib, «OCR» vositasini ishlating")
        return txt.encode(), "txt", "text/plain"
    if a == "compress":
        dpi, qual = int(p.get("dpi", 110)), int(p.get("quality", 60))
        try:
            doc.rewrite_images(dpi_threshold=dpi + 30, dpi_target=dpi, quality=qual)
        except Exception:
            pass  # eski PyMuPDF versiyasida rasm siqish yo'q, faqat tuzilma siqiladi
        return doc.tobytes(garbage=4, deflate=True, clean=True), "pdf", PDF
    if a == "numbers":
        size, start, pos = int(p.get("size", 11)), int(p.get("start", 1)), p.get("pos", "bc")
        for i, pg in enumerate(doc):
            s = str(start + i)
            w = fitz.get_text_length(s, fontsize=size)
            x = {"bc": (pg.rect.width - w) / 2, "br": pg.rect.width - w - 36, "bl": 36}.get(pos, 36)
            pg.insert_text((x, pg.rect.height - 24), s, fontsize=size, color=(0, 0, 0))
        return _save(doc)
    raise HTTPException(400, "Noma'lum PDF amali")
