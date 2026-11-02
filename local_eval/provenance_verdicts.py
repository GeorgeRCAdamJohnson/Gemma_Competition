"""Provenance-aware failure classifier.

The naive classifier says "NameError / collection error -> environment".  That is
wrong when the traceback points at code the AGENT wrote.  This version locates the
erroring file(s) in the traceback and checks them against the agent's patch:
  - error inside a file the agent edited  -> AGENT (its own patch broke collection)
  - error elsewhere, missing module/wheel -> ENV (sandbox defect; failure unverifiable)
  - assertion failure                     -> REAL
"""
import io
import json
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUN = os.path.join(ROOT, "kaggle_pkg", "out_e4b")

TB_LINE = re.compile(r"^([A-Za-z0-9_./\\-]+\.py):(\d+): in ")
SELF_LINE = re.compile(r"^([A-Za-z0-9_./\\-]+\.py):(\d+):\s")
ASSERT = re.compile(r"AssertionError|^E\s+assert |FAILED ")
ENVISH = re.compile(
    r"ModuleNotFoundError|No module named|ImportError|ERROR collecting|"
    r"Interrupted: \d+ error|fixture '.*' not found|No matching distribution|"
    r"Could not find a version|unrecognized arguments"
)


def patch_files(path):
    if not os.path.exists(path):
        return set()
    out = set()
    for line in io.open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            out.add(m.group(1).strip().replace("\\", "/"))
    return out


def tb_files(text):
    """Files appearing in the traceback section, with line numbers."""
    out = []
    for line in text.splitlines():
        m = TB_LINE.match(line) or SELF_LINE.match(line.strip())
        if m:
            p = m.group(1).replace("\\", "/")
            if p.startswith("./"):
                p = p[2:]
            out.append((p, int(m.group(2))))
    return out


def main():
    pdir = os.path.join(RUN, "results", "patches")
    tdir = os.path.join(RUN, "results", "test_outputs")
    rows = []
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".log"):
            continue
        tid = fn[:-4]
        text = io.open(os.path.join(tdir, fn), encoding="utf-8", errors="replace").read()
        ap = os.path.join(pdir, tid + ".patch")
        touched = patch_files(ap)
        where = tb_files(text)
        in_patch = [(p, n) for (p, n) in where if p in touched]
        envish = bool(ENVISH.search(text))
        real = bool(ASSERT.search(text))

        if in_patch:
            verdict = "AGENT"          # agent's own edit is in the traceback
        elif real and not envish:
            verdict = "REAL"
        elif envish and not real:
            verdict = "ENV"
        elif envish and real:
            verdict = "MIXED"
        else:
            verdict = "UNKNOWN"
        rows.append({"task": tid, "verdict": verdict,
                     "in_patch": [f"{p}:{n}" for p, n in in_patch][:4],
                     "touched": sorted(touched), "repo": tid.rsplit("_", 1)[0]})

    print("=== provenance-aware verdicts ===")
    for k, n in Counter(r["verdict"] for r in rows).most_common():
        print(f"  {k:<8} {n:>4}")
    print()
    byrepo = defaultdict(Counter)
    for r in rows:
        byrepo[r["repo"]][r["verdict"]] += 1
    print("=== by repo ===")
    for repo in sorted(byrepo):
        c = byrepo[repo]
        print(f"  {repo:<9} total={sum(c.values()):<4} " +
              " ".join(f"{k}={c[k]}" for k in ("AGENT", "REAL", "ENV", "MIXED", "UNKNOWN")))
    print()
    agent = [r for r in rows if r["verdict"] == "AGENT"]
    print(f"=== {len(agent)} tasks where the AGENT'S OWN edit appears in the traceback ===")
    for r in agent:
        print(f"  {r['task']:<18} {', '.join(r['in_patch'])}")
    print()
    env = [r for r in rows if r["verdict"] == "ENV"]
    print(f"=== {len(env)} genuine ENV failures (agent did not touch the erroring file) ===")
    for r in env:
        print(f"  {r['task']:<18} touched={len(r['touched'])}")
    io.open(os.path.join(HERE, "provenance_verdicts.json"), "w",
            encoding="utf-8").write(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
