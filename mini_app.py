"""
TELEGRAM MINI APP — ULTIMATE MEDIA & AI BOT
Barcha modullar va vositalarni bog'lovchi asosiy fayl.
"""

import os, io, json, hmac, hashlib, urllib.parse
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx
import qrcode

import core
import ai_tools
import extra_tools
import pdf_tools

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def home():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "index.html topilmadi"

@app.get("/static/client.js")
async def get_client_js():
    if os.path.exists("client.js"):
        with open("client.js", "r", encoding="utf-8") as f:
            return Response(f.read(), media_type="application/javascript")
    return Response("", media_type="application/javascript")

@app.get("/api/rates")
async def get_rates():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("https://cbu.uz/uz/arkhiv-kursov-valyut/json/")
            if r.status_code == 200:
                data = r.json()
                return [{"c": x["Ccy"], "r": float(x["Rate"]), "nom": int(x["Nominal"]), "date": x["Date"]} for x in data]
        except Exception:
            pass
    return []

@app.post("/api/ai")
async def ai_process(
    action: str = Form(...),
    prompt: Optional[str] = Form(""),
    size: Optional[str] = Form("1024x1024"),
    model: Optional[str] = Form("flux"),
    seed: Optional[int] = Form(None),
    style: Optional[str] = Form(""),
    file: Optional[UploadFile] = File(None)
):
    if action == "ai_gen":
        content, ct = await ai_tools.generate(prompt, size, model, seed, style)
        return Response(content, media_type=ct)
    elif action == "ai_edit":
        if not file:
            raise HTTPException(400, "Rasm yuklanmadi")
        data = await file.read()
        tmp_id = ai_tools.store(data)
        webapp_url = os.getenv("WEBAPP_URL", "https://your-app.onrender.com")
        public_url = f"{webapp_url}/api/tmp/{tmp_id}"
        content, ct = await ai_tools.edit(prompt, public_url)
        return Response(content, media_type=ct)
    raise HTTPException(400, "Noma'lum AI amal")

@app.get("/api/tmp/{tmp_id}")
async def get_tmp(tmp_id: str):
    data = ai_tools.fetch_tmp(tmp_id)
    if not data:
        raise HTTPException(404, "Topilmadi yoki muddati o'tdi")
    return Response(data, media_type="image/jpeg")

@app.post("/api/process")
async def process(
    action: str = Form(...),
    params: str = Form("{}"),
    files: list[UploadFile] = File([])
):
    try:
        p = json.loads(params)
    except Exception:
        p = {}

    datas = [await f.read() for f in files]

    if action == "qr":
        txt = p.get("text", "")
        if not txt:
            raise HTTPException(400, "Matn kiritilmadi")
        img = qrcode.make(txt)
        out, ext, mime = core.enc(img, p.get("format", "PNG"), 95)
        return Response(out, media_type=mime, headers={"Content-Disposition": f'attachment; filename="qrcode.{ext}"'})

    if action.startswith("pdf_"):
        if pdf_tools.fitz is None:
            raise HTTPException(500, "PyMuPDF o'rnatilmagan")
        out, ext, mime = pdf_tools.run(action, datas, p)
        return Response(out, media_type=mime, headers={"Content-Disposition": f'attachment; filename="result.{ext}"'})

    if action in extra_tools.TOOLS:
        loaded_imgs = [core.load(d)[0] for d in datas]
        fmt = p.get("format", "JPG")
        q = int(p.get("quality", 90))
        out, ext, mime = extra_tools.TOOLS[action](loaded_imgs, p, fmt, q)
        return Response(out, media_type=mime, headers={"Content-Disposition": f'attachment; filename="result.{ext}"'})

    if not datas:
        raise HTTPException(400, "Fayl yuklanmadi")
    
    img, fmt_orig = core.load(datas[0])
    fmt = p.get("format", fmt_orig or "JPG")
    q = int(p.get("quality", 90))

    if action == "convert":
        out, ext, mime = core.enc(img, fmt, q)
    elif action == "resize":
        mode = p.get("mode", "px")
        if mode == "percent":
            ratio = float(p.get("percent", 50)) / 100.0
            w, h = int(img.width * ratio), int(img.height * ratio)
        else:
            w = int(p.get("width", 1080))
            h = p.get("height")
            h = int(h) if h else None
            if p.get("keep", True) and h is None:
                h = int(img.height * (w / img.width))
        out, ext, mime = core.enc(core.rgb_op(img, lambda x: x.resize((w, h or int(x.height * w / x.width)), core.LANCZOS)), fmt, q)
    elif action == "compress":
        out, ext, mime = core.enc(img, fmt, q)
    elif action == "crop":
        ratio = p.get("ratio", "1:1")
        m = {"1:1":(1,1), "4:5":(4,5), "3:4":(3,4), "4:3":(4,3), "16:9":(16,9), "9:16":(9,16), "3:2":(3,2), "2:3":(2,3)}
        rw, rh = m.get(ratio, (1,1))
        cropped = core.ImageOps.fit(img, (rw * 400, rh * 400), core.LANCZOS)
        out, ext, mime = core.enc(cropped, fmt, q)
    else:
        out, ext, mime = core.enc(img, fmt, q)

    return Response(out, media_type=mime, headers={"Content-Disposition": f'attachment; filename="result.{ext}"'})

@app.post("/api/send")
async def send_file(file: UploadFile = File(...)):
    return {"ok": True}

@app.get("/health")
async def health():
    return {"ok": True}
