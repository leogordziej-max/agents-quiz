"""Génère une vidéo quiz verticale (1080x1920), version dynamique :
accroche percutante, musique rythmée, bruitages, cartes qui « pop », compte à rebours animé,
flash + confettis à la révélation, barre de progression.
Usage: python3 make_quiz.py quiz.json out.mp4
"""
import json, subprocess, sys, wave, os, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 22050
VOICE = os.path.join(os.path.dirname(__file__), "voices/fr-siwis-medium.onnx")
TMP = "/tmp/quizbuild"; os.makedirs(TMP, exist_ok=True)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FC = {}
def font(s):
    s = max(8, int(s))
    if s not in _FC: _FC[s] = ImageFont.truetype(FB, s)
    return _FC[s]

# Accroches : (texte lu, lignes affichées). Pas de fausse statistique, juste un défi.
HOOKS = [
    ("Trois questions, trois secondes chacune. T'es cap ?", ["3 QUESTIONS", "3 SECONDES", "T'ES CAP ?"]),
    ("Si tu fais trois sur trois, t'es un vrai génie.", ["3 SUR 3 ?", "ALORS T'ES", "UN GÉNIE"]),
    ("Prouve que t'as une bonne culture générale. Go !", ["PROUVE-LE", "EN 30", "SECONDES"]),
    ("Arrête de scroller, et réponds vite !", ["STOP !", "RÉPONDS", "VITE"]),
]
OUTRO_VOIX = "Alors, t'as eu combien ? Dis-le en commentaire, et reviens demain pour le prochain quiz !"

# ---------- audio ----------
def tts(text, name):
    path = f"{TMP}/{name}.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path,
                    "--length-scale", "0.84"], input=text.encode(), check=True,
                   stderr=subprocess.DEVNULL)
    with wave.open(path) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    a = a.astype(np.float32) / 32768
    if sr != SR: a = np.interp(np.linspace(0, len(a), int(len(a) * SR / sr)), np.arange(len(a)), a)
    return a * 1.15

def tone(freq, dur, vol=0.25, decay=18):
    t = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * decay) * vol).astype(np.float32)

def noise(dur, vol, decay):
    t = np.arange(int(dur * SR)) / SR
    return (np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * decay) * vol).astype(np.float32)

def whoosh():
    n = noise(0.35, 0.18, 0)
    env = np.sin(np.linspace(0, np.pi, len(n))) ** 2
    k = 40; sm = np.convolve(n, np.ones(k) / k, mode="same")       # passe-bas grossier
    return (sm * env * 3).astype(np.float32)

TICK = tone(1500, 0.07, 0.30, 50)
TICK_LAST = tone(2000, 0.10, 0.34, 40)
DING = tone(880, 0.6, 0.25, 5)
_d2 = tone(1320, 0.6, 0.22, 5); DING[int(0.07 * SR):] += _d2[: len(DING) - int(0.07 * SR)]
POP = tone(600, 0.08, 0.3, 60)
WHOOSH = whoosh()

def musique(total, bpm=124):
    """Boucle rythmée générée (libre de droits) : grosse caisse, charleston, basse."""
    n = int(total * SR) + SR; m = np.zeros(n, np.float32)
    beat = 60 / bpm; t = np.arange(int(0.25 * SR)) / SR
    kick = (np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 14) * 0.55).astype(np.float32)
    hat = noise(0.05, 0.10, 90); hat = hat - np.convolve(hat, np.ones(6) / 6, mode="same")
    basse = [55, 55, 65.4, 49]
    b = 0
    while b * beat < total:
        s = int(b * beat * SR)
        m[s:s + len(kick)] += kick[: max(0, n - s)]
        h = int((b + 0.5) * beat * SR); m[h:h + len(hat)] += hat[: max(0, n - h)]
        if b % 2 == 0:
            f = basse[(b // 8) % 4]; bl = tone(f, beat * 1.8, 0.22, 2.5)
            m[s:s + len(bl)] += bl[: max(0, n - s)]
        b += 1
    return m * 0.35

# ---------- timeline ----------
def build(quiz):
    hook = HOOKS[quiz.get("hook", random.randrange(len(HOOKS)))]
    quiz["_hook"] = hook
    parts, t = [], 0.0
    add = lambda seg, at: parts.append((at, seg))
    events = []
    intro = tts(hook[0], "intro")
    add(WHOOSH, 0.0); add(intro, 0.15)
    tend = 0.15 + len(intro) / SR + 0.25
    events.append(("intro", 0.0, tend, None)); t = tend
    for i, q in enumerate(quiz["questions"]):
        qa = tts(q["question"], f"q{i}")
        ra = tts(q["reponse_voix"], f"r{i}")
        t0 = t; add(WHOOSH, t0); add(qa, t0 + 0.2)
        tq = t0 + 0.2 + len(qa) / SR + 0.15
        for k in range(3): add(TICK_LAST if k == 2 else TICK, tq + k)
        tc = tq + 3.0
        add(DING, tc); add(POP, tc); add(ra, tc + 0.3)
        tend = tc + 0.3 + len(ra) / SR + 0.5
        events.append(("q", t0, tend, dict(i=i, q=q, tq=tq, tc=tc)))
        t = tend
    out = tts(quiz.get("outro_voix", OUTRO_VOIX), "outro")
    add(WHOOSH, t); add(out, t + 0.15)
    total = t + 0.15 + len(out) / SR + 0.6
    events.append(("outro", t, total, None))
    mix = musique(total)[: int(total * SR) + SR]
    for at, seg in parts:
        s = int(at * SR); e = min(len(mix), s + len(seg)); mix[s:e] += seg[: e - s]
    mix = np.tanh(mix * 1.1) * 0.95
    with wave.open(f"{TMP}/mix.wav", "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return events, total

# ---------- visuels ----------
PALETTES = [((255, 61, 110), (92, 26, 186)), ((0, 180, 216), (60, 30, 160)),
            ((255, 140, 0), (200, 30, 90)), ((30, 200, 130), (20, 70, 160)), ((150, 60, 255), (255, 60, 140))]
ACC, GOOD, WHITE, INK = (255, 214, 0), (40, 210, 110), (255, 255, 255), (28, 22, 54)

def make_bg(c1, c2):
    y = np.linspace(0, 1, H)[:, None, None]; x = np.linspace(0, 1, W)[None, :, None]
    g = np.clip(0.75 * y + 0.25 * x, 0, 1)
    arr = np.array(c1) * (1 - g) + np.array(c2) * g
    stripes = ((np.add.outer(np.arange(H), np.arange(W)) // 90) % 2)[..., None] * 10
    return Image.fromarray(np.clip(arr + stripes, 0, 255).astype(np.uint8))
BGS = [make_bg(*p) for p in PALETTES]

rng = random.Random(7)
SHAPES = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(20, 70), rng.uniform(-60, 60), rng.uniform(-90, -30), rng.choice("ost"))
          for _ in range(16)]

def ease_out(x): x = max(0., min(1., x)); return 1 - (1 - x) ** 3
def back(x):
    x = max(0., min(1., x)); c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def shapes(d, t, col):
    for x0, y0, r, vx, vy, kind in SHAPES:
        x = (x0 + vx * t) % (W + 200) - 100; y = (y0 + vy * t) % (H + 200) - 100
        if kind == "o": d.ellipse((x - r, y - r, x + r, y + r), outline=col, width=6)
        elif kind == "s": d.rectangle((x - r, y - r, x + r, y + r), outline=col, width=6)
        else: d.polygon([(x, y - r), (x + r, y + r), (x - r, y + r)], outline=col, width=6)

def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) <= maxw: cur = test
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def big(d, xy, text, size, fill=WHITE, stroke=8, anchor="mm"):
    d.text(xy, text, font=font(size), fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=INK)

def card(q, w=940):
    f = font(70); tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = wrap(tmp, q["question"], f, w - 90)
    h = 90 + len(lines) * 84
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 12, w, h), 44, fill=(0, 0, 0, 90))
    d.rounded_rectangle((0, 0, w, h - 12), 44, fill=WHITE)
    for k, l in enumerate(lines):
        d.text((w / 2, 45 + k * 84), l, font=f, fill=INK, anchor="ma")
    return img

_CARDS = {}
CONF_COLS = [(255, 214, 0), (255, 61, 110), (0, 200, 255), (40, 210, 110), (255, 255, 255)]

def frame(events, t, nq):
    ev = next((e for e in events if e[1] <= t < e[2]), events[-1])
    kind, t0, t1, data = ev
    idx = 0 if kind == "intro" else 4 if kind == "outro" else 1 + data["i"]
    img = BGS[idx % len(BGS)].copy(); d = ImageDraw.Draw(img)
    shapes(d, t, tuple(min(255, c + 40) for c in PALETTES[idx % len(PALETTES)][0]))
    total = events[-1][2]
    # barre de progression globale
    d.rectangle((0, 0, W, 14), fill=(0, 0, 0)); d.rectangle((0, 0, int(W * t / total), 14), fill=ACC)
    dt = t - t0
    ox = oy = 0
    if kind == "intro":
        hook = events[0][3] or None
        lines = QUIZ_HOOK[1]
        for k, l in enumerate(lines):
            p = back((dt - 0.12 - k * 0.35) / 0.3)
            if p <= 0: continue
            size = (150 if k == 2 else 120) * max(0.01, p)
            big(d, (W / 2, 640 + k * 230), l, size, fill=ACC if k == 2 else WHITE, stroke=max(1, int(10 * p)))
        big(d, (W / 2, 1500), "QUIZ CULTURE G", 54, fill=WHITE, stroke=5)
    elif kind == "outro":
        p = back(dt / 0.35)
        big(d, (W / 2, 720), "T'AS EU", 130 * max(.01, p), stroke=10)
        big(d, (W / 2, 880), "COMBIEN ?", 150 * max(.01, p), fill=ACC, stroke=10)
        p2 = ease_out((dt - 0.5) / 0.4)
        if p2 > 0:
            d.rounded_rectangle((110, 1080 + 60 * (1 - p2), W - 110, 1230 + 60 * (1 - p2)), 40, fill=WHITE)
            d.text((W / 2, 1155 + 60 * (1 - p2)), "Écris ton score en commentaire", font=font(44), fill=INK, anchor="mm")
            big(d, (W / 2, 1380), "Nouveau quiz chaque jour", 52, stroke=5)
    else:
        i, q, tq, tc = data["i"], data["q"], data["tq"], data["tc"]
        # légère secousse pendant la dernière seconde du compte à rebours
        if tc - 1 <= t < tc: ox, oy = int(6 * math.sin(t * 90)), int(5 * math.cos(t * 77))
        pill = f"QUESTION {i + 1}/{nq}"
        d.rounded_rectangle((W / 2 - 220, 70, W / 2 + 220, 160), 45, fill=INK)
        d.text((W / 2, 115), pill, font=font(50), fill=ACC, anchor="mm")
        key = id(q)
        if key not in _CARDS: _CARDS[key] = card(q)
        c = _CARDS[key]; p = back(dt / 0.38)
        if p > 0:
            s = max(0.05, p); cw, ch = int(c.width * s), int(c.height * s)
            cc = c.resize((cw, ch), Image.BILINEAR) if s != 1 else c
            img.paste(cc, (int(W / 2 - cw / 2) + ox, int(300 + c.height / 2 - ch / 2) + oy), cc)
        y0 = 300 + c.height + 80
        for k, opt in enumerate(q["options"]):
            pk = back((dt - 0.3 - 0.12 * k) / 0.3)
            if pk <= 0: continue
            sgn = -1 if k % 2 == 0 else 1
            xo = int(sgn * 700 * (1 - pk)) + ox; y = y0 + k * 200 + oy
            fill, tf, grow = (255, 255, 255), INK, 0
            if t >= tc:
                if k == q["bonne"]:
                    fill, tf = GOOD, WHITE; grow = int(18 * math.sin(min(1, (t - tc) / 0.25) * math.pi))
                else: fill, tf = (120, 110, 150), (210, 205, 225)
            d.rounded_rectangle((90 + xo - grow, y + 10 - grow, W - 90 + xo + grow, y + 170 + grow), 40, fill=(0, 0, 0))
            d.rounded_rectangle((90 + xo - grow, y - grow, W - 90 + xo + grow, y + 160 + grow), 40, fill=fill)
            d.ellipse((115 + xo, y + 25, 225 + xo, y + 135), fill=ACC if not (t >= tc and k != q["bonne"]) else (90, 85, 110))
            d.text((170 + xo, y + 80), "ABC"[k], font=font(60), fill=INK, anchor="mm")
            fs = 62
            while fs > 34 and d.textlength(opt, font=font(fs)) > W - 90 - 260 - 40: fs -= 2
            d.text((260 + xo, y + 80), opt, font=font(fs), fill=tf, anchor="lm")
        ybot = y0 + 3 * 200 + 40
        if tq <= t < tc:
            rem = tc - t; n = math.ceil(rem); frac = rem - (n - 1)
            col = [(255, 60, 60), (255, 150, 0), ACC][n - 1]
            r = 120; cx, cy = W / 2 + ox, ybot + 150 + oy
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK)
            d.arc((cx - r + 10, cy - r + 10, cx + r - 10, cy + r - 10), -90, -90 + 360 * (rem / 3), fill=col, width=22)
            pulse = 1 + 0.35 * max(0, frac - 0.7) / 0.3
            big(d, (cx, cy), str(n), 130 * pulse, fill=col, stroke=0)
        elif t >= tc:
            p = ease_out((t - tc - 0.2) / 0.35)
            if p > 0 and q.get("bonus"):
                f = font(46); lines = wrap(d, q["bonus"], f, 860)
                hh = 50 + len(lines) * 58; yb = ybot + 60 + 50 * (1 - p)
                d.rounded_rectangle((80, yb, W - 80, yb + hh), 34, fill=INK)
                for k, l in enumerate(lines):
                    d.text((W / 2, yb + 28 + k * 58), l, font=f, fill=WHITE, anchor="ma")
            # confettis
            ct = t - tc
            if ct < 1.4:
                cr = random.Random(i * 101)
                ycen = y0 + q["bonne"] * 200 + 80
                for _ in range(70):
                    a = cr.uniform(0, 2 * math.pi); v = cr.uniform(500, 1400)
                    x = W / 2 + math.cos(a) * v * ct; y = ycen + math.sin(a) * v * ct + 900 * ct * ct
                    s = cr.uniform(10, 20); col = cr.choice(CONF_COLS)
                    d.rectangle((x - s / 2, y - s / 3, x + s / 2, y + s / 3), fill=col)
            if ct < 0.1:  # flash
                img = Image.blend(img, Image.new("RGB", (W, H), WHITE), 0.6 * (1 - ct / 0.1))
    # flash blanc aux changements de scène
    if dt < 0.08 and kind != "intro":
        img = Image.blend(img, Image.new("RGB", (W, H), WHITE), 0.5 * (1 - dt / 0.08))
    return img

QUIZ_HOOK = HOOKS[0]

def render(quiz, dst):
    global QUIZ_HOOK
    events, total = build(quiz); QUIZ_HOOK = quiz["_hook"]
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", f"{TMP}/mix.wav",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    for f in range(int(total * FPS)):
        ff.stdin.write(frame(events, f / FPS, len(quiz["questions"])).convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode: raise RuntimeError("ffmpeg a échoué")
    return total

if __name__ == "__main__":
    q = json.load(open(sys.argv[1])); print(f"OK {sys.argv[2]} — {render(q, sys.argv[2]):.1f}s")
