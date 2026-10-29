"""Qo'shimcha rasm vositalari (faqat Pillow, tashqi API yo'q)."""
import io, math, zipfile
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageChops, ExifTags
from core import enc, flat, rgb_op, hex_rgb, get_font, load, LANCZOS, HTTPException


def _zip(items):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in items:
            z.writestr(n, d)
    return b.getvalue(), "zip", "application/zip"


def _wrap(d, t, f, maxw):
    lines, cur = [], ""
    for w in t.split():
        c = (cur + " " + w).strip()
        if d.textlength(c, font=f) <= maxw:
            cur = c
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ───────── qo'shimcha filtr effektlari (filtr vositasi ishlatadi) ─────────
def fx_sketch(im): return ImageOps.autocontrast(ImageOps.grayscale(im).filter(ImageFilter.CONTOUR)).convert("RGB")
def fx_grain(im): return ImageChops.add(im, Image.effect_noise(im.size, 40).convert("RGB"), 1, -128)
def fx_duotone(im): return ImageOps.colorize(ImageOps.grayscale(im), "#1b1464", "#ff6fb5")
def fx_glow(im): return ImageChops.screen(im, im.filter(ImageFilter.GaussianBlur(max(3, im.width // 70))))
def fx_vintage(im): return Image.blend(ImageOps.colorize(ImageOps.grayscale(im), "#3a2a1a", "#f2e2c4"), im, .3)

def fx_vignette(im):
    m = Image.radial_gradient("L").resize(im.size, LANCZOS).point(lambda v: int(max(0, v - 90) * 1.25))
    return Image.composite(Image.new("RGB", im.size, "black"), im, m)

def fx_cartoon(im):
    p = ImageOps.posterize(im.filter(ImageFilter.MedianFilter(5)), 3)
    e = ImageOps.invert(ImageOps.grayscale(im).filter(ImageFilter.FIND_EDGES)).point(lambda v: 0 if v < 215 else 255)
    return ImageChops.multiply(p, e.convert("RGB"))

def fx_mirror(im):
    w, h = im.size
    o = im.copy()
    o.paste(ImageOps.mirror(im.crop((0, 0, w // 2, h))), (w - w // 2, 0))
    return o

FX = {"sketch": fx_sketch, "grain": fx_grain, "duotone": fx_duotone, "glow": fx_glow,
      "vintage": fx_vintage, "vignette": fx_vignette, "cartoon": fx_cartoon, "mirror": fx_mirror}


# ───────── vositalar: hammasi (imgs, p, fmt, q) -> (bytes, ext, media) ─────────
def x_collage(imgs, p, fmt, q):
    if len(imgs) < 2:
        raise HTTPException(400, "Kollaj uchun kamida 2 ta rasm tanlang")
    n = len(imgs)
    cols = int(p.get("cols") or 0) or math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell, gap = int(p.get("cell", 600)), int(p.get("gap", 12))
    out = Image.new("RGB", (cols * cell + (cols + 1) * gap, rows * cell + (rows + 1) * gap), hex_rgb(p.get("bg", "#ffffff")))
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        out.paste(ImageOps.fit(flat(im), (cell, cell), LANCZOS), (gap + c * (cell + gap), gap + r * (cell + gap)))
    return enc(out, fmt, q)


def x_gif(imgs, p, fmt, q):
    if len(imgs) < 2:
        raise HTTPException(400, "GIF uchun kamida 2 ta rasm tanlang")
    w = min(720, imgs[0].width)
    h = int(imgs[0].height * w / imgs[0].width)
    fr = [ImageOps.fit(flat(i), (w, h), LANCZOS) for i in imgs]
    b = io.BytesIO()
    fr[0].save(b, "GIF", save_all=True, append_images=fr[1:], duration=int(p.get("ms", 500)), loop=0, optimize=True)
    return b.getvalue(), "gif", "image/gif"


def _meme_text(d, W, H, t, top):
    sz = int(W * .11)
    while True:
        f = get_font(sz)
        lines = _wrap(d, t, f, W * .94)
        if (len(lines) <= 3 and all(d.textlength(l, font=f) <= W * .96 for l in lines)) or sz <= 16:
            break
        sz -= 3
    sw, lh = max(2, sz // 9), int(sz * 1.15)
    y = int(H * .02) if top else H - int(H * .02) - lh * len(lines)
    for l in lines:
        d.text(((W - d.textlength(l, font=f)) / 2, y), l, font=f, fill="white", stroke_width=sw, stroke_fill="black")
        y += lh


def x_meme(imgs, p, fmt, q):
    im = imgs[0].convert("RGBA")
    d = ImageDraw.Draw(im)
    for key, top in (("top", True), ("bottom", False)):
        t = str(p.get(key) or "").upper().strip()[:120]
        if t:
            _meme_text(d, im.width, im.height, t, top)
    return enc(im, fmt, q)


def x_poster(imgs, p, fmt, q):
    try:
        W, H = (int(v) for v in str(p.get("size", "1080x1080")).split("x"))
    except Exception:
        W, H = 1080, 1080
    if imgs:
        bg = ImageOps.fit(flat(imgs[0]), (W, H), LANCZOS)
        bg = Image.blend(bg, Image.new("RGB", (W, H), "black"), .45)
    else:
        c1, c2 = hex_rgb(p.get("c1", "#2b1055")), hex_rgb(p.get("c2", "#d53369"))
        g = Image.linear_gradient("L").resize((W, H))
        bg = Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), g)
    d = ImageDraw.Draw(bg)
    text = str(p.get("text") or "Matn yozing").strip()[:400]
    col = hex_rgb(p.get("color", "#ffffff"))
    sz = int(W * .09)
    while sz > 20:
        f = get_font(sz)
        lines = _wrap(d, text, f, W * .8)
        if len(lines) * sz * 1.3 <= H * .6:
            break
        sz -= 4
    block = len(lines) * int(sz * 1.3)
    y = (H - block) // 2
    for l in lines:
        d.text(((W - d.textlength(l, font=f)) / 2, y), l, font=f, fill=col)
        y += int(sz * 1.3)
    a = str(p.get("author") or "").strip()[:60]
    if a:
        fa = get_font(int(sz * .5))
        d.text(((W - d.textlength("— " + a, font=fa)) / 2, y + sz * .5), "— " + a, font=fa, fill=col)
    return enc(bg, fmt, q)


def x_passport(imgs, p, fmt, q):
    try:
        wc, hc = (float(v) for v in str(p.get("size", "3.5x4.5")).split("x"))
    except Exception:
        wc, hc = 3.5, 4.5
    pw, ph = int(wc / 2.54 * 300), int(hc / 2.54 * 300)
    pic = ImageOps.fit(flat(imgs[0]), (pw, ph), LANCZOS, centering=(.5, .35))
    sheet = {"a4": (2480, 3508), "10x15": (1181, 1772)}.get(p.get("sheet", "10x15"), (1181, 1772))
    gap = 20
    cols, rows = max(1, (sheet[0] - gap) // (pw + gap)), max(1, (sheet[1] - gap) // (ph + gap))
    n = min(int(p.get("copies", 6)), cols * rows)
    cv = Image.new("RGB", sheet, "white")
    x0 = (sheet[0] - (cols * (pw + gap) - gap)) // 2
    for i in range(n):
        r, c = divmod(i, cols)
        cv.paste(pic, (x0 + c * (pw + gap), gap + r * (ph + gap)))
    return enc(cv, fmt, q)


def x_palette(imgs, p, fmt, q):
    n = max(3, min(int(p.get("n", 6)), 10))
    pal = flat(imgs[0]).resize((160, 160)).quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    raw = pal.getpalette()[:n * 3]
    n = min(n, len(raw) // 3)
    cnt = {i: c for c, i in pal.getcolors()}
    cols = [tuple(raw[i * 3:i * 3 + 3]) for i in sorted(range(n), key=lambda i: -cnt.get(i, 0))]
    img = Image.new("RGB", (1200, n * 120))
    d, f = ImageDraw.Draw(img), get_font(44)
    for k, c in enumerate(cols):
        d.rectangle((0, k * 120, 1200, k * 120 + 120), fill=c)
        lum = .299 * c[0] + .587 * c[1] + .114 * c[2]
        d.text((40, k * 120 + 30), "#%02X%02X%02X    rgb%s" % (c + (c,)), font=f, fill="black" if lum > 150 else "white")
    return enc(img, "PNG")


def x_split(imgs, p, fmt, q):
    im = imgs[0]
    cols = max(1, min(int(p.get("cols", 3)), 6))
    rows = 1 if p.get("mode", "cols") == "cols" else max(1, min(int(p.get("rows", 3)), 6))
    cw, ch = im.width // cols, im.height // rows
    items = []
    for r in range(rows):
        for c in range(cols):
            d, ext, _ = enc(im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)), fmt, q)
            items.append((f"part_{r * cols + c + 1}.{ext}", d))
    return _zip(items)


def x_fill(imgs, p, fmt, q):
    bg, im = hex_rgb(p.get("bg", "#ffffff")), imgs[0]
    base = flat(im, bg)
    if p.get("square"):
        s = max(im.size)
        cv = Image.new("RGB", (s, s), bg)
        cv.paste(base, ((s - im.width) // 2, (s - im.height) // 2))
        return enc(cv, fmt, q)
    return enc(base, fmt, q)


def x_pixelate(imgs, p, fmt, q):
    im = imgs[0].convert("RGBA")
    W, H = im.size
    k = max(2, int(p.get("strength", 15)))
    if p.get("area") == "box":
        x, y = int(W * float(p.get("x", 25)) / 100), int(H * float(p.get("y", 25)) / 100)
        box = (x, y, min(W, x + int(W * float(p.get("w", 50)) / 100)), min(H, y + int(H * float(p.get("h", 50)) / 100)))
    else:
        box = (0, 0, W, H)
    if box[2] <= box[0] or box[3] <= box[1]:
        raise HTTPException(400, "Maydon noto'g'ri")
    reg = im.crop(box)
    if p.get("type") == "blur":
        reg = reg.filter(ImageFilter.GaussianBlur(max(2, k * max(W, H) // 250)))
    else:
        b = max(2, int(k * max(W, H) / 400))
        reg = reg.resize((max(1, reg.width // b), max(1, reg.height // b)), Image.Resampling.BILINEAR).resize(reg.size, Image.Resampling.NEAREST)
    im.paste(reg, box[:2])
    return enc(im, fmt, q)


def x_mockup(imgs, p, fmt, q):
    s = flat(imgs[0])
    s = s.resize((800, int(s.height * 800 / s.width)), LANCZOS)
    if s.height > 2200:
        s = ImageOps.fit(s, (800, 2200), LANCZOS)
    bz, r = 26, 76
    pw, ph = s.width + bz * 2, s.height + bz * 2
    phone = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(phone)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), r, fill=(16, 16, 18, 255), outline=(90, 90, 96, 255), width=4)
    m = Image.new("L", s.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, s.width - 1, s.height - 1), r - bz + 14, fill=255)
    phone.paste(s, (bz, bz), m)
    d.rounded_rectangle(((pw - 170) // 2, bz + 14, (pw + 170) // 2, bz + 50), 18, fill=(16, 16, 18, 255))
    pad = 150
    W, H = pw + pad * 2, ph + pad * 2
    c1, c2 = hex_rgb(p.get("c1", "#3b82f6")), hex_rgb(p.get("c2", "#ec4899"))
    g = Image.linear_gradient("L").resize((W, H))
    bg = Image.composite(Image.new("RGB", (W, H), c2), Image.new("RGB", (W, H), c1), g).convert("RGBA")
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 30, pad + pw, pad + 30 + ph), r, fill=(0, 0, 0, 130))
    bg = Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(36)))
    bg.alpha_composite(phone, (pad, pad))
    return enc(bg, fmt, q)


def x_upscale(imgs, p, fmt, q):
    im, s = imgs[0], int(p.get("scale", 2))
    while s > 1 and im.width * s * im.height * s > 24_000_000:
        s -= 1
    if s <= 1:
        raise HTTPException(400, "Rasm allaqachon juda katta, kattalashtirib bo'lmaydi")
    o = im.resize((im.width * s, im.height * s), LANCZOS)
    o = rgb_op(o, lambda x: x.filter(ImageFilter.UnsharpMask(radius=1.6, percent=120, threshold=3)))
    return enc(o, fmt, q)


def x_colorkey(imgs, p, fmt, q):
    im = imgs[0].convert("RGB")
    if max(im.size) > 1200:
        im.thumbnail((1200, 1200), LANCZOS)
    col, tol = hex_rgb(p.get("color", "#ffffff")), int(p.get("tol", 25))
    if p.get("mode", "edge") == "all":
        r, g, b = ImageChops.difference(im, Image.new("RGB", im.size, col)).split()
        t = tol * 2.55
        alpha = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 0 if v <= t else min(255, int((v - t) * 8)))
    else:
        marker, tmp, hit = (255, 0, 254), im.copy(), False
        for xy in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
            px = tmp.getpixel(xy)
            if sum(abs(a - b) for a, b in zip(px, col)) <= tol * 4 + 30 and px != marker:
                ImageDraw.floodfill(tmp, xy, marker, thresh=tol * 4)
                hit = True
        if not hit:
            raise HTTPException(400, "Rasm chetlari tanlangan rangga o'xshamaydi. Fon rangini to'g'ri tanlang.")
        changed = ImageChops.difference(tmp, im).convert("L").point(lambda v: 255 if v else 0)
        alpha = ImageOps.invert(changed).filter(ImageFilter.GaussianBlur(1.2))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return enc(out, "PNG")


def x_ascii(imgs, p, fmt, q):
    w = max(20, min(int(p.get("width", 80)), 160))
    g = ImageOps.grayscale(flat(imgs[0]))
    h = max(1, int(g.height / g.width * w * .5))
    px = list(g.resize((w, h), LANCZOS).getdata())
    chars = " .:-=+*#%@" if p.get("invert") else "@%#*+=-:. "
    rows = ["".join(chars[px[y * w + x] * (len(chars) - 1) // 255] for x in range(w)) for y in range(h)]
    return "\n".join(rows).encode(), "txt", "text/plain"


def x_iconpack(imgs, p, fmt, q):
    sq = ImageOps.fit(imgs[0].convert("RGBA"), (512, 512), LANCZOS)
    items = [(f"icon-{s}.png", enc(sq.resize((s, s), LANCZOS), "PNG")[0]) for s in (16, 32, 48, 64, 128, 180, 192, 256, 512)]
    ico = io.BytesIO()
    sq.save(ico, "ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    items.append(("favicon.ico", ico.getvalue()))
    return _zip(items)


SOCIAL = {"instagram_post": (1080, 1080), "instagram_portret": (1080, 1350), "stories_reels": (1080, 1920),
          "youtube_thumbnail": (1280, 720), "telegram_avatar": (512, 512), "facebook_cover": (820, 312),
          "x_header": (1500, 500), "linkedin_banner": (1584, 396), "whatsapp_dp": (500, 500)}

def x_socialpack(imgs, p, fmt, q):
    im = flat(imgs[0])
    return _zip([(f"{n}_{w}x{h}.jpg", enc(ImageOps.fit(im, (w, h), LANCZOS), "JPG", 92)[0]) for n, (w, h) in SOCIAL.items()])


def x_info(datas):
    lines = []
    for n, d in enumerate(datas, 1):
        try:
            im = Image.open(io.BytesIO(d))
        except Exception:
            raise HTTPException(400, "Rasm o'qib bo'lmadi")
        lines.append(f"#{n}  {im.format}, {im.width}×{im.height}, {len(d) // 1024} KB")
        ex = im.getexif()
        shown = False
        for k, v in ex.items():
            name = ExifTags.TAGS.get(k, str(k))
            if name in ("Make", "Model", "Software", "DateTime", "LensModel"):
                lines.append(f"   {name}: {v}")
                shown = True
        try:
            if ex.get_ifd(0x8825):
                lines.append("   ⚠️ GPS joylashuv ma'lumoti BOR (Maxfiylik vositasi bilan o'chiring)")
                shown = True
        except Exception:
            pass
        if not shown:
            lines.append("   Yashirin ma'lumot (EXIF) topilmadi")
    return "\n".join(lines).encode(), "txt", "text/plain"


TOOLS = {"collage": x_collage, "gif": x_gif, "meme": x_meme, "poster": x_poster, "passport": x_passport,
         "palette": x_palette, "split": x_split, "fill": x_fill, "pixelate": x_pixelate, "mockup": x_mockup,
         "upscale": x_upscale, "colorkey": x_colorkey, "ascii": x_ascii, "iconpack": x_iconpack,
         "socialpack": x_socialpack}
