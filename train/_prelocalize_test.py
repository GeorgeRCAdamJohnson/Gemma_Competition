"""Can a MODEL-FREE pre-localizer find the gold file? Two cheap signals:
  (1) stacktrace / explicit paths in the problem statement (regex for fastapi/....py)
  (2) concept match: tokenize problem statement, match against repo module paths + top-level
      class/def names (ranked by overlap). Hand top-5 candidate files.
Scored against the gold file for the 6 held-out tasks. Tells us how much a pre-localizer buys.
"""
import json, re, os, sys, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_prelocalize.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = {json.loads(l)["instance_id"]: json.loads(l) for l in open(TASKS, encoding="utf-8")}
HELD = ["fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"]
R.set_repo("fastapi")
REPO = R.REPO

# build a cheap index: every .py file under fastapi/, plus its class/def names
index = {}  # relpath -> set(names)
for root,_,files in os.walk(REPO / "fastapi"):
    for fn in files:
        if not fn.endswith(".py"): continue
        fp = os.path.join(root, fn)
        rel = os.path.relpath(fp, REPO).replace("\\","/")
        try: src = open(fp, encoding="utf-8", errors="replace").read()
        except Exception: continue
        names = set(re.findall(r'^\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', src, re.M))
        names.add(os.path.splitext(fn)[0])  # module name
        index[rel] = names
p(f"indexed {len(index)} fastapi .py files")

STOP = set("the a an to of and or in on is are be fix bug add change for with this that from import def class self value error field param type".split())

def prelocalize(ps):
    # (1) explicit paths in stacktrace / text
    paths = set(re.findall(r'(fastapi/[\w/]+\.py)', ps))
    # (2) concept tokens -> file score by name overlap + path substring
    toks = set(w.lower() for w in re.findall(r'[A-Za-z_]{3,}', ps)) - STOP
    scores = {}
    for rel, names in index.items():
        s = 0
        base = os.path.splitext(os.path.basename(rel))[0].lower()
        if base in toks: s += 3                      # module name mentioned
        for n in names:
            if n.lower() in toks and len(n) > 3: s += 1
        # concept substring: 'router'->routing, 'sse'/'event'->sse
        for tok in toks:
            if tok in base or base in tok: s += 2
        if s: scores[rel] = s
    ranked = [p for p,_ in sorted(scores.items(), key=lambda kv:-kv[1])]
    # explicit paths first, then ranked concept matches
    out = list(dict.fromkeys(list(paths) + ranked))
    return out[:5], list(paths)

p(f"\n{'task':14} {'gold':34} {'in_top5?':9} {'rank':5} {'via_stacktrace?'}")
hits = 0
for tid in HELD:
    t = recs[tid]
    gold = re.findall(r'\+\+\+ b/(\S+)', t["patch"])
    gold = [g for g in gold if g.endswith(".py") and "test" not in g]
    gf = gold[0] if gold else "(none)"
    top5, paths = prelocalize(t["problem_statement"])
    in5 = gf in top5
    rank = top5.index(gf)+1 if in5 else 0
    via_st = gf in paths
    hits += in5
    p(f"{tid:14} {gf[:34]:34} {str(in5):9} {rank:<5} {via_st}")
    p(f"    top5: {top5}")
p(f"\nPRE-LOCALIZER top-5 recall: {hits}/{len(HELD)}")
OUT.close(); print("done")
