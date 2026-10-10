"""Verify the audit's headline: does TF-IDF over def names+source localize the gold def far better than
the graph/embedding tools? Build a TF-IDF index of the per-task graph nodes (name + source text), query
with the problem statement, measure top-k recall of the GOLD symbol(s)/file.

Model-free, CPU. For each task that (a) has a local graph and (b) edits a non-test def:
  gold symbols = defs/classes the patch touches; gold file = patched library file.
  TF-IDF: fit over nodes (id tokens + source tokens), query = problem_statement, rank nodes.
  record: gold symbol in top-1/5/10? gold FILE in top-10 (any node from that file)?
Compare against a 'graph-tool' baseline = exact-id lookup success (can the agent even query it?).
"""
import json, re, os, glob, collections, math
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_tfidf_localize.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
GRAPHS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\graphs"
recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]

def repo_short(t): return t["repo"].split("/")[-1]
def gold(t):
    files = [f for f in re.findall(r'\+\+\+ b/(\S+)', t["patch"]) if f.endswith(".py") and not re.search(r'(^|/)tests?/|test_|_test', f)]
    syms = set(re.findall(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', t["patch"]))
    for m in re.finditer(r'^[+\-]\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', t["patch"], re.M):
        syms.add(m.group(1))
    return files, {s for s in syms if len(s) > 2}

_tok = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
def toks(s): return _tok.findall(s.lower())

def graph_path(repo, commit):
    fp = os.path.join(GRAPHS, f"{repo}_{commit}.json")
    return fp if os.path.exists(fp) else None

def tfidf_rank(nodes, query):
    # build df
    docs = []
    for n in nodes:
        name = (n.get("id") or n.get("name") or "")
        # split dotted name into parts + camel/snake tokens, plus source tokens
        name_toks = toks(name.replace(".", " ")) + re.findall(r"[A-Z][a-z]+|[a-z]+|[0-9]+", name)
        src_toks = toks(n.get("text") or "")
        docs.append(collections.Counter(name_toks * 3 + src_toks))  # weight NAME tokens 3x
    N = len(docs)
    df = collections.Counter()
    for d in docs:
        for term in d: df[term] += 1
    idf = {term: math.log(1 + N / (1 + c)) for term, c in df.items()}
    qv = collections.Counter(toks(query))
    scores = []
    for i, d in enumerate(docs):
        s = 0.0
        for term, qf in qv.items():
            if term in d:
                s += qf * d[term] * idf.get(term, 0) ** 2
        scores.append((s, i))
    scores.sort(key=lambda x: -x[0])
    return [i for _, i in scores]

def node_file(n):
    # dotted id -> file path heuristic: fastapi.sse.X -> fastapi/sse.py
    nid = n.get("id") or n.get("name") or ""
    parts = nid.split(".")
    # drop trailing symbol(s): keep module path. Heuristic: module is parts up to last lowercase_file-ish
    return nid  # we match on symbol presence instead; file via gold symbol membership

rows = []
for t in recs:
    gp = graph_path(repo_short(t), t["base_commit"])
    files, syms = gold(t)
    if not gp or not files or not syms:
        continue
    g = json.load(open(gp, encoding="utf-8"))
    nodes = g["nodes"]
    ranked = tfidf_rank(nodes, t["problem_statement"])
    # gold symbol hit: a ranked node whose id tail is a gold symbol
    def is_gold(idx):
        nid = (nodes[idx].get("id") or nodes[idx].get("name") or "")
        tail = nid.split(".")[-1]
        return tail in syms
    top1 = any(is_gold(i) for i in ranked[:1])
    top5 = any(is_gold(i) for i in ranked[:5])
    top10 = any(is_gold(i) for i in ranked[:10])
    rows.append((t["instance_id"], repo_short(t), top1, top5, top10))

n = len(rows)
p(f"tasks scored (have graph + non-test def gold): {n}")
for k, idx in (("top1",2),("top5",3),("top10",4)):
    hits = sum(r[idx] for r in rows)
    p(f"  TF-IDF gold-symbol {k}: {hits}/{n} = {100*hits/n:.0f}%")
p("\nper-repo top10:")
byrepo = collections.defaultdict(lambda: [0,0])
for r in rows:
    byrepo[r[1]][0]+=1; byrepo[r[1]][1]+=r[4]
for repo,(tot,h) in sorted(byrepo.items()):
    p(f"  {repo:10} {h}/{tot} = {100*h/tot:.0f}%")
# held-out 6
held={"fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"}
p("\nheld-out 6:")
for r in rows:
    if r[0] in held: p(f"  {r[0]:16} top1={r[2]} top5={r[3]} top10={r[4]}")
OUT.close(); print("done")
