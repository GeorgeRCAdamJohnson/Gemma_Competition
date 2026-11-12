"""fastapi_14492 swings most between high and low passes (100% vs 45%). What do solved runs do differently?
Kaggle batch 3 logs (nodes with logs): first files read/grepped, and the file the final patch touches."""
import json
import re
from collections import Counter
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
T = "fastapi_14492"
out = []
for tr in Path("Outputs/kaggle_batch3/results").glob("node*/run_*/task_results.jsonl"):
    r = next((json.loads(l) for l in tr.read_text(encoding="utf-8").splitlines() if T in l), None)
    lp = tr.parent / "logs" / f"{T}.log"
    if not r or not lp.exists():
        continue
    log = ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace"))
    reads = re.findall(r"\] \S+ read_file \(([^)]+)\)", log)
    greps = re.findall(r"\] \S+ run_command (grep[^\n]{0,90})", log)
    pp = tr.parent / "patches" / f"{T}.patch"
    files = re.findall(r"^\+\+\+ b/(\S+)", pp.read_text(errors="replace"), re.M) if pp.exists() else []
    out.append((r["resolved"], tr.parent.parent.name, tr.parent.name, reads[:3], greps[:2], files))
for res, n, run, reads, greps, files in sorted(out, key=lambda x: not x[0]):
    print(f"{'SOLVED' if res else 'failed'} {n}/{run}: patch files {files} | first reads {reads} | first greps {greps}")
print("\npatched files, solved:", Counter(f for o in out if o[0] for f in o[5]))
print("patched files, failed:", Counter(f for o in out if not o[0] for f in o[5]))
gold = [json.loads(l) for l in open("colab_fasteval/_smoke_inputs/tasks.jsonl", encoding="utf-8") if T in l][0]
print("gold files:", re.findall(r"^\+\+\+ b/(\S+)", gold["patch"], re.M))
print("problem:", gold["problem_statement"][:400].replace("\n", " "))
