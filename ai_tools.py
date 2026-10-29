"""AI rasm yaratish / tahrirlash — Pollinations.ai (bepul, pullik API kerak emas).

Kalitsiz (anonim) rejim: image.pollinations.ai — tezlik cheklangan.
Ixtiyoriy bepul kalit: https://enter.pollinations.ai da ro'yxatdan o'ting va
POLLINATIONS_KEY muhit o'zgaruvchisiga qo'ying — limit oshadi.
"""
import os, time, uuid, random, asyncio, urllib.parse
import httpx
from fastapi import HTTPException

KEY = os.getenv("POLLINATIONS_KEY", "")
STYLES = {
    "photo": "ultra realistic photo, natural light, 35mm",
    "anime": "anime style, vibrant colors, detailed",
    "3d": "3D render, soft studio lighting, high detail",
    "illustration": "digital illustration, clean lines, colorful",
    "pixel": "pixel art, 16-bit, retro game style",
    "oil": "oil painting, visible brush strokes, rich texture",
    "logo": "minimalist vector logo, flat design, white background",
    "cinematic": "cinematic film still, dramatic lighting, shallow depth of field",
}
_tmp = {}


def store(data: bytes) -> str:
    now = time.time()
    for k in [k for k, v in _tmp.items() if v[1] < now]:
        _tmp.pop(k, None)
    i = uuid.uuid4().hex
    _tmp[i] = (data, now + 600)  # 10 daqiqa
    return i


def fetch_tmp(i: str):
    v = _tmp.get(i)
    return v[0] if v and v[1] > time.time() else None


async def _get(prompt: str, params: dict):
    if KEY:
        url, params = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt, safe=""), {**params, "key": KEY}
    else:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt, safe="")
    async with httpx.AsyncClient(timeout=150, follow_redirects=True) as c:
        for attempt in range(2):
            try:
                r = await c.get(url, params=params)
            except httpx.HTTPError:
                r = None
            if r is not None:
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and ct.startswith("image/"):
                    return r.content, ct
                if r.status_code == 429:
                    raise HTTPException(429, "AI servis band. 20 soniyadan keyin qayta urinib ko'ring")
                if r.status_code in (401, 402, 403):
                    raise HTTPException(502, "AI servis kalit talab qilmoqda. POLLINATIONS_KEY ni o'rnating (enter.pollinations.ai, bepul)")
            if attempt == 0:
                await asyncio.sleep(3)
    raise HTTPException(502, "AI servis hozir javob bermayapti. Birozdan keyin urinib ko'ring")


async def generate(prompt, size, model, seed, style):
    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        raise HTTPException(400, "Nima chizish kerakligini yozing")
    try:
        w, h = (int(v) for v in size.split("x"))
    except Exception:
        w, h = 1024, 1024
    full = prompt[:500] + (", " + STYLES[style] if style in STYLES else "")
    params = {"width": w, "height": h, "model": model if model in ("flux", "turbo") else "flux",
              "seed": seed or random.randint(1, 10_000_000), "nologo": "true", "safe": "true"}
    return await _get(full, params)


async def edit(prompt, public_url):
    prompt = (prompt or "").strip()
    if len(prompt) < 3:
        raise HTTPException(400, "Nimani o'zgartirish kerakligini yozing")
    return await _get(prompt[:500], {"model": "kontext", "image": public_url, "nologo": "true", "safe": "true",
                                     "seed": random.randint(1, 10_000_000)})
