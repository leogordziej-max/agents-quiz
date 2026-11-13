"""Génère une vidéo quiz verticale (1080x1920) à partir d'un JSON de questions.
Usage: python3 make_quiz.py quiz.json out.mp4
"""
import json, subprocess, sys, wave, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 22050
VOICE = os.path.join(os.path.dirname(__file__), "voices/fr-siwis-medium.onnx")
TMP = "/tmp/quizbuild"; os.makedirs(TMP, exist_ok=True)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(s): return ImageFont.truetype(FB, s)

# ---------- audio ----------
def tts(text, name):
    path = f"{TMP}/{name}.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path,
                    "--length-scale", "0.92"], input=text.encode(), check=True,
                   stderr=subprocess.DEVNULL)
    with wave.open(path) as w:
        sr = w.getframerate(); a = np.frombuffer(w.readframes(w.getnframes()), np.int16)
    a = a.astype(np.float32) / 32768
    if sr != SR: a = np.interp(np.linspace(0, len(a), int(len(a) * SR / sr)), np.arange(len(a)), a)
    return a

def tone(freq, dur, vol=0.25, decay=18):
    t = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * decay) * vol).astype(np.float32)

TICK = tone(1400, 0.08, 0.18, 40)
DING = tone(880, 0.6, 0.22, 5) + np.pad(tone(1320, 0.45, 0.18, 6), (int(0.08 * SR), int(0.6 * SR)))[: int(0.6 * SR)]

# ---------- timeline ----------
def build(quiz):
    events, audio_parts, t = [], [], 0.0
    def add(seg, at):  audio_parts.append((at, seg))
    intro = tts(quiz["intro"], "intro")
    events.append(("intro", t, t + len(intro) / SR + 0.4, None)); add(intro, t)
    t += len(intro) / SR + 0.4
    for i, q in enumerate(quiz["questions"]):
        qa = tts(q["question"], f"q{i}")
        ra = tts(q["reponse_voix"], f"r{i}")
        t0 = t; tq = t0 + len(qa) / SR + 0.3
        add(qa, t0 + 0.15)
        tc = tq + 3.0
        for k in range(3): add(TICK, tq + k)
        add(DING, tc); add(ra, tc + 0.25)
        tend = tc + 0.25 + len(ra) / SR + 0.6
        events.append(("q", t0, tend, dict(i=i, q=q, tq=tq, tc=tc)))
        t = tend
    out = tts(quiz["outro"], "outro")
    add(out, t); events.append(("outro", t, t + len(out) / SR + 1.0, None))
    total = t + len(out) / SR + 1.0
    mix = np.zeros(int(total * SR) + SR, np.float32)
    for at, seg in audio_parts:
        s = int(at * SR); mix[s:s + len(seg)] += seg
    mix = np.clip(mix, -1, 1)
    with wave.open(f"{TMP}/mix.wav", "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    return events, total

# ---------- visuels ----------
BG1, BG2 = (24, 20, 60), (88, 28, 120)
ACC, GOOD, BAD, WHITE = (255, 196, 0), (46, 204, 113), (90, 90, 120), (255, 255, 255)
def background():
    g = np.linspace(0, 1, H)[:, None]
    arr = (np.array(BG1) * (1 - g)[..., None] + np.array(BG2) * g[..., None]).repeat(W, 1)
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for x, y, r in [(150, 300, 220), (950, 1500, 300), (900, 250, 120)]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 0), outline=(255, 255, 255), width=3)
    return Image.blend(Image.fromarray(arr.astype(np.uint8)), img, 0.08)
BG = background()

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3

def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) <= maxw: cur = test
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def ctext(d, y, text, f, fill=WHITE, maxw=920, lh=1.18):
    lines = wrap(d, text, f, maxw)
    for k, l in enumerate(lines):
        d.text((W / 2, y + k * f.size * lh), l, font=f, fill=fill, anchor="ma")
    return y + len(lines) * f.size * lh

def frame(events, t, nq):
    img = BG.copy(); d = ImageDraw.Draw(img)
    ev = next((e for e in events if e[1] <= t < e[2]), events[-1])
    kind, t0, t1, data = ev
    d.text((W / 2, 110), "QUIZ CULTURE G", font=font(46), fill=ACC, anchor="ma")
    if kind == "intro":
        p = ease((t - t0) / 0.5)
        ctext(d, 700 - 60 * (1 - p), "3 questions.", font(110))
        ctext(d, 880, "Combien tu en as ?", font(84), fill=ACC)
    elif kind == "outro":
        p = ease((t - t0) / 0.5)
        ctext(d, 720, "Ton score ?", font(110))
        ctext(d, 900 + 40 * (1 - p), "Dis-le en commentaire", font(70), fill=ACC)
    else:
        i, q, tq, tc = data["i"], data["q"], data["tq"], data["tc"]
        # progression
        for k in range(nq):
            x = W / 2 + (k - (nq - 1) / 2) * 70
            d.ellipse((x - 16, 200, x + 16, 232), fill=ACC if k <= i else (255, 255, 255, 60))
        p = ease((t - t0) / 0.4)
        d.rounded_rectangle((70, 330 - 40 * (1 - p), W - 70, 760), 40, fill=(255, 255, 255))
        ctext(d, 400, q["question"], font(68), fill=(30, 25, 60), maxw=860)
        letters = "ABC"
        for k, opt in enumerate(q["options"]):
            pk = ease((t - t0 - 0.25 - 0.15 * k) / 0.35)
            if pk <= 0: continue
            y = 860 + k * 210; xo = int(300 * (1 - pk))
            col = (255, 255, 255, 40)
            fill = (60, 50, 120); tf = WHITE
            if t >= tc:
                if k == q["bonne"]: fill = GOOD
                else: fill, tf = BAD, (170, 170, 190)
            d.rounded_rectangle((90 + xo, y, W - 90 + xo, y + 170), 34, fill=fill)
            d.ellipse((120 + xo, y + 30, 230 + xo, y + 140), fill=ACC)
            d.text((175 + xo, y + 85), letters[k], font=font(60), fill=(30, 25, 60), anchor="mm")
            fs = 62
            while fs > 34 and d.textlength(opt, font=font(fs)) > W - 90 - 270 - 30: fs -= 2
            d.text((270 + xo, y + 85), opt, font=font(fs), fill=tf, anchor="lm")
        # compte à rebours
        if tq <= t < tc:
            rem = tc - t; n = math.ceil(rem)
            frac = rem - (n - 1); s = 1 + 0.25 * max(0, frac - 0.75) * 4
            r = 110
            d.ellipse((W / 2 - r, 1530, W / 2 + r, 1530 + 2 * r), fill=ACC)
            d.text((W / 2, 1530 + r), str(n), font=font(int(130 * s)), fill=(30, 25, 60), anchor="mm")
            bw = (W - 200) * (rem / 3)
            d.rounded_rectangle((100, 1800, 100 + max(bw, 30), 1830), 15, fill=ACC)
        elif t >= tc:
            ctext(d, 1560, q.get("bonus", ""), font(48), fill=(230, 230, 255), maxw=900)
    return img

def main(src, dst):
    quiz = json.load(open(src))
    events, total = build(quiz)
    n = int(total * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", f"{TMP}/mix.wav",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", dst], stdin=subprocess.PIPE)
    for f in range(n):
        ff.stdin.write(frame(events, f / FPS, len(quiz["questions"])).convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    print(f"OK {dst} — {total:.1f}s")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
