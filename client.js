/* Brauzerda ishlaydigan vositalar: serverga yuk tushmaydi, hammasi bepul. */
(function () {
  const T = {};
  const $ = (r, s) => r.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const copy = async t => { try { await navigator.clipboard.writeText(t); } catch (e) { const a = document.createElement("textarea"); a.value = t; document.body.appendChild(a); a.select(); document.execCommand("copy"); a.remove(); } };
  const mk = (id, i, n, h, body, init) => { T[id] = { i, n, h, cl: true, render(root) { root.innerHTML = `<div class="hint">${h}</div>${body}<pre class="txt hidden" id="o"></pre><div class="acts hidden" id="oa"><button class="main" id="cp">📋 Nusxa olish</button></div>`; init(root, txt => show(root, txt)); } }; };
  function show(root, txt, noCopy) {
    const o = $(root, "#o"); o.textContent = txt; o.classList.remove("hidden");
    const a = $(root, "#oa"); a.classList.toggle("hidden", !!noCopy);
    $(root, "#cp").onclick = async () => { await copy(txt); $(root, "#cp").textContent = "✅ Nusxa olindi"; setTimeout(() => $(root, "#cp").textContent = "📋 Nusxa olish", 1500); };
  }
  const btn = (id, l, main) => `<button class="go" id="${id}" style="margin-top:10px;${main ? "" : "background:var(--cyan);color:#fff"}">${l}</button>`;
  const num = v => parseFloat(String(v).replace(/\s/g, "").replace(",", "."));
  const fmt = (n, d = 2) => isFinite(n) ? n.toLocaleString("uz-UZ", { maximumFractionDigits: d }).replace(/,/g, " ") : "—";

  /* ───────── MATN ───────── */
  const LC = [["o'", "ў"], ["g'", "ғ"], ["sh", "ш"], ["ch", "ч"], ["yo", "ё"], ["yu", "ю"], ["ya", "я"], ["ye", "е"], ["ts", "ц"], ["a", "а"], ["b", "б"], ["d", "д"], ["e", "е"], ["f", "ф"], ["g", "г"], ["h", "ҳ"], ["i", "и"], ["j", "ж"], ["k", "к"], ["l", "л"], ["m", "м"], ["n", "н"], ["o", "о"], ["p", "п"], ["q", "қ"], ["r", "р"], ["s", "с"], ["t", "т"], ["u", "у"], ["v", "в"], ["x", "х"], ["y", "й"], ["z", "з"], ["'", "ъ"]];
  const isL = c => /[a-zA-Z']/.test(c || "");
  function lat2cyr(t) {
    t = t.replace(/[ʻʼ‘’`´]/g, "'");
    let r = "", i = 0;
    while (i < t.length) {
      let done = false;
      for (const [k, v] of LC) {
        if (t.substr(i, k.length).toLowerCase() !== k) continue;
        if (k === "yo" && t[i + 2] === "'") continue;
        const s = t.substr(i, k.length), up = s[0] !== s[0].toLowerCase(), two = s.length > 1 && s[1] !== s[1].toLowerCase();
        let c = v;
        if (k === "e" && !isL(t[i - 1])) c = "э";
        if (k === "ye" && isL(t[i - 1])) c = "йе";
        r += up ? (two ? c.toUpperCase() : c[0].toUpperCase() + c.slice(1)) : c;
        i += k.length; done = true; break;
      }
      if (!done) { r += t[i]; i++; }
    }
    return r;
  }
  const CL = { а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "yo", ж: "j", з: "z", и: "i", й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "x", ц: "ts", ч: "ch", ш: "sh", ъ: "'", ь: "", ы: "i", э: "e", ю: "yu", я: "ya", ў: "o'", қ: "q", ғ: "g'", ҳ: "h" };
  const CY = /[А-Яа-яЁёЎўҚқҒғҲҳ]/;
  function cyr2lat(t) {
    return t.replace(/[А-Яа-яЁёЎўҚқҒғҲҳ]/g, (ch, off, str) => {
      const l = ch.toLowerCase();
      let v = CL[l];
      if (v === undefined) return ch;
      if (l === "е") { const p = (str[off - 1] || " ").toLowerCase(); if (!CY.test(p) || "аеёиоуэюяъ".includes(p)) v = "ye"; }
      if (ch === l || !v) return v;
      return CY.test(str[off + 1] || "") && str[off + 1] === str[off + 1].toUpperCase() ? v.toUpperCase() : v[0].toUpperCase() + v.slice(1);
    });
  }
  mk("translit", "🔁", "Lotin ⇄ Kirill", "O'zbek matnini lotindan kirillga yoki teskarisiga o'giring.",
    `<label>Matn</label><textarea id="i" rows="6" placeholder="Matnni shu yerga yozing yoki qo'ying"></textarea>
     <div class="row">${btn("a", "Lotin → Kirill")}${btn("b", "Kirill → Lotin")}</div>`,
    (r, out) => { $(r, "#a").onclick = () => out(lat2cyr($(r, "#i").value)); $(r, "#b").onclick = () => out(cyr2lat($(r, "#i").value)); });

  mk("textutil", "🔠", "Matn asboblari", "Sanash, harf o'zgartirish va matnni tozalash.",
    `<label>Matn</label><textarea id="i" rows="7"></textarea><div class="sm" id="st"></div>
     <div id="bs" style="margin-top:6px">${[["up", "KATTA HARF"], ["low", "kichik harf"], ["title", "Har So'z Bosh Harf"], ["sent", "Gap boshi"], ["sp", "Ortiqcha bo'shliq"], ["br", "Qatorlarni birlashtirish"], ["sort", "Saralash (A–Z)"], ["uniq", "Takrorlarni o'chirish"], ["rev", "Teskari"]].map(([k, l]) => `<span class="pill" data-k="${k}">${l}</span>`).join("")}</div>`,
    (r, out) => {
      const i = $(r, "#i");
      const st = () => { const t = i.value, w = (t.trim().match(/\S+/g) || []).length; $(r, "#st").textContent = `${t.length} belgi · ${w} so'z · ${t ? t.split("\n").length : 0} qator · ~${Math.max(1, Math.ceil(w / 200))} daq o'qish`; };
      i.oninput = st; st();
      const F = {
        up: t => t.toUpperCase(), low: t => t.toLowerCase(),
        title: t => t.toLowerCase().replace(/(^|[\s(])(\S)/g, (m, a, b) => a + b.toUpperCase()),
        sent: t => t.toLowerCase().replace(/(^\s*|[.!?]\s+)(\S)/g, (m, a, b) => a + b.toUpperCase()),
        sp: t => t.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim(), br: t => t.replace(/\s*\n\s*/g, " ").trim(),
        sort: t => t.split("\n").sort((a, b) => a.localeCompare(b)).join("\n"), uniq: t => [...new Set(t.split("\n"))].join("\n"),
        rev: t => [...t].reverse().join("")
      };
      r.querySelectorAll(".pill").forEach(p => p.onclick = () => { i.value = F[p.dataset.k](i.value); st(); out(i.value); });
    });

  const U = ["", "bir", "ikki", "uch", "to'rt", "besh", "olti", "yetti", "sakkiz", "to'qqiz"], TN = ["", "o'n", "yigirma", "o'ttiz", "qirq", "ellik", "oltmish", "yetmish", "sakson", "to'qson"], SC = ["", "ming", "million", "milliard", "trillion"];
  const w3 = n => [n >= 100 ? U[Math.floor(n / 100)] + " yuz" : "", TN[Math.floor(n % 100 / 10)], U[n % 10]].filter(Boolean).join(" ");
  function words(n) { if (n === 0) return "nol"; const p = []; let i = 0; while (n > 0) { const g = n % 1000; if (g) p.unshift((w3(g) + " " + SC[i]).trim()); n = Math.floor(n / 1000); i++; } return p.join(" "); }
  mk("numwords", "🔢", "Raqam → so'z", "Summani so'z bilan yozing (shartnoma, kvitansiya uchun).",
    `<label>Raqam</label><input type="text" id="i" inputmode="numeric" placeholder="1250000">${btn("a", "So'zga aylantirish")}`,
    (r, out) => $(r, "#a").onclick = () => {
      const n = Math.floor(num($(r, "#i").value));
      if (!isFinite(n) || n < 0 || n > 999999999999999) return out("0 dan 999 999 999 999 999 gacha butun son kiriting");
      const w = words(n); out(`${fmt(n, 0)} so'm\n${w.charAt(0).toUpperCase() + w.slice(1)} so'm`);
    });

  const b64e = t => btoa(String.fromCharCode(...new TextEncoder().encode(t)));
  const b64d = t => new TextDecoder().decode(Uint8Array.from(atob(t.trim()), c => c.charCodeAt(0)));
  mk("base64", "🧬", "Base64 / URL", "Matnni Base64 yoki URL formatiga kodlash va qaytarish.",
    `<label>Matn</label><textarea id="i" rows="5"></textarea><div class="row">${btn("a", "Base64 kodlash")}${btn("b", "Base64 ochish")}${btn("c", "URL kodlash")}${btn("d", "URL ochish")}</div>`,
    (r, out) => {
      const go = f => () => { try { out(f($(r, "#i").value)); } catch (e) { out("Xato: matn noto'g'ri formatda"); } };
      $(r, "#a").onclick = go(b64e); $(r, "#b").onclick = go(b64d); $(r, "#c").onclick = go(encodeURIComponent); $(r, "#d").onclick = go(decodeURIComponent);
    });

  mk("json", "🧾", "JSON tekshirish", "JSON ni chiroyli formatlash, siqish va xatolarni topish.",
    `<label>JSON</label><textarea id="i" rows="8" placeholder='{"ism":"Ali"}'></textarea><div class="row">${btn("a", "Chiroyli")}${btn("b", "Siqish")}</div>`,
    (r, out) => {
      const go = sp => () => { try { out(JSON.stringify(JSON.parse($(r, "#i").value), null, sp)); } catch (e) { out("❌ JSON xato: " + e.message); } };
      $(r, "#a").onclick = go(2); $(r, "#b").onclick = go(0);
    });

  const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
  mk("hash", "#️⃣", "Xesh va UUID", "Matndan SHA xesh olish yoki tasodifiy UUID yaratish.",
    `<label>Matn</label><textarea id="i" rows="4"></textarea><div class="row">${btn("a", "SHA-256")}${btn("b", "SHA-1")}${btn("c", "SHA-512")}${btn("d", "Yangi UUID")}</div>`,
    (r, out) => {
      const h = alg => async () => out(hex(await crypto.subtle.digest(alg, new TextEncoder().encode($(r, "#i").value))));
      $(r, "#a").onclick = h("SHA-256"); $(r, "#b").onclick = h("SHA-1"); $(r, "#c").onclick = h("SHA-512");
      $(r, "#d").onclick = () => out(crypto.randomUUID());
    });

  mk("password", "🔐", "Parol yaratish", "Kuchli tasodifiy parol. Hech qayerga yuborilmaydi, telefoningizda yaratiladi.",
    `<label>Uzunlik <b id="lv">16</b></label><input type="range" id="len" min="8" max="64" value="16">
     <label class="chk"><input type="checkbox" id="u" checked>Katta harflar</label><label class="chk"><input type="checkbox" id="d" checked>Raqamlar</label><label class="chk"><input type="checkbox" id="s" checked>Belgilar (!@#)</label>
     ${btn("a", "Yaratish")}`,
    (r, out) => {
      $(r, "#len").oninput = e => $(r, "#lv").textContent = e.target.value;
      $(r, "#a").onclick = () => {
        let cs = "abcdefghijkmnopqrstuvwxyz"; if ($(r, "#u").checked) cs += "ABCDEFGHJKLMNPQRSTUVWXYZ"; if ($(r, "#d").checked) cs += "23456789"; if ($(r, "#s").checked) cs += "!@#$%^&*-_=+?";
        const lim = Math.floor(2 ** 32 / cs.length) * cs.length; let p = "";
        while (p.length < +$(r, "#len").value) { const x = crypto.getRandomValues(new Uint32Array(1))[0]; if (x < lim) p += cs[x % cs.length]; }
        out(p);
      };
    });

  mk("ocr", "👁", "OCR: rasmdan matn", "Rasmdagi yozuvni matnga aylantiradi. Brauzeringizda ishlaydi, birinchi marta til fayli yuklanadi (10–20 MB).",
    `<label>Rasm</label><input type="file" id="f" accept="image/png,image/jpeg,image/webp">
     <label>Til</label><select id="l"><option value="uzb+eng">O'zbek (lotin) + Ingliz</option><option value="rus+eng">Rus + Ingliz</option><option value="uzb_cyrl+rus">O'zbek (kirill) + Rus</option><option value="eng">Ingliz</option></select>
     ${btn("a", "Matnni o'qish")}<div class="sm" id="pg"></div>`,
    (r, out) => $(r, "#a").onclick = async () => {
      const f = $(r, "#f").files[0]; if (!f) return out("Avval rasm tanlang");
      try {
        $(r, "#pg").textContent = "⏳ Dastur yuklanmoqda...";
        if (!window.Tesseract) await new Promise((ok, no) => { const s = document.createElement("script"); s.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js"; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
        const res = await Tesseract.recognize(f, $(r, "#l").value, { logger: m => { if (m.status) $(r, "#pg").textContent = `⏳ ${m.status}${m.progress ? " " + Math.round(m.progress * 100) + "%" : ""}`; } });
        $(r, "#pg").textContent = "";
        out(res.data.text.trim() || "Matn topilmadi. Aniqroq va to'g'ri turgan rasm tanlang.");
      } catch (e) { $(r, "#pg").textContent = ""; out("❌ OCR ishlamadi. Internetni tekshiring va qayta urinib ko'ring."); }
    });

  /* ───────── HISOB-KITOB ───────── */
  const RATE = { data: null };
  mk("currency", "💱", "Valyuta kursi", "O'zbekiston Markaziy banki rasmiy kurslari asosida.",
    `<div class="row"><div><label>Miqdor</label><input type="text" id="a" inputmode="decimal" value="100"></div><div><label>Qaysi valyutadan</label><select id="f"></select></div></div>
     <label>Qaysi valyutaga</label><select id="t"></select><div class="sm" id="dt">Kurslar yuklanmoqda...</div>`,
    async (r, out) => {
      try {
        if (!RATE.data) { const x = await fetch("/api/rates"); if (!x.ok) throw 0; RATE.data = await x.json(); }
        const L = [{ c: "UZS", r: 1, nom: 1 }, ...RATE.data.filter(x => ["USD", "EUR", "RUB", "KZT", "CNY", "GBP", "TRY", "JPY", "KRW", "AED", "KGS", "TJS"].includes(x.c))];
        const opt = d => L.map(x => `<option ${x.c === d ? "selected" : ""}>${x.c}</option>`).join("");
        $(r, "#f").innerHTML = opt("USD"); $(r, "#t").innerHTML = opt("UZS");
        const per = c => { const x = L.find(y => y.c === c); return x.r / x.nom; };
        const calc = () => { const v = num($(r, "#a").value), f = $(r, "#f").value, t = $(r, "#t").value; out(`${fmt(v)} ${f} = ${fmt(v * per(f) / per(t), t === "UZS" ? 0 : 4)} ${t}`); };
        ["#a", "#f", "#t"].forEach(s => $(r, s).oninput = calc); calc();
        $(r, "#dt").textContent = "Kurs sanasi: " + (RATE.data[0]?.date || "");
      } catch (e) { $(r, "#dt").textContent = "❌ Kurslar olinmadi. Birozdan keyin qayta urinib ko'ring."; }
    });

  mk("percent", "％", "Foiz hisoblash", "Uchta oddiy foiz masalasi.",
    `<label>1) X ning Y foizi nechta?</label><div class="row"><input type="text" id="a1" inputmode="decimal" placeholder="Y %"><input type="text" id="b1" inputmode="decimal" placeholder="X"></div>
     <label>2) X son Y ning necha foizi?</label><div class="row"><input type="text" id="a2" inputmode="decimal" placeholder="X"><input type="text" id="b2" inputmode="decimal" placeholder="Y"></div>
     <label>3) X dan Y gacha necha foiz o'zgardi?</label><div class="row"><input type="text" id="a3" inputmode="decimal" placeholder="X (eski)"><input type="text" id="b3" inputmode="decimal" placeholder="Y (yangi)"></div>`,
    (r, out) => {
      const g = s => num($(r, s).value), calc = () => {
        const L = [];
        if (isFinite(g("#a1") * g("#b1"))) L.push(`${fmt(g("#b1"))} ning ${fmt(g("#a1"))}% = ${fmt(g("#b1") * g("#a1") / 100)}`);
        if (isFinite(g("#a2") / g("#b2"))) L.push(`${fmt(g("#a2"))} soni ${fmt(g("#b2"))} ning ${fmt(g("#a2") / g("#b2") * 100)}% i`);
        if (isFinite((g("#b3") - g("#a3")) / g("#a3"))) { const d = (g("#b3") - g("#a3")) / g("#a3") * 100; L.push(`O'zgarish: ${d > 0 ? "+" : ""}${fmt(d)}% (${d >= 0 ? "oshdi" : "kamaydi"})`); }
        if (L.length) show(r, L.join("\n"), true);
      };
      r.querySelectorAll("input").forEach(i => i.oninput = calc);
    });

  mk("loan", "🏦", "Kredit kalkulyator", "Oylik to'lov va umumiy ortiqcha to'lovni hisoblang.",
    `<label>Kredit summasi</label><input type="text" id="p" inputmode="decimal" value="50000000">
     <div class="row"><div><label>Yillik foiz %</label><input type="text" id="r" inputmode="decimal" value="24"></div><div><label>Muddat (oy)</label><input type="text" id="m" inputmode="numeric" value="24"></div></div>${btn("a", "Hisoblash")}`,
    (r, out) => $(r, "#a").onclick = () => {
      const P = num($(r, "#p").value), i = num($(r, "#r").value) / 1200, n = Math.round(num($(r, "#m").value));
      if (!(P > 0 && n > 0 && i >= 0)) return out("Summa, foiz va muddatni to'g'ri kiriting");
      const an = i ? P * i * (1 + i) ** n / ((1 + i) ** n - 1) : P / n, tot = an * n, dTot = P * i * (n + 1) / 2;
      out(`ANNUITET (har oy bir xil)\nOylik to'lov: ${fmt(an, 0)}\nJami to'lov: ${fmt(tot, 0)}\nOrtiqcha: ${fmt(tot - P, 0)}\n\nDIFFERENSIAL (kamayib boradi)\nBirinchi oy: ${fmt(P / n + P * i, 0)}\nOxirgi oy: ${fmt(P / n + P / n * i, 0)}\nOrtiqcha: ${fmt(dTot, 0)}`);
    });

  mk("bmi", "⚖️", "Tana massasi indeksi", "Bo'y va vazn bo'yicha BMI. Bu umumiy ko'rsatkich, tibbiy tashxis emas.",
    `<div class="row"><div><label>Bo'y (sm)</label><input type="text" id="h" inputmode="decimal" value="170"></div><div><label>Vazn (kg)</label><input type="text" id="w" inputmode="decimal" value="70"></div></div>${btn("a", "Hisoblash")}`,
    (r, out) => $(r, "#a").onclick = () => {
      const h = num($(r, "#h").value) / 100, w = num($(r, "#w").value), b = w / (h * h);
      if (!(h > .5 && h < 2.6 && w > 10)) return out("Bo'y va vaznni to'g'ri kiriting");
      out(`BMI: ${fmt(b, 1)}\n${b < 18.5 ? "Vazn yetishmaydi" : b < 25 ? "Me'yorda" : b < 30 ? "Ortiqcha vazn" : "Semizlik"}\nMe'yor oralig'i: ${fmt(18.5 * h * h, 1)} – ${fmt(24.9 * h * h, 1)} kg`);
    });

  mk("age", "🎂", "Yosh hisoblash", "Tug'ilgan sanadan necha yosh, necha kun yashagan va keyingi tug'ilgan kun.",
    `<label>Tug'ilgan sana</label><input type="date" id="d">${btn("a", "Hisoblash")}`,
    (r, out) => $(r, "#a").onclick = () => {
      const v = $(r, "#d").value; if (!v) return out("Sanani tanlang");
      const b = new Date(v), n = new Date(); if (b > n) return out("Sana kelajakda");
      let y = n.getFullYear() - b.getFullYear(), m = n.getMonth() - b.getMonth(), d = n.getDate() - b.getDate();
      if (d < 0) { m--; d += new Date(n.getFullYear(), n.getMonth(), 0).getDate(); } if (m < 0) { y--; m += 12; }
      let nx = new Date(n.getFullYear(), b.getMonth(), b.getDate()); if (nx < new Date(n.getFullYear(), n.getMonth(), n.getDate())) nx.setFullYear(n.getFullYear() + 1);
      const days = Math.floor((n - b) / 864e5), wd = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"][b.getDay()];
      out(`Yosh: ${y} yil, ${m} oy, ${d} kun\nJami: ${fmt(days, 0)} kun (${fmt(days / 7, 0)} hafta)\nKeyingi tug'ilgan kun: ${Math.ceil((nx - n) / 864e5)} kundan keyin\nTug'ilgan kuni: ${wd}`);
    });

  const UN = {
    "Uzunlik": { m: 1, km: 1000, sm: .01, mm: .001, mil: 1609.344, fut: .3048, dyuym: .0254, yard: .9144 },
    "Vazn": { kg: 1, g: .001, tonna: 1000, funt: .45359237, unsiya: .028349523 },
    "Maydon": { "m²": 1, "km²": 1e6, "gektar": 1e4, "sotix": 100, "sm²": 1e-4, "akr": 4046.8564 },
    "Hajm": { litr: 1, ml: .001, "m³": 1000, galon: 3.785411784, "stakan(250ml)": .25 },
    "Tezlik": { "km/soat": 1, "m/s": 3.6, "mil/soat": 1.609344, "tugun": 1.852 },
    "Ma'lumot": { MB: 1, KB: 1 / 1024, GB: 1024, TB: 1048576, bit: 1 / 8388608 }
  };
  mk("units", "📏", "Birlik o'giruvchi", "Uzunlik, vazn, maydon, hajm, tezlik, harorat va ma'lumot hajmi.",
    `<label>Turi</label><select id="k">${Object.keys(UN).concat("Harorat").map(k => `<option>${k}</option>`).join("")}</select>
     <div class="row"><div><label>Miqdor</label><input type="text" id="a" inputmode="decimal" value="1"></div><div><label>Birlik</label><select id="f"></select></div></div>
     <label>Natija birligi</label><select id="t"></select>`,
    (r, out) => {
      const fill = () => { const k = $(r, "#k").value, u = k === "Harorat" ? ["°C", "°F", "K"] : Object.keys(UN[k]); $(r, "#f").innerHTML = u.map(x => `<option>${x}</option>`).join(""); $(r, "#t").innerHTML = u.map((x, i) => `<option ${i === 1 ? "selected" : ""}>${x}</option>`).join(""); calc(); };
      const calc = () => {
        const k = $(r, "#k").value, v = num($(r, "#a").value), f = $(r, "#f").value, t = $(r, "#t").value; let res;
        if (k === "Harorat") { const c = f === "°C" ? v : f === "°F" ? (v - 32) * 5 / 9 : v - 273.15; res = t === "°C" ? c : t === "°F" ? c * 9 / 5 + 32 : c + 273.15; }
        else res = v * UN[k][f] / UN[k][t];
        out(`${fmt(v, 6)} ${f} = ${fmt(res, 6)} ${t}`);
      };
      const out2 = txt => show(r, txt, true); out.call = null;
      const o = out; out = out2;
      $(r, "#k").onchange = fill; ["#a", "#f", "#t"].forEach(s => $(r, s).oninput = calc); fill();
    });

  mk("random", "🎲", "Qur'a / tasodif", "Giveaway g'olibini tanlash, tanga tashlash, kub va tasodifiy son.",
    `<label>Ro'yxat (har qatorda bitta ishtirokchi)</label><textarea id="l" rows="5" placeholder="@ali&#10;@vali&#10;@sardor"></textarea>
     <div class="row"><div><label>G'oliblar soni</label><input type="text" id="n" inputmode="numeric" value="1"></div><div>${btn("w", "🏆 Tanlash")}</div></div>
     <div class="row">${btn("c", "🪙 Tanga")}${btn("d", "🎲 Kub")}</div>
     <div class="row"><div><label>Dan</label><input type="text" id="a" inputmode="numeric" value="1"></div><div><label>Gacha</label><input type="text" id="b" inputmode="numeric" value="100"></div></div>${btn("r", "Tasodifiy son")}`,
    (r, out) => {
      const rnd = n => { const x = crypto.getRandomValues(new Uint32Array(1))[0]; return x % n; };
      $(r, "#w").onclick = () => {
        const L = $(r, "#l").value.split("\n").map(s => s.trim()).filter(Boolean), n = Math.max(1, Math.min(+$(r, "#n").value || 1, L.length));
        if (!L.length) return out("Ro'yxatni to'ldiring");
        const a = [...L]; const w = []; while (w.length < n) w.push(a.splice(rnd(a.length), 1)[0]);
        out("🏆 G'oliblar:\n" + w.map((x, i) => `${i + 1}. ${x}`).join("\n"));
      };
      $(r, "#c").onclick = () => out(rnd(2) ? "🪙 Gerb" : "🪙 Raqam");
      $(r, "#d").onclick = () => out("🎲 " + (rnd(6) + 1));
      $(r, "#r").onclick = () => { const a = Math.round(num($(r, "#a").value)), b = Math.round(num($(r, "#b").value)); out(b < a ? "Chegaralar noto'g'ri" : String(a + rnd(b - a + 1))); };
    });

  function hsl(r, g, b) {
    r /= 255; g /= 255; b /= 255; const M = Math.max(r, g, b), m = Math.min(r, g, b); let h = 0, s = 0; const l = (M + m) / 2;
    if (M !== m) { const d = M - m; s = l > .5 ? d / (2 - M - m) : d / (M + m); h = M === r ? (g - b) / d + (g < b ? 6 : 0) : M === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; }
    return `hsl(${Math.round(h)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
  }
  mk("color", "🎯", "Rang kodlari", "Rang tanlang yoki HEX kiriting: HEX, RGB va HSL kodlarini oling.",
    `<label>Rang</label><input type="color" id="c" value="#e0246f"><label>yoki HEX kod</label><input type="text" id="h" value="#e0246f">`,
    (r, out) => {
      const upd = h => { const m = /^#?([0-9a-f]{6})$/i.exec(h.trim()); if (!m) return; const v = m[1], R = parseInt(v.slice(0, 2), 16), G = parseInt(v.slice(2, 4), 16), B = parseInt(v.slice(4, 6), 16);
        $(r, "#c").value = "#" + v; show(r, `HEX: #${v.toUpperCase()}\nRGB: rgb(${R}, ${G}, ${B})\n${hsl(R, G, B)}`); };
      $(r, "#c").oninput = e => { $(r, "#h").value = e.target.value; upd(e.target.value); }; $(r, "#h").oninput = e => upd(e.target.value); upd("#e0246f");
    });

  window.CLIENT_TOOLS = T;
})();
