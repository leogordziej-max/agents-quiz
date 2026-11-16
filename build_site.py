"""Construit le site : _site/index.html (bureau des agents) + _site/tiktoks.html (toutes les vidéos)."""
import json, os, shutil, html
HERE = os.path.dirname(os.path.abspath(__file__))
run = json.load(open(f"{HERE}/run.json"))
out = f"{HERE}/_site"; os.makedirs(f"{out}/tiktoks", exist_ok=True)
tpl = open(f"{HERE}/site/template.html").read()
open(f"{out}/index.html", "w").write(tpl.replace("__RUN__", json.dumps(run, ensure_ascii=False)))
if run.get("video"): shutil.copy(f"{HERE}/sorties/{run['video']}", f"{out}/{run['video']}")

idx_path = f"{HERE}/tiktoks/index.json"
idx = json.load(open(idx_path)) if os.path.exists(idx_path) else []
cartes = []
for v in reversed(idx):
    src = f"{HERE}/tiktoks/{v['fichier']}"
    if not os.path.exists(src): continue
    shutil.copy(src, f"{out}/tiktoks/{v['fichier']}")
    leg = html.escape(v["legende"]); f = html.escape(v["fichier"])
    qs = "".join(f"<li>{html.escape(q)}</li>" for q in v["questions"])
    cartes.append(f"""<article class="c"><video src="tiktoks/{f}" controls playsinline preload="none"></video>
<div class="m"><b>{html.escape(v['date'])}</b><ul>{qs}</ul>
<p class="leg">{leg}</p>
<a class="btn" href="tiktoks/{f}" download>Télécharger la vidéo</a>
<button class="btn2" onclick="navigator.clipboard.writeText(this.dataset.t);this.textContent='Légende copiée'" data-t="{leg}">Copier la légende</button></div></article>""")
page = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mes TikToks</title><style>
:root{{--bg:#f4f1ea;--panel:#fffdf8;--ink:#1d1a16;--muted:#6f675c;--line:#e3ddd1;--acc:#e8a400}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15130f;--panel:#1f1c17;--ink:#f1ece2;--muted:#a59c8e;--line:#332e26;--acc:#f0b429}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,sans-serif}}
.wrap{{max-width:980px;margin:0 auto;padding:20px 16px 40px}} h1{{margin:0 0 4px;font-size:24px}} .sub{{color:var(--muted);margin:0 0 16px}}
a{{color:inherit}} .grid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}}
.c{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px}}
video{{width:100%;aspect-ratio:9/16;border-radius:10px;background:#000}} ul{{margin:6px 0;padding-left:18px;color:var(--muted);font-size:13.5px}}
.leg{{font-size:13px;color:var(--muted)}} .btn,.btn2{{display:block;text-align:center;margin-top:8px;padding:10px;border-radius:999px;font:inherit;font-weight:600;border:0;cursor:pointer;text-decoration:none}}
.btn{{background:var(--ink);color:var(--bg)}} .btn2{{background:var(--line);color:var(--ink);width:100%}}
</style></head><body><div class="wrap"><h1>Mes TikToks</h1>
<p class="sub">{len(cartes)} vidéo(s), la plus récente en premier · <a href="./">← Bureau des agents</a></p>
<div class="grid">{''.join(cartes) or '<p>Aucune vidéo pour l’instant.</p>'}</div></div></body></html>"""
open(f"{out}/tiktoks.html", "w").write(page)
print(f"site OK — {len(cartes)} vidéo(s)")
