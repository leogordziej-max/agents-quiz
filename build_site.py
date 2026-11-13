"""Construit la page « Bureau des agents » à partir de run.json : _site/index.html + la dernière vidéo."""
import json, os, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
run = json.load(open(f"{HERE}/run.json"))
out = f"{HERE}/_site"; os.makedirs(out, exist_ok=True)
tpl = open(f"{HERE}/site/template.html").read()
open(f"{out}/index.html", "w").write(tpl.replace("__RUN__", json.dumps(run, ensure_ascii=False)))
if run.get("video"): shutil.copy(f"{HERE}/sorties/{run['video']}", f"{out}/{run['video']}")
print("site OK")
