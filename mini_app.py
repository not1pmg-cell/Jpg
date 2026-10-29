"""
TELEGRAM MINI APP — ADVANCED MEDIA & TOOLS (PASSPORT & AI TOOLS)
1 faylda to'liq ishlaydigan zamonaviy versiya.
Ishga tushirish: uvicorn mini_app:app --host 0.0.0.0 --port $PORT
"""

import os, io, json, hmac, hashlib, urllib.parse, uuid, subprocess
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import qrcode

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ACTIONS = {
    "convert", "resize", "compress", "crop", "enhance", "clean_screenshot", 
    "qrcode", "video_trim", "video_to_mp3", "passport_photo", "watermark", "sticker", "circle"
}

def verify_init_data(init_data: str):
    if not init_data: return None
    try:
        p = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        h = p.pop("hash","")
        s = "\n".join(f"{k}={v}" for k,v in sorted(p.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, s.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc,h): return None
        return json.loads(p.get("user","{}"))
    except Exception: return None

def require_user(init_data):
    u = verify_init_data(init_data)
    if not u: raise HTTPException(401,"Invalid initData")
    return u

def to_bytes(img, fmt, q=90):
    b=io.BytesIO(); fmt=fmt.upper()
    if fmt in ("JPG","JPEG"): img.convert("RGB").save(b,"JPEG",quality=q,optimize=True)
    elif fmt=="WEBP": img.save(b,"WEBP",quality=q)
    elif fmt=="PNG": img.save(b,"PNG",optimize=True)
    else: img.save(b,fmt)
    return b.getvalue()

def resize_img(img,w,h=None):
    if h: return img.resize((w,h), Image.Resampling.LANCZOS)
    r=w/img.width
    return img.resize((w,int(img.height*r)), Image.Resampling.LANCZOS)

def crop_center(img,ratio):
    m={"1:1":(1,1),"4:5":(4,5),"16:9":(16,9),"9:16":(9,16)}
    rw,rh=m.get(ratio,(1,1))
    return ImageOps.fit(img,(rw*400,rh*400),Image.Resampling.LANCZOS)

def enhance_img(img):
    img=ImageEnhance.Brightness(img).enhance(1.06)
    img=ImageEnhance.Contrast(img).enhance(1.12)
    img=ImageEnhance.Color(img).enhance(1.10)
    return ImageEnhance.Sharpness(img).enhance(1.35)

def clean_shot(img):
    img=img.convert("RGB").filter(ImageFilter.MedianFilter(3))
    return enhance_img(img)

def passport_prep(img):
    # Pasport uchun 3:4 nisbat (masalan 600x800) va oq fon simulyatsiyasi / tiniqlashtirish
    img = img.convert("RGB")
    img = ImageOps.fit(img, (600, 800), Image.Resampling.LANCZOS)
    return enhance_img(img)

def make_circle(img):
    img = img.convert("RGBA").resize((512, 512), Image.Resampling.LANCZOS)
    mask = Image.new("L", (512, 512), 0)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, 512, 512), fill=255)
    img.putalpha(mask)
    return img

@app.post("/api/process")
async def process(
    action: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text_data: Optional[str] = Form(""),
    format: str = Form("PNG"),
    quality: int = Form(85),
    width: int = Form(0),
    height: int = Form(0),
    ratio: str = Form("1:1"),
    init_data: str = Header("", alias="X-Telegram-Init-Data")
):
    require_user(init_data)
    if action not in ACTIONS: raise HTTPException(400,"Unknown action")

    if action == "qrcode":
        if not text_data: raise HTTPException(400, "Matn yoki havola kiritilmadi")
        img = qrcode.make(text_data)
        out = to_bytes(img, "PNG", 100)
        return Response(out, media_type="image/png", headers={"Content-Disposition": f'attachment; filename="qrcode.png"'})

    if not file: raise HTTPException(400, "Fayl yuklanmadi")
    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024: raise HTTPException(413, "Fayl hajmi juda katta")

    if action in ("video_trim", "video_to_mp3"):
        temp_in = f"/tmp/{uuid.uuid4().hex}.mp4"
        with open(temp_in, "wb") as f: f.write(data)
        
        if action == "video_to_mp3":
            temp_out = temp_in.replace(".mp4", ".mp3")
            subprocess.run(["ffmpeg", "-i", temp_in, "-q:a", "0", "-map", "a", temp_out], check=True)
            with open(temp_out, "rb") as f: out = f.read()
            os.remove(temp_in); os.remove(temp_out)
            return Response(out, media_type="audio/mpeg", headers={"Content-Disposition": f'attachment; filename="audio.mp3"'})
        
        temp_out = temp_in.replace(".mp4", "_out.mp4")
        subprocess.run(["ffmpeg", "-i", temp_in, "-vcodec", "libx264", "-crf", "28", temp_out], check=True)
        with open(temp_out, "rb") as f: out = f.read()
        os.remove(temp_in); os.remove(temp_out)
        return Response(out, media_type="video/mp4", headers={"Content-Disposition": f'attachment; filename="compressed_video.mp4"'})

    try:
        img = Image.open(io.BytesIO(data)); img.load()
    except Exception: raise HTTPException(400, "Yaroqsiz rasm formati")

    ext = "jpg"; media = "image/jpeg"
    if action == "convert":
        ext = "jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out = to_bytes(img, format, quality)
    elif action == "resize":
        if width <= 0: raise HTTPException(400, "Kenglik kiritilmadi")
        ext = "jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out = to_bytes(resize_img(img, width, height or None), format, quality)
    elif action == "compress":
        ext = "jpg"; out = to_bytes(img, "JPEG", max(10, min(quality, 95)))
    elif action == "crop":
        ext = "jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out = to_bytes(crop_center(img, ratio), format, quality)
    elif action == "enhance":
        ext = "jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out = to_bytes(enhance_img(img), format, quality)
    elif action == "passport_photo":
        ext = "jpg"; out = to_bytes(passport_prep(img), "JPEG", 95)
    elif action == "circle":
        ext = "png"; media = "image/png"; out = to_bytes(make_circle(img), "PNG", 100)
    elif action == "sticker":
        ext = "png"; media = "image/png"; out = to_bytes(resize_img(img, 512, 512), "PNG", 100)
    else:
        ext = "pdf"; media = "application/pdf"
        b = io.BytesIO(); clean_shot(img).save(b, "PDF"); out = b.getvalue()

    return Response(out, media_type=media, headers={"Content-Disposition": f'attachment; filename="{uuid.uuid4().hex[:10]}.{ext}"'})

HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Pro Media Tools</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root {
  --bg: #0f172a; --card: #1e293b; --accent: #3b82f6; --accent-hover: #2563eb;
  --text: #f8fafc; --muted: #94a3b8; --border: #334155; --input-bg: #0b0f19;
}
.light-theme {
  --bg: #f1f5f9; --card: #ffffff; --accent: #2563eb; --accent-hover: #1d4ed8;
  --text: #0f172a; --muted: #64748b; --border: #cbd5e1; --input-bg: #f8fafc;
}
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif;transition:background 0.3s, color 0.3s;}
body{background:var(--bg);color:var(--text);padding:16px;min-height:100vh;padding-bottom:40px;}
.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.theme-btn{background:var(--card);border:1px solid var(--border);color:var(--text);padding:8px 14px;border-radius:12px;cursor:pointer;font-size:14px;font-weight:600;}
.header{text-align:center;margin-bottom:18px;}
.header h1{font-size:22px;font-weight:800;margin-bottom:4px;}
.header p{font-size:13px;color:var(--muted);}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}
@media(max-width:480px){.grid{grid-template-columns:repeat(2,1fr);}}
.tool{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:14px 8px;text-align:center;cursor:pointer;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);}
.tool.active{border-color:var(--accent);background:rgba(59,130,246,0.1);box-shadow:0 0 15px rgba(59,130,246,0.2);}
.tool span{font-size:24px;display:block;margin-bottom:6px;}
.tool b{font-size:12px;display:block;color:var(--text);}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:16px;margin-top:16px;box-shadow:0 10px 15px -3px rgba(0,0,0,0.1);}
label{display:block;font-size:12px;font-weight:600;color:var(--muted);margin:12px 0 6px;}
input,select{width:100%;background:var(--input-bg);border:1px solid var(--border);color:var(--text);padding:12px;border-radius:12px;outline:none;font-size:14px;}
input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 2px rgba(59,130,246,0.2);}
button.action-btn{width:100%;margin-top:16px;background:var(--accent);border:0;color:#fff;padding:14px;border-radius:14px;font-weight:700;cursor:pointer;font-size:15px;}
button.action-btn:hover{background:var(--accent-hover);}
.preview{margin-top:14px;text-align:center;}
.preview img{max-width:100%;max-height:220px;border-radius:12px;border:1px solid var(--border);}
.status{margin-top:12px;font-size:13px;color:var(--muted);text-align:center;font-weight:500;}
.hidden{display:none;}
</style>
</head>
<body>

<div class="top-bar">
  <div style="font-weight:800; font-size:16px;">⚡️ ProKit</div>
  <button class="theme-btn" id="themeToggle">☀️ Kunduzgi</button>
</div>

<div class="header">
  <h1>🛠 Mukammal Media Markaz</h1>
  <p>Pasport 4x3, Rasm, Video va QR-kod vositalari</p>
</div>

<div class="grid" id="tools"></div>

<div class="card">
  <div id="inputBox">
    <label id="inputLabel">Faylni yuklash</label>
    <input type="file" id="file" accept="image/*">
  </div>
  <div class="preview hidden" id="pw"><img id="pv"></div>
  <div id="opts"></div>
  <button class="action-btn" id="run">🚀 Amalni Bajarish</button>
  <div class="status" id="st"></div>
</div>

<script>
const tg = window.Telegram?.WebApp; tg?.ready(); tg?.expand();

const themeToggle = document.getElementById("themeToggle");
let isDark = true;
themeToggle.onclick = () => {
  isDark = !isDark;
  document.body.classList.toggle("light-theme", !isDark);
  themeToggle.textContent = isDark ? "☀️ Kunduzgi" : "🌙 Tungi";
};

let action = "passport_photo";
const tools = [
  ["passport_photo", "🪪", "Pasport (4x3)"],
  ["enhance", "✨", "Tiniqlashtirish"],
  ["resize", "📐", "O'lcham"],
  ["compress", "🗜", "Siqish"],
  ["crop", "✂️", "Kesish"],
  ["circle", "🟢", "Doira (Avatar)"],
  ["sticker", "🏷", "Stiker (512x512)"],
  ["qrcode", "qr", "QR-kod yaratish"],
  ["video_trim", "🎬", "Video Opt"],
  ["video_to_mp3", "🎵", "MP3 ga o'tish"]
];

document.getElementById("tools").innerHTML = tools.map(([id,i,n]) => 
  `<div class="tool ${id===action?"active":""}" data-a="${id}"><span>${i}</span><b>${n}</b></div>`
).join("");

function opts() {
  const o = document.getElementById("opts");
  const box = document.getElementById("inputBox");
  
  if (action === "qrcode") {
    box.innerHTML = `<label>QR-kod uchun matn yoki havola kiriting</label><input type="text" id="text_data" placeholder="https://t.me/...">`;
    o.innerHTML = "";
    document.getElementById("pw").classList.add("hidden");
  } else {
    box.innerHTML = `<label id="inputLabel">${action.includes('video') ? 'Video yuklash' : 'Rasm yuklash'}</label><input type="file" id="file" accept="${action.includes('video') ? 'video/*' : 'image/*'}">`;
    document.getElementById("file").onchange = e => {
      const f = e.target.files[0];
      if(!f) return;
      if(!action.includes('video')) {
        document.getElementById("pw").classList.remove("hidden");
        document.getElementById("pv").src = URL.createObjectURL(f);
      }
    };

    if(action === "resize") o.innerHTML = `<label>Kenglik (px)</label><input id="width" type="number" value="1080"><label>Balandlik (px)</label><input id="height" type="number" placeholder="Avtomatik">`;
    else if(action === "compress") o.innerHTML = `<label>Sifat darajasi (%): <span id="qval">75</span></label><input id="quality" type="range" min="10" max="95" value="75" oninput="document.getElementById('qval').textContent=this.value">`;
    else if(action === "crop") o.innerHTML = `<label>Tomonlar nisbati</label><select id="ratio"><option>1:1</option><option>4:5</option><option>16:9</option><option>9:16</option></select>`;
    else o.innerHTML = "";
  }
}
opts();

document.querySelectorAll(".tool").forEach(e => e.onclick = () => {
  document.querySelectorAll(".tool").forEach(x => x.classList.remove("active"));
  e.classList.add("active");
  action = e.dataset.a;
  opts();
});

document.getElementById("run").onclick = async () => {
  const st = document.getElementById("st");
  const fd = new FormData();
  fd.append("action", action);

  if (action === "qrcode") {
    const txt = document.getElementById("text_data")?.value;
    if(!txt) return st.textContent = "⚠️ Matn kiriting.";
    fd.append("text_data", txt);
  } else {
    const f = document.getElementById("file")?.files[0];
    if(!f) return st.textContent = "⚠️ Avval fayl tanlang.";
    fd.append("file", f);
    if(action === "resize"){
      fd.append("width", document.getElementById("width").value);
      fd.append("height", document.getElementById("height").value || 0);
    }
    if(action === "compress") fd.append("quality", document.getElementById("quality").value);
    if(action === "crop") fd.append("ratio", document.getElementById("ratio").value);
  }

  st.textContent = "⏳ Ishlanmoqda, kuting...";
  try {
    const r = await fetch("/api/process", {
      method: "POST",
      body: fd,
      headers: { "X-Telegram-Init-Data": tg?.initData || "" }
    });
    if(!r.ok) throw new Error(await r.text());
    const b = await r.blob();
    const u = URL.createObjectURL(b);
    const a = document.createElement("a");
    a.href = u;
    a.download = action === "qrcode" ? "qrcode.png" : (action === "video_to_mp3" ? "audio.mp3" : "result");
    a.click();
    st.textContent = "✅ Tayyor, yuklab olindi!";
    tg?.HapticFeedback?.notificationOccurred("success");
  } catch(e) {
    st.textContent = "❌ Xatolik: " + e.message;
    tg?.HapticFeedback?.notificationOccurred("error");
  }
};
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home(): return HTML

@app.get("/health")
async def health(): return {"ok": True}
