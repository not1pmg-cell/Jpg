"""
TELEGRAM MINI APP — IMAGE TOOLS
1 faylda to'liq ishlaydigan versiya.
Ishga tushirish: uvicorn mini_app:app --host 0.0.0.0 --port $PORT
"""

import os, io, json, hmac, hashlib, urllib.parse, uuid
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ACTIONS = {"convert","resize","compress","crop","enhance","clean_screenshot"}

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

@app.post("/api/process")
async def process(action:str=Form(...),file:UploadFile=File(...),format:str=Form("PNG"),
                  quality:int=Form(85),width:int=Form(0),height:int=Form(0),ratio:str=Form("1:1"),
                  init_data:str=Header("",alias="X-Telegram-Init-Data")):
    require_user(init_data)
    if action not in ACTIONS: raise HTTPException(400,"Unknown action")
    data=await file.read()
    if len(data)>MAX_MB*1024*1024: raise HTTPException(413,"File too large")
    try:
        img=Image.open(io.BytesIO(data)); img.load()
    except Exception: raise HTTPException(400,"Invalid image")

    ext="png"; media="image/png"
    if action=="convert":
        ext="jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out=to_bytes(img,format,quality)
    elif action=="resize":
        if width<=0: raise HTTPException(400,"width required")
        ext="jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out=to_bytes(resize_img(img,width,height or None),format,quality)
    elif action=="compress":
        ext="jpg"; out=to_bytes(img,"JPEG",max(10,min(quality,95)))
    elif action=="crop":
        ext="jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out=to_bytes(crop_center(img,ratio),format,quality)
    elif action=="enhance":
        ext="jpg" if format.upper() in ("JPG","JPEG") else format.lower()
        out=to_bytes(enhance_img(img),format,quality)
    else:
        ext="pdf"; media="application/pdf"
        b=io.BytesIO(); clean_shot(img).save(b,"PDF"); out=b.getvalue()

    if ext in ("jpg","jpeg"): media="image/jpeg"
    elif ext=="webp": media="image/webp"

    return Response(out,media_type=media,headers={"Content-Disposition":f'attachment; filename="{uuid.uuid4().hex[:10]}.{ext}"'})

HTML = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Image Tools</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:#0b0f19;--card:#141b2d;--accent:#2f81f7;--text:#e7ecf5;--muted:#8b98ad}
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui}
body{background:var(--bg);color:var(--text);padding:16px;min-height:100vh}
.header{text-align:center;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.tool{background:var(--card);border:1px solid #1f2937;border-radius:16px;padding:16px;text-align:center;cursor:pointer}
.tool.active{border-color:var(--accent);background:#16233b}
.tool span{font-size:26px;display:block;margin-bottom:6px}
.card{background:var(--card);border-radius:18px;padding:16px;margin-top:16px}
label{display:block;font-size:12px;color:var(--muted);margin:10px 0 6px}
input,select{width:100%;background:#0e1424;border:1px solid #243044;color:var(--text);padding:12px;border-radius:12px}
button{width:100%;margin-top:14px;background:var(--accent);border:0;color:#fff;padding:14px;border-radius:14px;font-weight:700}
.preview{margin-top:14px;text-align:center}
.preview img{max-width:100%;border-radius:12px}
.status{margin-top:10px;font-size:13px;color:var(--muted);text-align:center}
.hidden{display:none}
</style></head><body>
<div class="header"><h1>🖼 Image Tools</h1><p>Rasmni tanlang va amalni bajaring</p></div>
<div class="grid" id="tools"></div>
<div class="card">
<label>Rasm yuklash</label>
<input type="file" id="file" accept="image/*">
<div class="preview hidden" id="pw"><img id="pv"></div>
<div id="opts"></div>
<button id="run">Bajarish</button>
<div class="status" id="st"></div>
</div>
<script>
const tg=window.Telegram?.WebApp; tg?.ready(); tg?.expand();
let action="convert";
const tools=[["convert","🔄","Format"],["resize","📐","Resize"],["compress","🗜","Siqish"],["crop","✂️","Kesish"],["enhance","✨","Yaxshilash"],["clean_screenshot","🧹","Screenshot"]];
document.getElementById("tools").innerHTML=tools.map(([id,i,n])=>`<div class="tool ${id===action?"active":""}" data-a="${id}"><span>${i}</span><b>${n}</b></div>`).join("");
function opts(){const o=document.getElementById("opts");
if(action==="convert")o.innerHTML=`<label>Format</label><select id="format"><option>PNG</option><option>JPG</option><option>WEBP</option></select>`;
else if(action==="resize")o.innerHTML=`<label>Kenglik</label><input id="width" type="number" value="1080"><label>Balandlik</label><input id="height" type="number">`;
else if(action==="compress")o.innerHTML=`<label>Sifat</label><input id="quality" type="range" min="10" max="95" value="75">`;
else if(action==="crop")o.innerHTML=`<label>Nisbat</label><select id="ratio"><option>1:1</option><option>4:5</option><option>16:9</option><option>9:16</option></select>`;
else o.innerHTML="";}
opts();
document.querySelectorAll(".tool").forEach(e=>e.onclick=()=>{document.querySelectorAll(".tool").forEach(x=>x.classList.remove("active"));e.classList.add("active");action=e.dataset.a;opts();});
document.getElementById("file").onchange=e=>{const f=e.target.files[0];if(!f)return;document.getElementById("pw").classList.remove("hidden");document.getElementById("pv").src=URL.createObjectURL(f);};
document.getElementById("run").onclick=async()=>{
const f=document.getElementById("file").files[0];const st=document.getElementById("st");
if(!f)return st.textContent="Avval rasm tanlang.";
const fd=new FormData();fd.append("action",action);fd.append("file",f);
if(action==="convert")fd.append("format",document.getElementById("format").value);
if(action==="resize"){fd.append("width",document.getElementById("width").value);fd.append("height",document.getElementById("height").value||0);}
if(action==="compress")fd.append("quality",document.getElementById("quality").value);
if(action==="crop")fd.append("ratio",document.getElementById("ratio").value);
st.textContent="⏳ Ishlanmoqda...";
try{const r=await fetch("/api/process",{method:"POST",body:fd,headers:{"X-Telegram-Init-Data":tg?.initData||""}});
if(!r.ok)throw new Error(await r.text());
const b=await r.blob();const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download="result";a.click();
st.textContent="✅ Tayyor!";tg?.HapticFeedback?.notificationOccurred("success");}
catch(e){st.textContent="❌ "+e.message;tg?.HapticFeedback?.notificationOccurred("error");}};
</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(): return HTML

@app.get("/health")
async def health(): return {"ok":True}
