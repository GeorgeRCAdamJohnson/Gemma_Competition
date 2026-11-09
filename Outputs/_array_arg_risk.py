"""Exposure to the vLLM 0.19.1 gemma4 tool-parser infinite loop (forum 753973): the trigger is an ARRAY tool
argument holding a bare (non-<|"|>) element that contains ']'. Which of our tools take arrays, and how often do our
agents call them (E4B pack logs, 31B logs)?"""
import glob
import re
import tarfile
from collections import Counter

A = re.compile(r"\x1b\[[0-9;]*m")
TOOLS = ("get_code_subgraph", "get_code_neighbors", "search_similar_code", "run_skill_script")
cnt = Counter(); arr = Counter(); runs = Counter(); ex = {}


def scan(name, text, src):
    runs[src] += 1
    for t in TOOLS:
        n = len(re.findall(r"\b%s\b" % t, text))
        if n:
            cnt[(src, t)] += n
    for m in re.finditer(r"(get_code_subgraph|run_skill_script)[^\n]{0,200}", text):
        s = m.group(0)
        if "[" in s and ("positional_args" in s or "node" in s or "ids" in s):
            arr[(src, m.group(1))] += 1
            ex.setdefault((src, m.group(1)), s[:180])


for f in glob.glob("Outputs/e4b_pack*_val/results/node*/run_*/logs/*.log"):
    scan(f, A.sub("", open(f, encoding="utf-8", errors="replace").read()), "E4B pack")
for f in glob.glob("Outputs/e4b_cap_ab/results/node*/run_1/logs/*.log"):
    scan(f, A.sub("", open(f, encoding="utf-8", errors="replace").read()), "E4B ca5")
for f in glob.glob("Outputs/v7_31b_full129/results/logs/*.log"):
    scan(f, A.sub("", open(f, encoding="utf-8", errors="replace").read()), "31B v7")
for tgz in ("Outputs/ca5_31b_presubmit_85/results.tar.gz",):
    with tarfile.open(tgz) as tf:
        for m in tf.getmembers():
            if m.name.endswith(".log") and "/logs/" in m.name:
                scan(m.name, A.sub("", tf.extractfile(m).read().decode("utf-8", "replace")), "31B pre85")
print("runs scanned:", dict(runs))
print("tool mentions:", {f"{k[0]}|{k[1]}": v for k, v in sorted(cnt.items())})
print("array-arg calls (bracket in args):", {f"{k[0]}|{k[1]}": v for k, v in arr.items()})
for k, v in ex.items():
    print("  e.g.", k, "::", v)
