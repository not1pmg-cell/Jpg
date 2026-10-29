"""Umumiy rasm yordamchilari."""
import io
from fastapi import HTTPException
from PIL import Image, ImageOps, ImageFont, ImageDraw, ImageFilter, ImageChops, ImageEnhance

LANCZOS = Image.Resampling.LANCZOS

# ───────────────────────── IMAGE HELPERS ─────────────────────────
MEDIA = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "bmp": "image/bmp",
         "gif": "image/gif", "tiff": "image/tiff", "pdf": "application/pdf"}

def load(data: bytes):
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except Exception:
        raise HTTPException(400, "Rasm o'qib bo'lmadi (fayl buzilgan yoki format noma'lum)")
    img = ImageOps.exif_transpose(img)  # telefon rasmlari yotib qolmasin
    has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    return img.convert("RGBA" if has_alpha else "RGB"), fmt

def flat(img, bg=(255, 255, 255)):
    if img.mode == "RGBA":
        base = Image.new("RGB", img.size, bg)
        base.paste(img, mask=img.getchannel("A"))
        return base
    return img.convert("RGB")

def rgb_op(img, fn):
    """Alfa kanalini saqlagan holda RGB ustida amal bajaradi."""
    if img.mode == "RGBA":
        a = img.getchannel("A")
        out = fn(img.convert("RGB")).convert("RGB")
        out.putalpha(a)
        return out
    return fn(img.convert("RGB"))

def hex_rgb(h, default=(255, 255, 255)):
    try:
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default

def enc(img, fmt, q=90):
    f = str(fmt).upper()
    f = "JPG" if f == "JPEG" else ("TIFF" if f == "TIF" else f)
    b = io.BytesIO()
    if f == "JPG":
        flat(img).save(b, "JPEG", quality=q, optimize=True, progressive=True)
    elif f == "PNG":
        img.save(b, "PNG", optimize=True)
    elif f == "WEBP":
        img.save(b, "WEBP", quality=q, method=4)
    elif f == "PDF":
        flat(img).save(b, "PDF", resolution=100)
    elif f == "BMP":
        flat(img).save(b, "BMP")
    elif f == "GIF":
        flat(img).convert("P", palette=Image.Palette.ADAPTIVE).save(b, "GIF")
    elif f == "TIFF":
        img.save(b, "TIFF", compression="tiff_lzw")
    else:
        raise HTTPException(400, "Bu format qo'llab-quvvatlanmaydi")
    ext = f.lower()
    return b.getvalue(), ext, MEDIA[ext]

def get_font(size):
    for n in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

