"""Build v15 submission.zip LOCALLY (no GPU) by extracting the agent-dir writes from notebook_src.py.
The agent dir (agent.yaml, prompts/system.md, configs/sampling.yaml, eval_config.yaml) is exactly what the
scored submission needs; a file-upload submission runs on Kaggle's scoring compute, not our GPU quota."""
import os, re, zipfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "notebook_src.py"), encoding="utf-8").read()
AGENT = os.path.join(HERE, "_agent_dir")
if os.path.exists(AGENT): shutil.rmtree(AGENT)
os.makedirs(os.path.join(AGENT, "prompts"), exist_ok=True)
os.makedirs(os.path.join(AGENT, "configs"), exist_ok=True)

# Pull each (AGENT_DIR / '<relpath>').write_text('''<content>''', ...) block out of the notebook source.
pat = re.compile(
    r"\(AGENT_DIR\s*/\s*(?P<parts>(?:'[^']+'\s*/\s*)*'[^']+')\)\.write_text\('''(?P<body>.*?)'''",
    re.DOTALL)
written = []
for m in pat.finditer(src):
    parts = re.findall(r"'([^']+)'", m.group("parts"))
    rel = os.path.join(*parts)
    body = m.group("body")
    dest = os.path.join(AGENT, rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    written.append(rel)
print("wrote agent files:", written)

# Zip at the ROOT of the archive (make_archive with root_dir=AGENT = dir entries, matching accepted structure)
zip_base = os.path.join(HERE, "submission")
if os.path.exists(zip_base + ".zip"): os.remove(zip_base + ".zip")
zip_path = shutil.make_archive(zip_base, "zip", root_dir=AGENT)
with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
print("submission.zip =", zip_path)
print("contents:", names)
# sanity: required files present
need = {"agent.yaml", "prompts/system.md", "configs/sampling.yaml", "eval_config.yaml"}
have = {n for n in names if not n.endswith("/")}
missing = need - have
print("MISSING:", missing if missing else "none - OK")
