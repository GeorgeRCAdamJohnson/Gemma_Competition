"""TRACK B: local retrieval-index localizer (the LoRA's localization JOB as exact lookup, 16GB, no gate).

Given a repo checked out at base_commit + a (metadata-stripped) symptom, rank candidate FILES by TF-IDF
similarity of the symptom against each file's indexable text (path tokens + def/class names [weighted] +
docstrings + identifiers). Returns ranked file list. Shippable as an ADK skill .py in the submission.

This file is BOTH the library (build_index/rank) and a self-test harness that measures top-k file recall
on the curriculum holdout, by indexing the REAL repo tree at each task's base_commit (faithful to what
the agent searches).
"""
import json, re, os, math, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPOS = os.path.join(HERE, "..", "local_eval", "repos")
CURR = os.path.join(HERE, "data", "localization_curriculum.jsonl")

_tok = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_def = re.compile(r"^\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)", re.M)
_doc = re.compile(r'"""(.*?)"""', re.S)
STOP = set("the and for that this with from not are was will can has have you your def class self "
           "import return none true false value error type test def__ init main app get post".split())

def _tokens(s):
    return [w for w in _tok.findall(s.lower()) if w not in STOP and len(w) > 2]

def index_repo(repo_dir):
    """Index every .py file (excluding tests) -> {relpath: Counter(term->weight)}. def/class names x3,
    path tokens x2, docstrings + identifiers x1."""
    docs = {}
    for root, _, files in os.walk(repo_dir):
        if os.sep + ".git" in root: continue
        for fn in files:
            if not fn.endswith(".py"): continue
            rel = os.path.relpath(os.path.join(root, fn), repo_dir).replace("\\", "/")
            if re.search(r'(^|/)tests?/|test_|_test', rel): continue
            try: src = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
            except Exception: continue
            c = collections.Counter()
            for name in _def.findall(src):
                for t in _tokens(name) + re.findall(r"[a-z]+|[A-Z][a-z]*", name):
                    c[t.lower()] += 3
            for p in _tokens(rel.replace("/", " ").replace(".py", "")):
                c[p] += 2
            for d in _doc.findall(src):
                for t in _tokens(d): c[t] += 1
            for t in _tokens(src): c[t] += 1
            if c: docs[rel] = c
    return docs

def _idf(docs):
    N = len(docs); df = collections.Counter()
    for c in docs.values():
        for term in c: df[term] += 1
    return {t: math.log(1 + N / (1 + d)) for t, d in df.items()}

def rank_files(docs, idf, symptom, k=10):
    q = collections.Counter(_tokens(symptom))
    scored = []
    for rel, c in docs.items():
        s = 0.0
        for term, qf in q.items():
            if term in c: s += qf * (1 + math.log(c[term])) * idf.get(term, 0) ** 2
        if s: scored.append((s, rel))
    scored.sort(key=lambda x: -x[0])
    return [rel for _, rel in scored[:k]]

def _checkout(repo_dir, commit):
    subprocess.run(["git", "reset", "--hard", commit], cwd=repo_dir, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    subprocess.run(["git", "clean", "-fd"], cwd=repo_dir, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")

def _norm_gold(gf):
    # curriculum gold_file is repo-relative like 'fastapi/sse.py' or 'src/requests/utils.py'
    return gf.replace("\\", "/")

def evaluate(split="holdout"):
    rows = [json.loads(l) for l in open(CURR, encoding="utf-8")]
    rows = [r for r in rows if r["split"] == split]
    by_repo = collections.defaultdict(list)
    for r in rows: by_repo[r["repo"]].append(r)
    hits = {1: 0, 3: 0, 5: 0, 10: 0}; n = 0; detail = []
    for repo, rs in by_repo.items():
        repo_dir = os.path.join(REPOS, repo)
        if not os.path.isdir(repo_dir):
            continue
        # group by commit to avoid re-checkout per task
        by_commit = collections.defaultdict(list)
        for r in rs: by_commit[r["base_commit"]].append(r)
        for commit, crs in by_commit.items():
            _checkout(repo_dir, commit)
            docs = index_repo(repo_dir); idf = _idf(docs)
            for r in crs:
                ranked = rank_files(docs, idf, r["symptom"], k=10)
                gold = _norm_gold(r["gold_file"])
                pos = next((i for i, f in enumerate(ranked) if f == gold or f.endswith("/" + gold) or gold.endswith("/" + f)), -1)
                n += 1
                for kk in hits:
                    if 0 <= pos < kk: hits[kk] += 1
                detail.append((r["instance_id"], pos + 1 if pos >= 0 else 0, gold))
    return n, hits, detail

if __name__ == "__main__":
    import sys
    out = open(os.path.join(HERE, "_localizer_eval.log"), "w", encoding="utf-8")
    def p(*a): print(*a, file=out, flush=True); print(*a)
    n, hits, detail = evaluate("holdout")
    p(f"TRACK-B retrieval localizer | holdout n={n}")
    for k in (1, 3, 5, 10):
        p(f"  top-{k} file recall: {hits[k]}/{n} = {100*hits[k]/max(n,1):.0f}%")
    p("\nper-task (rank of gold file, 0=miss):")
    for iid, rank, gold in sorted(detail, key=lambda x: x[1] or 99):
        p(f"  {iid:16} rank={rank:<3} {gold}")
    out.close()
