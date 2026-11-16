"""Chaîne d'agents v2 : produit une vidéo quiz de bout en bout et journalise chaque étape dans run.json.

- Avec la variable d'environnement GEMINI_API_KEY : Hugo écrit des questions inédites avec Gemini,
  Inès les vérifie (second appel Gemini, avec recherche Google si disponible).
- Sans clé : Hugo pioche dans banque_questions.json (mode secours).
Usage : python3 agents.py
"""
import json, os, re, random, subprocess, sys, time, datetime, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_quiz

KEY = os.environ.get("GEMINI_API_KEY", "").strip()
API = "https://generativelanguage.googleapis.com/v1beta"
BANK = json.load(open(f"{HERE}/banque_questions.json"))
HIST_PATH = f"{HERE}/historique.json"
HIST = json.load(open(HIST_PATH)) if os.path.exists(HIST_PATH) else {"utilisees": [], "videos": 0}
LOG = {"debut": datetime.datetime.now().isoformat(timespec="seconds"), "agents": [],
       "source": "gemini" if KEY else "banque"}
T0 = time.time()
CTX = {}

# ---------------- Gemini ----------------
def _req(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
    for essai in range(4):
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 503) and essai < 3:
                time.sleep(15 * (essai + 1)); continue
            raise RuntimeError(f"Gemini HTTP {e.code} : {msg}")

def choisir_modele():
    if os.environ.get("GEMINI_MODEL"): return os.environ["GEMINI_MODEL"]
    noms = []
    for m in _req(f"{API}/models?pageSize=200").get("models", []):
        n = m["name"].split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []): continue
        if "flash" not in n or any(x in n for x in ("lite", "image", "tts", "live", "audio", "thinking", "exp")): continue
        noms.append(n)
    if not noms: raise RuntimeError("Aucun modèle Gemini Flash disponible pour cette clé")
    def cle(n):
        v = re.findall(r"(\d+(?:\.\d+)?)", n); stable = "preview" not in n
        return (stable, float(v[0]) if v else 0, -len(n))
    return max(noms, key=cle)

def gemini(prompt, json_mode=True, search=False, temperature=0.9):
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temperature}}
    if json_mode and not search: body["generationConfig"]["responseMimeType"] = "application/json"
    if search: body["tools"] = [{"google_search": {}}]
    out = _req(f"{API}/models/{CTX['modele']}:generateContent", body)
    txt = "".join(p.get("text", "") for p in out["candidates"][0]["content"].get("parts", []))
    if not json_mode: return txt
    m = re.search(r"[\[{].*[\]}]", txt, re.S)
    return json.loads(m.group(0) if m else txt)

# ---------------- agents ----------------
def agent(nom, role):
    def deco(fn):
        def run(*a):
            t0 = time.time(); entry = {"nom": nom, "role": role, "debut": round(t0 - T0, 2)}
            try:
                out, msg, details = fn(*a)
                entry.update(statut="ok", message=msg, details=details)
            except Exception as e:
                out = None; entry.update(statut="erreur", message=str(e)[:300], details=[])
            entry["duree"] = round(time.time() - t0, 2)
            LOG["agents"].append(entry); print(f"[{nom}] {entry['statut']} — {entry['message']}", flush=True)
            if entry["statut"] != "ok":
                LOG["duree_totale"] = round(time.time() - T0, 1)
                json.dump(LOG, open(f"{HERE}/run.json", "w"), ensure_ascii=False, indent=1)
                raise SystemExit(1)
            return out
        return run
    return deco

THEMES = ["Géographie", "Histoire", "Sciences", "Animaux", "Espace", "Corps humain", "Art", "Sport",
          "Cinéma", "Musique", "Langue française", "Inventions", "Nourriture", "Records", "Mythologie"]

@agent("Léa", "Choix des thèmes")
def choisir_theme():
    recents = HIST.get("themes_recents", [])[-6:]
    dispo = [t for t in THEMES if t not in recents] or THEMES
    themes = random.sample(dispo, 3)
    details = [f"Thèmes du jour : {', '.join(themes)}"]
    if recents: details.append(f"Évités (déjà faits récemment) : {', '.join(recents)}")
    if KEY:
        CTX["modele"] = choisir_modele(); details.append(f"Modèle IA : {CTX['modele']}")
    return themes, "3 thèmes choisis", details

FORMAT = """Chaque question est un objet JSON avec exactement ces clés :
- "theme" : le thème
- "question" : en français, 70 caractères maximum, se termine par " ?"
- "options" : liste de 3 réponses courtes (18 caractères maximum chacune)
- "bonne" : index (0, 1 ou 2) de la bonne réponse, varie sa position
- "reponse_voix" : exactement "Réponse X : <bonne option> !" avec X = A, B ou C
- "bonus" : une anecdote vraie et vérifiable liée à la réponse, 55 caractères maximum"""

def ecrire_questions(themes, n, exclure):
    prompt = f"""Tu écris des questions pour un quiz de culture générale en vidéo courte (TikTok), public français ado/adulte.
Écris {n} questions à choix multiple, réparties sur ces thèmes : {', '.join(themes)}.
Règles :
- Uniquement des faits établis, stables et vérifiables. Pas d'actualité, pas de chiffre approximatif ou contesté, pas de piège ambigu.
- Une seule bonne réponse indiscutable ; les deux autres doivent être plausibles mais clairement fausses.
- Difficulté moyenne : pas évident, mais une bonne partie des gens peut trouver.
- N'utilise aucune de ces questions déjà publiées : {json.dumps(exclure[-150:], ensure_ascii=False)}
{FORMAT}
Réponds uniquement avec une liste JSON de {n} objets."""
    qs = gemini(prompt)
    return qs if isinstance(qs, list) else qs.get("questions", [])

@agent("Hugo", "Rédaction du quiz")
def rediger(themes):
    if not KEY:
        dispo = [q for q in BANK if q["question"] not in HIST["utilisees"]]
        if len(dispo) < 3: raise ValueError("Pas de clé Gemini et banque de secours épuisée")
        random.shuffle(dispo); choix = dispo[:3]
        return choix, f"3 questions tirées de la banque vérifiée ({len(dispo) - 3} restantes)", [q["question"] for q in choix]
    cands = ecrire_questions(themes, 6, HIST["utilisees"])
    return cands, f"{len(cands)} questions candidates écrites par l'IA", [q.get("question", "?") for q in cands]

def check_format(q):
    try:
        assert set(("question", "options", "bonne", "reponse_voix", "bonus")) <= set(q), "clés manquantes"
        assert len(q["options"]) == 3, "il faut 3 options"
        assert len(set(o.lower() for o in q["options"])) == 3, "options en double"
        assert int(q["bonne"]) in (0, 1, 2), "index invalide"
        q["bonne"] = int(q["bonne"])
        assert q["options"][q["bonne"]].lower() in q["reponse_voix"].lower(), "réponse lue ≠ bonne option"
        assert "ABC"[q["bonne"]] in q["reponse_voix"].split(":")[0], "mauvaise lettre annoncée"
        assert len(q["question"]) <= 80, "question trop longue"
        assert all(len(o) <= 24 for o in q["options"]), "option trop longue"
        assert len(q["bonus"]) <= 70, "anecdote trop longue"
        assert q["question"] not in HIST["utilisees"], "déjà publiée"
        return None
    except AssertionError as e:
        return str(e)

def verif_faits(qs):
    lst = [{"id": i, "question": q["question"], "options": q["options"], "bonne_reponse": q["options"][q["bonne"]],
            "anecdote": q["bonus"]} for i, q in enumerate(qs)]
    prompt = f"""Tu es vérificateur de faits, strict. Pour chaque question de quiz ci-dessous, vérifie (en cherchant si besoin) :
1. que la bonne réponse indiquée est exacte et indiscutable ;
2. que les deux autres options sont bien fausses ;
3. que l'anecdote est exacte.
Au moindre doute, rejette. Questions : {json.dumps(lst, ensure_ascii=False)}
Réponds uniquement avec une liste JSON : [{{"id": 0, "ok": true, "raison": "courte justification"}}, ...]"""
    try:
        res = gemini(prompt, search=True, temperature=0); mode = "avec recherche Google"
    except Exception:
        res = gemini(prompt, temperature=0); mode = "sans recherche"
    return {int(r["id"]): r for r in res}, mode

@agent("Inès", "Vérification")
def verifier(cands, themes):
    details = []; bons = []
    for q in cands:
        err = check_format(q)
        if err: details.append(f"✘ {q.get('question', '?')} — {err}")
        else: bons.append(q)
    if KEY and bons:
        res, mode = verif_faits(bons); details.insert(0, f"Vérification des faits {mode}")
        ok = []
        for i, q in enumerate(bons):
            r = res.get(i, {"ok": False, "raison": "pas de verdict"})
            if r.get("ok") is True: ok.append(q); details.append(f"✔ {q['question']} → {q['options'][q['bonne']]}")
            else: details.append(f"✘ {q['question']} — {r.get('raison', '')[:90]}")
        bons = ok
    if len(bons) < 3:
        if KEY and not CTX.get("relance"):
            CTX["relance"] = True; details.append("Moins de 3 questions valides : je redemande à Hugo")
            nouv = ecrire_questions(themes, 6, HIST["utilisees"] + [q["question"] for q in cands])
            for q in nouv:
                if len(bons) >= 3: break
                if check_format(q) is None:
                    res, _ = verif_faits([q])
                    if res.get(0, {}).get("ok") is True: bons.append(q); details.append(f"✔ (relance) {q['question']}")
        if len(bons) < 3: raise ValueError("Pas assez de questions validées : " + " | ".join(details[-4:]))
    choix = bons[:3]
    quiz = {"intro": "Trois questions. Combien tu en as ?", "questions": choix,
            "outro": "Alors, ton score ? Dis-le en commentaire !"}
    return quiz, f"{len(bons)} questions validées, 3 retenues", details

@agent("Malo", "Voix off")
def voix(quiz):
    events, total = make_quiz.build(quiz); make_quiz.QUIZ_HOOK = quiz["_hook"]
    return (events, total), f"Voix, musique et bruitages prêts, durée {total:.1f} s", [f"Accroche : {quiz['_hook'][0]}", "Voix : Piper fr-siwis (gratuite)", "Musique générée, libre de droits"]

@agent("Zoé", "Montage")
def montage(quiz, ev):
    events, total = ev
    n = HIST["videos"] + 1; dst = f"{HERE}/sorties/quiz_{n:03d}.mp4"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", "1080x1920", "-r", "30", "-i", "-", "-i", f"{make_quiz.TMP}/mix.wav", "-c:v", "libx264",
        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", "-movflags", "+faststart", dst],
        stdin=subprocess.PIPE)
    for f in range(int(total * 30)):
        ff.stdin.write(make_quiz.frame(events, f / 30, 3).convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    if ff.returncode: raise RuntimeError("ffmpeg a échoué")
    return dst, f"Vidéo montée : {os.path.basename(dst)}", ["1080×1920, 30 i/s, H.264"]

@agent("Sam", "Contrôle qualité")
def controle(dst):
    p = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,width,height:format=duration,size", "-of", "json", dst]))
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    dur = float(p["format"]["duration"]); mo = int(p["format"]["size"]) / 1e6
    assert (v["width"], v["height"]) == (1080, 1920), "mauvais format"
    assert any(s["codec_type"] == "audio" for s in p["streams"]), "pas de son"
    assert 15 <= dur <= 60, f"durée hors limites : {dur:.1f}s"
    return dst, "Vidéo conforme", ["Format vertical OK", "Son présent", f"Durée {dur:.1f} s", f"Poids {mo:.1f} Mo"]

@agent("Noé", "Publication")
def publier(dst, quiz):
    legende = "Quiz culture G : t'as eu combien ? 🧠 #quiz #culturegenerale #apprendresurtiktok"
    open(dst.replace(".mp4", "_legende.txt"), "w").write(legende)
    # rangement dans le dossier tiktoks/ (gardé dans le dépôt, 60 dernières vidéos)
    import shutil
    dossier = f"{HERE}/tiktoks"; os.makedirs(dossier, exist_ok=True)
    jour = datetime.date.today().isoformat()
    nom = f"{jour}_{os.path.basename(dst)}"
    shutil.copy(dst, f"{dossier}/{nom}")
    idx_path = f"{dossier}/index.json"
    idx = json.load(open(idx_path)) if os.path.exists(idx_path) else []
    idx.append({"date": jour, "fichier": nom, "legende": legende,
                "questions": [q["question"] for q in quiz["questions"]]})
    while len(idx) > 60:
        vieux = idx.pop(0)
        try: os.remove(f"{dossier}/{vieux['fichier']}")
        except FileNotFoundError: pass
    json.dump(idx, open(idx_path, "w"), ensure_ascii=False, indent=1)
    return dst, "Rangée dans « Mes TikToks », prête à publier", [f"Fichier : tiktoks/{nom}", f"Légende : {legende}", "Comptes TikTok/YouTube pas encore connectés"]

if __name__ == "__main__":
    themes = choisir_theme(); cands = rediger(themes); quiz = verifier(cands, themes)
    ev = voix(quiz); dst = montage(quiz, ev); controle(dst); publier(dst, quiz)
    HIST["utilisees"] += [q["question"] for q in quiz["questions"]]; HIST["videos"] += 1
    HIST["themes_recents"] = (HIST.get("themes_recents", []) + themes)[-12:]
    json.dump(HIST, open(HIST_PATH, "w"), ensure_ascii=False, indent=1)
    LOG["video"] = os.path.basename(dst); LOG["duree_totale"] = round(time.time() - T0, 1)
    LOG["quiz"] = quiz["questions"]
    json.dump(LOG, open(f"{HERE}/run.json", "w"), ensure_ascii=False, indent=1)
