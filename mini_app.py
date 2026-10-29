"""
TELEGRAM MINI APP — IMAGE TOOLS  (v2)
Ishga tushirish:  uvicorn mini_app:app --host 0.0.0.0 --port $PORT

ENV o'zgaruvchilar:
  BOT_TOKEN       — BotFather bergan token (majburiy)
  MAX_UPLOAD_MB   — bitta fayl limiti, default 20
  DEV_MODE        — "1" bo'lsa Telegram tekshiruvi o'chadi (faqat brauzerda sinash uchun!)
"""

import os, io, json, hmac, hashlib, time, urllib.parse, uuid
from typing import List
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont, ImageChops

try:  # iPhone (HEIC) rasmlari uchun
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
DEV_MODE = os.getenv("DEV_MODE", "") == "1"
Image.MAX_IMAGE_PIXELS = 100_000_000

app = FastAPI(title="Image Tools")
LANCZOS = Image.Resampling.LANCZOS

# ───────────────────────── AUTH ─────────────────────────
def verify_init_data(init_data: str):
    if not init_data:
        return None
    try:
        p = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        h = p.pop("hash", "")
        if time.time() - int(p.get("auth_date", "0")) > 86400:  # 24 soatdan eski
            return None
        s = "\n".join(f"{k}={v}" for k, v in sorted(p.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, s.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, h):
            return None
        return json.loads(p.get("user", "{}"))
    except Exception:
        return None

def require_user(init_data: str):
    if DEV_MODE:
        return {"id": 0}
    u = verify_init_data(init_data)
    if not u:
        raise HTTPException(401, "Telegram orqali oching (initData noto'g'ri yoki eskirgan)")
    return u

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

# ───────────────────────── TOOLS ─────────────────────────
RATIOS = {"1:1": (1, 1), "4:5": (4, 5), "3:4": (3, 4), "4:3": (4, 3), "16:9": (16, 9),
          "9:16": (9, 16), "3:2": (3, 2), "2:3": (2, 3)}

def t_resize(img, p, fmt, q):
    if p.get("mode") == "percent":
        k = float(p.get("percent", 50)) / 100
        w, h = int(img.width * k), int(img.height * k)
    else:
        w, h = int(p.get("width") or 0), int(p.get("height") or 0)
        if not w and not h:
            raise HTTPException(400, "Kenglik yoki balandlikni kiriting")
        if p.get("keep", True):
            if w and h:
                w, h = ImageOps.contain(img, (w, h)).size
            elif w:
                h = int(img.height * w / img.width)
            else:
                w = int(img.width * h / img.height)
        else:
            w, h = w or img.width, h or img.height
    w, h = max(1, min(w, 10000)), max(1, min(h, 10000))
    return enc(img.resize((w, h), LANCZOS), fmt, q)

def t_compress(img, p, fmt, q):
    fmt = fmt if fmt in ("JPG", "WEBP") else "JPG"
    target = int(p.get("target_kb") or 0)
    if target <= 0:
        return enc(img, fmt, q)
    cur = img
    for _ in range(6):  # sifat past bo'lsa, o'lchamni ham kichraytiramiz
        lo, hi, found = 5, 95, None
        while lo <= hi:
            m = (lo + hi) // 2
            d = enc(cur, fmt, m)
            if len(d[0]) <= target * 1024:
                found, lo = d, m + 1
            else:
                hi = m - 1
        if found:
            return found
        cur = cur.resize((max(1, int(cur.width * .8)), max(1, int(cur.height * .8))), LANCZOS)
    return enc(cur, fmt, 5)

def t_crop(img, p, fmt, q):
    rw, rh = RATIOS.get(p.get("ratio", "1:1"), (1, 1))
    cx, cy = {"center": (.5, .5), "top": (.5, 0), "bottom": (.5, 1),
              "left": (0, .5), "right": (1, .5)}.get(p.get("pos", "center"), (.5, .5))
    tw, th = img.width, int(img.width * rh / rw)
    if th > img.height:
        th, tw = img.height, int(img.height * rw / rh)
    x, y = int((img.width - tw) * cx), int((img.height - th) * cy)
    return enc(img.crop((x, y, x + tw, y + th)), fmt, q)

def t_adjust(img, p, fmt, q):
    f = lambda k: 1 + float(p.get(k, 0)) / 100
    def go(im):
        if p.get("auto"):
            im = ImageOps.autocontrast(im, cutoff=1)
        im = ImageEnhance.Brightness(im).enhance(f("brightness"))
        im = ImageEnhance.Contrast(im).enhance(f("contrast"))
        im = ImageEnhance.Color(im).enhance(f("color"))
        return ImageEnhance.Sharpness(im).enhance(f("sharpness"))
    return enc(rgb_op(img, go), fmt, q)

def t_filter(img, p, fmt, q):
    name = p.get("name", "gray")
    def go(im):
        if name == "gray":
            return ImageOps.grayscale(im).convert("RGB")
        if name == "sepia":
            return ImageOps.colorize(ImageOps.grayscale(im), "#2b1a0a", "#f5deb3")
        if name == "bw":
            return ImageOps.grayscale(im).point(lambda i: 255 if i > 128 else 0).convert("RGB")
        if name == "invert":
            return ImageOps.invert(im)
        if name == "blur":
            return im.filter(ImageFilter.GaussianBlur(max(2, im.width // 150)))
        if name == "sharpen":
            return im.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=2))
        if name == "emboss":
            return im.filter(ImageFilter.EMBOSS)
        if name == "edges":
            return ImageOps.invert(ImageOps.grayscale(im).filter(ImageFilter.FIND_EDGES)).convert("RGB")
        if name == "warm":
            r, g, b = im.split()
            return Image.merge("RGB", (r.point(lambda i: min(255, int(i * 1.12))), g, b.point(lambda i: int(i * .88))))
        if name == "cool":
            r, g, b = im.split()
            return Image.merge("RGB", (r.point(lambda i: int(i * .88)), g, b.point(lambda i: min(255, int(i * 1.12)))))
        if name == "poster":
            return ImageOps.posterize(im, 3)
        return im
    return enc(rgb_op(img, go), fmt, q)

def t_rotate(img, p, fmt, q):
    ang = float(p.get("angle", 0))
    if p.get("flip_h"):
        img = ImageOps.mirror(img)
    if p.get("flip_v"):
        img = ImageOps.flip(img)
    if ang % 360:
        img = img.convert("RGBA").rotate(-ang, expand=True, resample=Image.Resampling.BICUBIC)
    return enc(img, fmt, q)

def t_watermark(img, p, fmt, q):
    base = img.convert("RGBA")
    W, H = base.size
    text = str(p.get("text") or "@mybot")[:60]
    sz = max(10, int(W * float(p.get("size", 5)) / 100))
    op = int(255 * float(p.get("opacity", 60)) / 100)
    col = hex_rgb(p.get("color", "#ffffff")) + (op,)
    stroke = (0, 0, 0, op)
    fnt = get_font(sz)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sw = max(1, sz // 18)
    bb = d.textbbox((0, 0), text, font=fnt, stroke_width=sw)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pos = p.get("position", "br")
    if pos == "tile":
        tile = Image.new("RGBA", (tw + sz * 2, th + sz * 2), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((sz, sz), text, font=fnt, fill=col, stroke_width=sw, stroke_fill=stroke)
        tile = tile.rotate(30, expand=True, resample=Image.Resampling.BICUBIC)
        for y in range(-tile.height // 2, H, tile.height):
            for x in range(-tile.width // 2, W, tile.width):
                layer.paste(tile, (x, y), tile)
    else:
        m = int(W * .03)
        xy = {"tl": (m, m), "tr": (W - tw - m, m), "bl": (m, H - th - m),
              "br": (W - tw - m, H - th - m), "c": ((W - tw) // 2, (H - th) // 2)}.get(pos, (m, m))
        d.text((xy[0] - bb[0], xy[1] - bb[1]), text, font=fnt, fill=col, stroke_width=sw, stroke_fill=stroke)
    return enc(Image.alpha_composite(base, layer), fmt, q)

def t_round(img, p, fmt, q):
    r = float(p.get("radius", 50)) / 100
    if r >= .5:  # doira
        s = min(img.size)
        img = ImageOps.fit(img, (s, s), LANCZOS)
    W, H = img.size
    mask = Image.new("L", (W * 4, H * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W * 4 - 1, H * 4 - 1), radius=int(min(W, H) * 4 * r), fill=255)
    mask = mask.resize((W, H), LANCZOS)
    img = img.convert("RGBA")
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return enc(img, "PNG")

def t_sticker(img, p, fmt, q):
    img = ImageOps.contain(img.convert("RGBA"), (512, 512), LANCZOS)
    quality = 92
    out = enc(img, "WEBP", quality)
    while len(out[0]) > 500 * 1024 and quality > 30:
        quality -= 12
        out = enc(img, "WEBP", quality)
    return out

def t_border(img, p, fmt, q):
    n = max(0, min(int(p.get("size", 40)), 1000))
    col = hex_rgb(p.get("color", "#ffffff")) + (255,)
    return enc(ImageOps.expand(img.convert("RGBA"), n, col), fmt, q)

def t_scan(img, p, fmt, q):
    g = ImageOps.grayscale(img.convert("RGB"))
    if p.get("mode", "bw") == "bw":
        bg = g.filter(ImageFilter.GaussianBlur(max(15, img.width // 40)))
        g = ImageOps.invert(ImageChops.subtract(bg, g))  # soyani yo'qotadi, matn qoladi
        g = ImageOps.autocontrast(g, cutoff=2).point(lambda i: 255 if i > 165 else int(i * .55))
    else:
        g = ImageOps.autocontrast(g, cutoff=1)
    return enc(g.convert("RGB"), p.get("format", "PDF"), q)

def t_strip(img, p, fmt, q, orig):
    f = {"JPEG": "JPG", "PNG": "PNG", "WEBP": "WEBP"}.get(orig or "", "PNG")
    return enc(img, f, 95)

def t_topdf(imgs, p):
    pages = []
    for im in imgs:
        im = flat(im)
        if p.get("a4"):
            canvas = Image.new("RGB", (1240, 1754), "white")
            im = ImageOps.contain(im, (1160, 1674), LANCZOS)
            canvas.paste(im, ((1240 - im.width) // 2, (1754 - im.height) // 2))
            im = canvas
        pages.append(im)
    b = io.BytesIO()
    pages[0].save(b, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    return b.getvalue(), "pdf", MEDIA["pdf"]

ACTIONS = {"convert", "resize", "compress", "crop", "adjust", "filter", "rotate", "watermark",
           "round", "sticker", "border", "scan", "strip", "topdf"}

def work(action, datas, p):
    loaded = [load(d) for d in datas]
    imgs = [x[0] for x in loaded]
    img, orig = imgs[0], loaded[0][1]
    fmt = str(p.get("format", "PNG")).upper()
    q = max(5, min(int(p.get("quality", 90)), 100))
    if action == "topdf":
        return t_topdf(imgs, p)
    if action == "convert": return enc(img, fmt, q)
    if action == "resize": return t_resize(img, p, fmt, q)
    if action == "compress": return t_compress(img, p, fmt, q)
    if action == "crop": return t_crop(img, p, fmt, q)
    if action == "adjust": return t_adjust(img, p, fmt, q)
    if action == "filter": return t_filter(img, p, fmt, q)
    if action == "rotate": return t_rotate(img, p, fmt, q)
    if action == "watermark": return t_watermark(img, p, fmt, q)
    if action == "round": return t_round(img, p, fmt, q)
    if action == "sticker": return t_sticker(img, p, fmt, q)
    if action == "border": return t_border(img, p, fmt, q)
    if action == "scan": return t_scan(img, p, fmt, q)
    if action == "strip": return t_strip(img, p, fmt, q, orig)
    raise HTTPException(400, "Noma'lum amal")

# ───────────────────────── API ─────────────────────────
@app.post("/api/process")
async def process(action: str = Form(...), params: str = Form("{}"),
                  files: List[UploadFile] = File(...),
                  init_data: str = Header("", alias="X-Telegram-Init-Data")):
    require_user(init_data)
    if action not in ACTIONS:
        raise HTTPException(400, "Noma'lum amal")
    if not files or len(files) > 30:
        raise HTTPException(400, "1 tadan 30 tagacha rasm yuboring")
    try:
        p = json.loads(params)
        assert isinstance(p, dict)
    except Exception:
        raise HTTPException(400, "Parametrlar noto'g'ri")
    datas = []
    for f in files:
        d = await f.read()
        if len(d) > MAX_MB * 1024 * 1024:
            raise HTTPException(413, f"Fayl {MAX_MB} MB dan katta")
        datas.append(d)
    try:
        out, ext, media = await run_in_threadpool(work, action, datas, p)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Qayta ishlashda xato: {type(e).__name__}")
    return Response(out, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{uuid.uuid4().hex[:10]}.{ext}"'})

@app.post("/api/send")
async def send(file: UploadFile = File(...), caption: str = Form(""),
               init_data: str = Header("", alias="X-Telegram-Init-Data")):
    """Natijani foydalanuvchining bot bilan chatiga hujjat sifatida yuboradi."""
    u = require_user(init_data)
    if not u.get("id"):
        raise HTTPException(400, "Chatga yuborish faqat Telegram ichida ishlaydi")
    data = await file.read()
    if len(data) > 49 * 1024 * 1024:
        raise HTTPException(413, "Fayl Telegram limitidan katta")
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                         data={"chat_id": u["id"], "caption": caption[:200]},
                         files={"document": (file.filename or "result", data, file.content_type or "application/octet-stream")})
    if r.status_code != 200:
        try:
            msg = r.json().get("description", "Telegram xatosi")
        except Exception:
            msg = "Telegram xatosi"
        if "initiate" in msg or "blocked" in msg:
            msg = "Avval botga kirib /start bosing, keyin qayta urinib ko'ring"
        raise HTTPException(502, msg)
    return {"ok": True}

@app.get("/health")
async def health():
    return {"ok": True}

# ───────────────────────── FRONTEND ─────────────────────────
HTML = r"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">
<title>Image Tools</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--paper:#f2f4f6;--surface:#ffffff;--ink:#11151b;--mute:#667080;--line:#d9dee5;--cyan:#0096b8;--mag:#e0246f;--magfg:#fff;--ok:#0a8f5b;--err:#c62828}
:root.dark{--paper:#0f1318;--surface:#181e26;--ink:#eef1f5;--mute:#8b96a6;--line:#29323e;--cyan:#38c4e3;--mag:#ff4f93;--magfg:#1a0610;--ok:#3ddc97;--err:#ff6b6b}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--paper);color:var(--ink);padding:14px 14px 110px;min-height:100vh;line-height:1.4}
h1{font-size:22px;font-weight:800;letter-spacing:-.02em}
.sub{color:var(--mute);font-size:13px;margin:2px 0 14px}
.strip{display:flex;gap:8px;overflow-x:auto;padding:2px 0 10px;margin:0 -14px;padding-left:14px;padding-right:14px;scrollbar-width:none;position:sticky;top:0;background:var(--paper);z-index:5}
.strip::-webkit-scrollbar{display:none}
.tool{flex:0 0 auto;display:flex;align-items:center;gap:6px;background:var(--surface);border:1.5px solid var(--line);color:var(--ink);padding:9px 13px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer}
.tool.on{border-color:var(--mag);box-shadow:inset 0 -3px 0 var(--mag)}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;margin-top:12px}
.hint{font-size:13px;color:var(--mute);margin-bottom:4px}
.drop{position:relative;display:block;text-align:center;padding:30px 16px;border-radius:6px;cursor:pointer;background:var(--paper)}
.drop:before,.drop:after,.drop i:before,.drop i:after{content:"";position:absolute;width:18px;height:18px;border:0 solid var(--cyan)}
.drop:before{top:6px;left:6px;border-width:3px 0 0 3px}.drop:after{top:6px;right:6px;border-width:3px 3px 0 0}
.drop i:before{bottom:6px;left:6px;border-width:0 0 3px 3px}.drop i:after{bottom:6px;right:6px;border-width:0 3px 3px 0}
.drop b{display:block;font-size:16px}.drop small{color:var(--mute)}
.drop.over{background:var(--line)}
input[type=file]{display:none}
.files{margin-top:10px;display:grid;gap:8px}
.file{display:flex;align-items:center;gap:10px;background:var(--paper);border-radius:10px;padding:6px}
.file .th{width:54px;height:54px;border-radius:7px;background:var(--line);object-fit:cover;display:grid;place-items:center;font-size:22px;flex:none}
.file .nm{flex:1;min-width:0}.file .nm b{display:block;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.file .nm span{font-size:12px;color:var(--mute)}
.x{border:0;background:none;color:var(--mute);font-size:20px;padding:8px 10px;cursor:pointer}
label{display:flex;justify-content:space-between;font-size:13px;color:var(--mute);margin:12px 0 5px;font-weight:600}
label b{color:var(--ink)}
input[type=number],input[type=text],select{width:100%;background:var(--paper);border:1.5px solid var(--line);color:var(--ink);padding:11px 12px;border-radius:10px;font-size:15px;outline:none}
input:focus,select:focus{border-color:var(--cyan)}
input[type=range]{width:100%;accent-color:var(--mag)}
input[type=color]{width:100%;height:44px;border:1.5px solid var(--line);border-radius:10px;background:var(--paper);padding:3px}
.chk{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:15px;cursor:pointer}
.chk input{width:20px;height:20px;accent-color:var(--mag)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.hidden{display:none!important}
.bar{position:fixed;left:0;right:0;bottom:0;padding:10px 14px calc(10px + env(safe-area-inset-bottom));background:var(--paper);border-top:1px solid var(--line);z-index:9}
.go{width:100%;border:0;background:var(--mag);color:var(--magfg);padding:15px;border-radius:12px;font-size:16px;font-weight:800;cursor:pointer}
.go:disabled{opacity:.5}
.st{font-size:13px;text-align:center;margin-top:6px;min-height:18px;color:var(--mute)}.st.ok{color:var(--ok)}.st.err{color:var(--err)}
.res{margin-top:12px}
.rv{position:relative;padding:14px;background:var(--paper);border-radius:6px;text-align:center}
.rv:before,.rv:after,.rv i:before,.rv i:after{content:"";position:absolute;width:14px;height:14px;border:0 solid var(--mag)}
.rv:before{top:4px;left:4px;border-width:3px 0 0 3px}.rv:after{top:4px;right:4px;border-width:3px 3px 0 0}
.rv i:before{bottom:4px;left:4px;border-width:0 0 3px 3px}.rv i:after{bottom:4px;right:4px;border-width:0 3px 3px 0}
.rv img{max-width:100%;max-height:340px;border-radius:4px;background:repeating-conic-gradient(#8883 0 25%,transparent 0 50%) 0 0/16px 16px}
.rv .pdf{font-size:46px}
.info{font-size:13px;color:var(--mute);margin:8px 0;text-align:center}.info b{color:var(--ok)}
.acts{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.acts button{border:1.5px solid var(--line);background:var(--surface);color:var(--ink);padding:12px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer}
.acts .main{grid-column:1/-1;background:var(--cyan);border-color:var(--cyan);color:#fff}
</style></head><body>
<h1>Image Tools</h1>
<p class="sub">Rasmlarni telefonda o'zgartiring: format, o'lcham, siqish, filtr va boshqalar.</p>
<div class="strip" id="tools"></div>

<div class="panel">
  <label class="drop" id="drop" for="file"><i></i><b>📷 Rasm tanlang</b><small id="dropHint">Galereyadan tanlang yoki bu yerga tashlang</small></label>
  <input type="file" id="file" accept="image/*,.heic,.heif" multiple>
  <div class="files" id="files"></div>
</div>

<div class="panel"><div class="hint" id="hint"></div><div id="opts"></div></div>
<div id="results"></div>

<div class="bar"><button class="go" id="run">Bajarish</button><div class="st" id="st"></div></div>

<script>
const tg=window.Telegram&&window.Telegram.WebApp; if(tg){tg.ready();tg.expand();}
const dark=(tg&&tg.colorScheme)?tg.colorScheme==="dark":matchMedia("(prefers-color-scheme: dark)").matches;
document.documentElement.classList.toggle("dark",dark);
const $=s=>document.querySelector(s);
const kb=n=>n>=1048576?(n/1048576).toFixed(2)+" MB":Math.max(1,Math.round(n/1024))+" KB";
const hap=t=>{try{tg.HapticFeedback.notificationOccurred(t)}catch(e){}};
const INIT=(tg&&tg.initData)||"";

const FMT=(o,v)=>({k:"format",l:"Format",t:"select",o:o,v:v});
const QLT={k:"quality",l:"Sifat",t:"range",min:10,max:100,v:90,u:"%"};
const T={
convert:{i:"🔄",n:"Format",h:"Rasmni boshqa formatga o'tkazing. PNG shaffoflikni saqlaydi, JPG kichik hajm beradi.",f:[FMT(["PNG","JPG","WEBP","BMP","GIF","TIFF","PDF"],"PNG"),QLT]},
resize:{i:"📐",n:"O'lcham",h:"Tayyor o'lchamni tanlang yoki o'zingiz kiriting. Nisbat buzilmaydi.",f:[
 {t:"preset",l:"Tayyor o'lcham",o:[["","Tanlang..."],["1080x1080","Instagram post 1080×1080"],["1080x1920","Stories / Reels 1080×1920"],["512x512","Telegram avatar 512×512"],["1920x1080","Full HD 1920×1080"],["1280x720","HD 1280×720"],["3840x2160","4K 3840×2160"],["800x0","Kenglik 800 px"],["350x450","Hujjat 3.5×4.5 (350×450)"]]},
 {k:"mode",l:"Rejim",t:"select",o:[["px","Piksel"],["percent","Foiz"]],v:"px"},
 {k:"width",l:"Kenglik (px)",t:"number",v:1080,show:["mode","px"]},{k:"height",l:"Balandlik (px, ixtiyoriy)",t:"number",v:"",show:["mode","px"]},
 {k:"percent",l:"Foiz",t:"range",min:5,max:300,v:50,u:"%",show:["mode","percent"]},
 {k:"keep",l:"Nisbatni saqlash",t:"check",v:true,show:["mode","px"]},FMT(["JPG","PNG","WEBP"],"JPG"),QLT]},
compress:{i:"🗜",n:"Siqish",h:"Hajmni kichraytiring. Aniq hajm (KB) kiritsangiz, shunga yaqinlashtiramiz.",f:[
 {k:"target_kb",l:"Maqsad hajm (KB, ixtiyoriy)",t:"number",v:"",ph:"masalan 200"},
 {k:"quality",l:"Sifat",t:"range",min:10,max:95,v:70,u:"%"},FMT(["JPG","WEBP"],"JPG")]},
crop:{i:"✂️",n:"Kesish",h:"Rasmni tanlangan nisbatda kesing. Eng katta mumkin bo'lgan qism olinadi.",f:[
 {k:"ratio",l:"Nisbat",t:"select",o:["1:1","4:5","3:4","4:3","16:9","9:16","3:2","2:3"],v:"1:1"},
 {k:"pos",l:"Qaysi qismi qolsin",t:"select",o:[["center","Markaz"],["top","Yuqori"],["bottom","Pastki"],["left","Chap"],["right","O'ng"]],v:"center"},FMT(["JPG","PNG","WEBP"],"JPG"),QLT]},
adjust:{i:"🎚",n:"Sozlash",h:"Yorug'lik, kontrast, rang va ravshanlikni sozlang.",f:[
 {k:"auto",l:"Avto-yaxshilash",t:"check",v:false},
 {k:"brightness",l:"Yorug'lik",t:"range",min:-60,max:60,v:6},{k:"contrast",l:"Kontrast",t:"range",min:-60,max:60,v:12},
 {k:"color",l:"Rang to'yinishi",t:"range",min:-100,max:100,v:10},{k:"sharpness",l:"Ravshanlik",t:"range",min:-100,max:200,v:35},FMT(["JPG","PNG","WEBP"],"JPG"),QLT]},
filter:{i:"🎨",n:"Filtr",h:"Tayyor effektlardan birini qo'llang.",f:[
 {k:"name",l:"Effekt",t:"select",o:[["gray","Oq-qora"],["sepia","Sepiya"],["bw","Qora-oq (kontrast)"],["warm","Iliq"],["cool","Sovuq"],["invert","Teskari ranglar"],["blur","Xira"],["sharpen","Ravshan"],["emboss","Relyef"],["edges","Chizma"],["poster","Poster"]],v:"gray"},FMT(["JPG","PNG","WEBP"],"JPG"),QLT]},
rotate:{i:"🔃",n:"Aylantirish",h:"Aylantiring yoki akslantiring.",f:[
 {k:"angle",l:"Burchak",t:"range",min:-180,max:180,v:90,u:"°"},{k:"flip_h",l:"Gorizontal akslantirish",t:"check",v:false},{k:"flip_v",l:"Vertikal akslantirish",t:"check",v:false},FMT(["PNG","JPG","WEBP"],"PNG"),QLT]},
watermark:{i:"💧",n:"Suv belgisi",h:"Rasmingizga matn yozing: kanal nomi, ism yoki himoya belgisi.",f:[
 {k:"text",l:"Matn",t:"text",v:"@kanalim"},
 {k:"position",l:"Joyi",t:"select",o:[["br","Pastki o'ng"],["bl","Pastki chap"],["tr","Yuqori o'ng"],["tl","Yuqori chap"],["c","Markaz"],["tile","Butun rasm bo'ylab"]],v:"br"},
 {k:"size",l:"Matn kattaligi",t:"range",min:2,max:20,v:6,u:"%"},{k:"opacity",l:"Shaffoflik",t:"range",min:10,max:100,v:65,u:"%"},{k:"color",l:"Rang",t:"color",v:"#ffffff"},FMT(["JPG","PNG","WEBP"],"JPG"),QLT]},
round:{i:"⭕",n:"Yumaloq",h:"Burchaklarni yumaloqlang yoki avatar uchun doira qiling. Natija PNG bo'ladi.",f:[
 {k:"radius",l:"Yumaloqlik (50 = doira)",t:"range",min:0,max:50,v:50,u:"%"}]},
sticker:{i:"🏷",n:"Stiker",h:"Telegram stikeri uchun 512 px WEBP tayyorlaydi. Keyin @Stickers botiga yuboring.",f:[]},
border:{i:"🖼",n:"Ramka",h:"Rasm atrofiga rangli ramka qo'shing.",f:[
 {k:"size",l:"Qalinlik (px)",t:"range",min:0,max:300,v:40,u:"px"},{k:"color",l:"Rang",t:"color",v:"#ffffff"},FMT(["PNG","JPG","WEBP"],"PNG"),QLT]},
scan:{i:"📄",n:"Skaner",h:"Daftar yoki hujjat rasmini toza skaner ko'rinishiga keltiradi. Soya yo'qoladi.",f:[
 {k:"mode",l:"Ko'rinish",t:"select",o:[["bw","Oq-qora hujjat"],["gray","Kulrang"]],v:"bw"},FMT(["PDF","PNG","JPG"],"PDF"),QLT]},
topdf:{i:"📚",n:"PDF yig'ish",h:"Bir nechta rasmni tanlang. Hammasi bitta PDF fayl bo'ladi, tartib tanlash bo'yicha.",f:[
 {k:"a4",l:"A4 varaqqa joylash",t:"check",v:true}]},
strip:{i:"🛡",n:"Maxfiylik",h:"Rasmdagi yashirin ma'lumot (joylashuv, kamera, vaqt) o'chiriladi. Ko'rinishi o'zgarmaydi.",f:[]}
};
let action="convert",files=[],results=[],busy=false;
const meta={};

$("#tools").innerHTML=Object.entries(T).map(([id,t])=>`<button class="tool" data-a="${id}">${t.i} ${t.n}</button>`).join("");
document.querySelectorAll(".tool").forEach(b=>b.onclick=()=>setAction(b.dataset.a));

function setAction(a){
 action=a;
 document.querySelectorAll(".tool").forEach(b=>b.classList.toggle("on",b.dataset.a===a));
 const t=T[a];$("#hint").textContent=t.h;
 $("#dropHint").textContent=a==="topdf"?"Bir nechta rasm tanlang (tartib bo'yicha)":"Galereyadan tanlang yoki bu yerga tashlang";
 $("#opts").innerHTML=t.f.length?t.f.map(fieldHtml).join(""):`<div class="hint">Qo'shimcha sozlama yo'q. Rasm tanlab "Bajarish" ni bosing.</div>`;
 $("#opts").oninput=refresh;refresh();
}
function fieldHtml(f){
 const sh=f.show?` data-show="${f.show[0]}=${f.show[1]}"`:"";
 const id=f.k?`f_${f.k}`:"preset";
 if(f.t==="check")return `<label class="chk"${sh}><input type="checkbox" id="${id}" ${f.v?"checked":""}>${f.l}</label>`;
 let c="";
 if(f.t==="select"||f.t==="preset")c=`<select id="${id}">${f.o.map(o=>{const[v,l]=Array.isArray(o)?o:[o,o];return `<option value="${v}" ${v===f.v?"selected":""}>${l}</option>`}).join("")}</select>`;
 else if(f.t==="range")c=`<input type="range" id="${id}" min="${f.min}" max="${f.max}" value="${f.v}">`;
 else if(f.t==="color")c=`<input type="color" id="${id}" value="${f.v}">`;
 else c=`<input type="${f.t}" id="${id}" value="${f.v??""}" placeholder="${f.ph||""}" ${f.t==="number"?'inputmode="numeric" min="0"':""}>`;
 return `<div${sh}><label>${f.l}${f.t==="range"?`<b id="o_${f.k}">${f.v}${f.u||""}</b>`:""}</label>${c}</div>`;
}
function refresh(e){
 const t=T[action];
 if(e&&e.target.id==="preset"&&e.target.value){const[w,h]=e.target.value.split("x");$("#f_mode").value="px";$("#f_width").value=w;$("#f_height").value=h==="0"?"":h;}
 t.f.forEach(f=>{if(f.t==="range"){const el=$("#f_"+f.k);if(el)$("#o_"+f.k).textContent=el.value+(f.u||"")}});
 document.querySelectorAll("[data-show]").forEach(el=>{const[k,v]=el.dataset.show.split("=");const s=$("#f_"+k);el.classList.toggle("hidden",!!s&&s.value!==v)});
}
function collect(){
 const p={};
 T[action].f.forEach(f=>{if(!f.k)return;const el=$("#f_"+f.k);if(!el)return;
  p[f.k]=f.t==="check"?el.checked:(f.t==="range"||f.t==="number")&&el.value!==""?Number(el.value):el.value;});
 return p;
}

// ── fayllar
function addFiles(list){
 const arr=[...list].filter(f=>f.type.startsWith("image/")||/\.(heic|heif)$/i.test(f.name));
 if(!arr.length)return say("Faqat rasm fayllari qabul qilinadi","err");
 files=action==="topdf"?files.concat(arr).slice(0,30):arr.slice(0,30);
 results=[];renderResults();renderFiles();
}
function renderFiles(){
 $("#files").innerHTML=files.map((f,i)=>{
  const url=meta[f.name+f.size]?.url||(meta[f.name+f.size]={url:URL.createObjectURL(f)}).url;
  return `<div class="file"><img class="th" src="${url}" onerror="this.outerHTML='<div class=th>🖼</div>'"><div class="nm"><b>${f.name}</b><span>${kb(f.size)}<span id="d${i}"></span></span></div><button class="x" onclick="rm(${i})">✕</button></div>`}).join("");
 files.forEach((f,i)=>{const im=new Image();im.onload=()=>{const e=$("#d"+i);if(e)e.textContent=" · "+im.naturalWidth+"×"+im.naturalHeight};im.src=meta[f.name+f.size].url});
}
function rm(i){files.splice(i,1);renderFiles()}
$("#file").onchange=e=>{addFiles(e.target.files);e.target.value=""};
const dz=$("#drop");
["dragenter","dragover"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add("over")}));
["dragleave","drop"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove("over")}));
dz.addEventListener("drop",e=>addFiles(e.dataTransfer.files));

// ── ishga tushirish
function say(m,c){const s=$("#st");s.textContent=m;s.className="st "+(c||"")}
async function errText(r){const t=await r.text();try{return JSON.parse(t).detail||t}catch(e){return t}}
async function run(){
 if(busy)return;
 if(!files.length)return say("Avval rasm tanlang","err");
 busy=true;$("#run").disabled=true;results=[];renderResults();
 try{
  const p=collect();
  const jobs=action==="topdf"?[files]:files.map(f=>[f]);
  for(let i=0;i<jobs.length;i++){
   say(`⏳ Ishlanmoqda ${i+1}/${jobs.length}...`);
   const fd=new FormData();fd.append("action",action);fd.append("params",JSON.stringify(p));
   jobs[i].forEach(f=>fd.append("files",f));
   const r=await fetch("/api/process",{method:"POST",body:fd,headers:{"X-Telegram-Init-Data":INIT}});
   if(!r.ok)throw new Error(await errText(r));
   const blob=await r.blob();
   const m=/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition")||"");
   const ext=m?m[1].split(".").pop():"png";
   const base=jobs[i][0].name.replace(/\.[^.]+$/,"");
   results.push({blob,name:`${base}_${action}.${ext}`,url:URL.createObjectURL(blob),orig:jobs[i].reduce((a,f)=>a+f.size,0)});
  }
  renderResults();say("✅ Tayyor!","ok");hap("success");
  $("#results").scrollIntoView({behavior:"smooth"});
 }catch(e){say("❌ "+e.message,"err");hap("error")}
 finally{busy=false;$("#run").disabled=false}
}
$("#run").onclick=run;

// ── natija
function renderResults(){
 $("#results").innerHTML=results.length?`<div class="panel res">`+results.map((r,i)=>{
  const isImg=r.blob.type.startsWith("image/");
  const diff=Math.round((1-r.blob.size/r.orig)*100);
  const info=`${kb(r.orig)} → <b>${kb(r.blob.size)}</b>${action!=="topdf"&&diff>0?` (−${diff}%)`:""}`;
  return `<div style="margin-bottom:16px"><div class="rv"><i></i>${isImg?`<img src="${r.url}">`:`<div class="pdf">📄</div><div>${r.name}</div>`}</div>
  <div class="info">${info}</div>
  <div class="acts"><button class="main" onclick="sendRes(${i})">📨 Chatga yuborish</button>
  <button onclick="dl(${i})">⬇️ Yuklab olish</button>${isImg?`<button onclick="cont(${i})">🔁 Davom ettirish</button>`:"<span></span>"}</div></div>`}).join("")
  +(results.length>1?`<div class="acts"><button class="main" onclick="sendAll()">📨 Hammasini yuborish (${results.length})</button></div>`:"")+`</div>`:"";
}
async function sendOne(i){
 const r=results[i];const fd=new FormData();
 fd.append("file",new File([r.blob],r.name,{type:r.blob.type}));
 const x=await fetch("/api/send",{method:"POST",body:fd,headers:{"X-Telegram-Init-Data":INIT}});
 if(!x.ok)throw new Error(await errText(x));
}
async function sendRes(i){
 if(!INIT)return dl(i);
 try{say("📨 Yuborilmoqda...");await sendOne(i);say("✅ Chatga yuborildi","ok");hap("success")}
 catch(e){say("❌ "+e.message,"err");hap("error")}
}
async function sendAll(){
 if(!INIT)return results.forEach((_,i)=>dl(i));
 try{for(let i=0;i<results.length;i++){say(`📨 Yuborilmoqda ${i+1}/${results.length}...`);await sendOne(i)}say("✅ Hammasi chatga yuborildi","ok");hap("success")}
 catch(e){say("❌ "+e.message,"err")}
}
function dl(i){
 const r=results[i];const a=document.createElement("a");a.href=r.url;a.download=r.name;document.body.appendChild(a);a.click();a.remove();
 if(INIT)say("Telegramda yuklash ishlamasa, «Chatga yuborish» ni bosing");
}
function cont(i){
 const r=results[i];files=[new File([r.blob],r.name,{type:r.blob.type})];results=[];renderResults();renderFiles();
 window.scrollTo({top:0,behavior:"smooth"});say("Natija yangi rasm sifatida olindi. Boshqa vositani tanlang.","ok");
}
setAction("convert");
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML
