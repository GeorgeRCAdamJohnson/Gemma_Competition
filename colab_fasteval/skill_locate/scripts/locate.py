"""locate: rank the repo files that DEFINE what the problem talks about, so the edit lands at the definition site
(not a caller, sibling, test, doc or packaging file). Pure stdlib + git; runs inside the task sandbox (cwd = repo).

usage (via run_skill_script):  args = {"q": "<identifiers, class/function names, error text, file names from the problem>"}
also: python3 locate.py --q "..."   or   python3 locate.py "token1 token2 ..."
Output: the top candidate files with the defining lines, best first.
"""
import math
import os
import re
import subprocess
import sys
from collections import defaultdict

STOP = set("""a an and are as at be been but by can could do does for from has have how if in into is it its may must not
of on or should so than that the their then there these this to use used uses using was were when where which while
will with would you your fix bug issue error problem should expected actual behavior behaviour example docs doc
true false none self cls return value values default type types file files function functions method class code
test tests support add added remove make new old work works working case same different also only just like""".split())
LOW = re.compile(r"(^|/)(docs?|tests?|testing|examples?|benchmarks?|scripts?)/|(^|/)(test_[^/]*|[^/]*_test\.py|conftest\.py)$|"
                 r"\.(md|rst|txt|toml|cfg|ini|yaml|yml|json|lock|cff)$|(^|/)(LICENSE|README|CHANGELOG|CONTRIBUTING|setup\.py)",
                 re.I)


def repo_root():
    for c in [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace", os.getcwd()]:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


def query_text():
    a = sys.argv[1:]
    if "--q" in a:
        i = a.index("--q")
        return " ".join(a[i + 1:])
    return " ".join(x for x in a if not x.startswith("--"))


def clean(q):
    """v3: drop PR-template boilerplate that pulls the ranking toward unrelated files."""
    q = re.sub(r"<!--.*?-->", " ", q, flags=re.S)                         # HTML comment templates
    q = re.sub(r"(?m)^\s*[-*]\s*\[[ xX]\].*$", " ", q)                     # checklist lines
    q = re.sub(r"(?mi)^\s*#+\s*(type of changes|checklist|description)\s*$", " ", q)
    q = re.sub(r"(?i)please describe your changes here.*?possible\.", " ", q, flags=re.S)
    q = re.sub(r"https?://\S+", " ", q)                                    # bare issue / PR links
    return q


def tokens(q):
    toks = set()
    for m in re.finditer(r"`([^`]{2,80})`", q):                      # backticked spans
        toks.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", m.group(1)))
    toks.update(re.findall(r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b", q))   # CamelCase
    toks.update(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", q))         # snake_case
    toks.update(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\()", q))            # name(
    for m in re.finditer(r"\b[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+\b", q):      # dotted a.b.c -> parts
        toks.update(p for p in m.group(0).split(".") if len(p) > 2)
    toks.update(re.findall(r"\b[A-Za-z_]\w{3,}\b", q))                       # plain words (low weight below)
    return {t for t in toks if t.lower() not in STOP and not t.isdigit()}


def files_by_ext(root):
    try:
        r = subprocess.run("git ls-files", shell=True, cwd=root, capture_output=True, text=True, timeout=60)
        fs = [f for f in r.stdout.splitlines() if f.endswith(".py")]
    except Exception:
        fs = []
    if not fs:  # no git index (or git missing): walk the tree
        for d, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if not x.startswith(".") and x not in ("node_modules", "__pycache__", "venv", ".venv")]
            fs += [os.path.relpath(os.path.join(d, x), root) for x in fn if x.endswith(".py")]
    return fs


def main():
    root = repo_root()
    q = query_text()
    if not q.strip():
        print("locate: pass the problem's identifiers / error text, e.g. args {\"q\": \"FileProxy write flush\"}")
        return
    q = clean(q)
    title = next((ln for ln in q.splitlines() if ln.strip()), "")
    toks = tokens(q)
    title_toks = tokens(title)
    strong = {t for t in toks if ("_" in t or re.search(r"[a-z][A-Z]", t) or re.search(rf"`[^`]*\b{re.escape(t)}\b", q))}
    pyfiles = files_by_ext(root)
    texts = {}
    for f in pyfiles:
        try:
            texts[f] = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
        except OSError:
            pass
    n = max(1, len(texts))
    # v2 (2026-11-12): RARITY weighting. v1 ranked hub files (applications.py, routing.py, console.py) first because
    # they mention everything -- the same trap the failing agent runs fall into. A token in 2 files now counts far more
    # than one in 40, for definitions and mentions alike.
    df = {t: sum(1 for x in texts.values() if t in x) for t in toks}
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 0.1 for t in toks}
    key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())   # FileProxy == file_proxy == _file_proxy
    score, defs, uses = defaultdict(float), defaultdict(list), defaultdict(int)
    def_re = {t: re.compile(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(t)}\b|^\s*{re.escape(t)}\s*[:=]") for t in toks}
    for f, text in texts.items():
        low = 0.25 if LOW.search(f) else 1.0
        stem = key(os.path.splitext(os.path.basename(f))[0])
        parts = set(re.split(r"[_\-]+", os.path.splitext(os.path.basename(f))[0].lower())) - {""}
        for t in toks:
            stem_hit = key(t) == stem and len(stem) > 3
            part_hit = (not stem_hit) and len(t) > 3 and t.lower() in parts          # "proxy" -> file_proxy.py
            tw = 3.0 if t in title_toks else 1.0                                     # v3: the title carries the signal
            if stem_hit or part_hit:                                                 # file named after the concept:
                score[f] += (10 if stem_hit else 5) * tw * low                       # strong evidence, NOT idf-scaled
            if t not in text:
                continue
            w = (3.0 if t in strong else 1.0) * idf[t] * tw
            n_use = text.count(t)
            hits = [i + 1 for i, ln in enumerate(text.splitlines()) if def_re[t].search(ln)]
            if hits:
                score[f] += 6 * w * low
                defs[f] += [(t, h) for h in hits[:2]]
            if n_use:
                score[f] += min(n_use, 3) * 0.2 * w * low
                uses[f] += n_use
    ranked = sorted(score, key=lambda f: -score[f])[:5]
    if not ranked:
        print("locate: no Python file mentions any of", sorted(toks)[:12])
        return
    print("CANDIDATE FILES (best first). Open #1 with sed -n around the DEFINITION line and edit THERE:")
    for i, f in enumerate(ranked, 1):
        d = ", ".join(f"{t} @L{h}" for t, h in defs[f][:4]) or "no definition, uses only"
        print(f"  {i}. {f}   score {score[f]:.1f} | defines: {d} | mentions {uses[f]}")
    print("Edit the file that DEFINES the behaviour (#1 unless the problem names another file). "
          "Do not edit tests, docs, README, LICENSE or packaging files.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never break the agent loop
        print(f"locate: error {type(e).__name__}: {e}")
