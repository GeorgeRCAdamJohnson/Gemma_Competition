"""Full-corpus data inspection (model-free, all 129 tasks). Answers the strategy-driving questions:
 1. localization signal: % tasks that name gold file / gold symbol / embed a stacktrace path
 2. patch size distribution (lines added/removed, # hunks, # files touched)
 3. file concentration per repo (do bugs cluster?)
 4. per-repo localization difficulty
 5. concept->symbol gap for file-not-named tasks
Writes a readable report. No model, no GGUF, no network.
"""
import json, re, os, collections, statistics as st
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_corpus_inspect.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]
p(f"TOTAL TASKS: {len(recs)}")

def repo_short(t): return t["repo"].split("/")[-1]
def nontest_files(patch):
    fs = re.findall(r'\+\+\+ b/(\S+)', patch)
    return [f for f in fs if f.endswith(".py") and not re.search(r'(^|/)tests?/|test_|_test', f)]
def gold_syms(patch):
    s = set(re.findall(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', patch))
    for m in re.finditer(r'^[+\-]\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', patch, re.M):
        s.add(m.group(1))
    return s
def patch_stats(patch):
    add = sum(1 for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++'))
    rem = sum(1 for l in patch.splitlines() if l.startswith('-') and not l.startswith('---'))
    hunks = patch.count('@@ -')
    return add, rem, hunks

# ---- repo split
byrepo = collections.Counter(repo_short(t) for t in recs)
p("\n=== REPO SPLIT ==="); [p(f"  {r:10} {n}") for r,n in byrepo.most_common()]

# ---- localization signal (per repo + overall)
p("\n=== LOCALIZATION SIGNAL (does problem_statement point to the gold site?) ===")
p(f"{'repo':10} {'n':>4} {'file_named':>11} {'sym_named':>10} {'stacktrace':>11} {'none':>6}")
agg = collections.defaultdict(lambda: collections.Counter())
rows_none = []
for t in recs:
    r = repo_short(t); ps = t["problem_statement"]
    files = nontest_files(t["patch"]); syms = gold_syms(t["patch"])
    gf = files[0] if files else None
    file_named = bool(gf) and (gf in ps or os.path.basename(gf) in ps)
    sym_named = any(s in ps for s in syms if len(s) > 3)
    stack = bool(re.search(r'(?:[\w/]+/)?[\w]+\.py[:"\s]', ps)) and (r in ps or '.py' in ps)
    stack = bool(re.findall(r'\b[\w/]+\.py\b', ps))
    agg[r]['n']+=1
    agg[r]['file']+=file_named; agg[r]['sym']+=sym_named; agg[r]['stack']+=stack
    if not (file_named or sym_named or stack):
        agg[r]['none']+=1; rows_none.append((t['instance_id'], gf, sorted(syms)[:3]))
for r in sorted(agg, key=lambda k:-agg[k]['n']):
    a=agg[r]; n=a['n']
    p(f"{r:10} {n:>4} {a['file']:>11} {a['sym']:>10} {a['stack']:>11} {a['none']:>6}")
tot_n=sum(a['n'] for a in agg.values()); tot_none=sum(a['none'] for a in agg.values())
tot_file=sum(a['file'] for a in agg.values()); tot_sym=sum(a['sym'] for a in agg.values()); tot_st=sum(a['stack'] for a in agg.values())
p(f"{'ALL':10} {tot_n:>4} {tot_file:>11} {tot_sym:>10} {tot_st:>11} {tot_none:>6}")
p(f"  => file named: {100*tot_file/tot_n:.0f}%  sym named: {100*tot_sym/tot_n:.0f}%  stacktrace: {100*tot_st/tot_n:.0f}%  NO signal: {100*tot_none/tot_n:.0f}%")

# ---- patch size distribution
adds=[]; files_touched=[]; hunks_all=[]
for t in recs:
    a,rm,h = patch_stats(t["patch"]); adds.append(a); hunks_all.append(h)
    files_touched.append(len(nontest_files(t["patch"])))
p("\n=== PATCH SIZE (gold fixes) ===")
p(f"  lines added: median {int(st.median(adds))}  mean {st.mean(adds):.1f}  max {max(adds)}  <=5 lines: {100*sum(1 for a in adds if a<=5)/len(adds):.0f}%  <=15: {100*sum(1 for a in adds if a<=15)/len(adds):.0f}%")
p(f"  files touched: median {int(st.median(files_touched))}  1-file: {100*sum(1 for f in files_touched if f==1)/len(files_touched):.0f}%  >=2: {100*sum(1 for f in files_touched if f>=2)/len(files_touched):.0f}%")
p(f"  hunks: median {int(st.median(hunks_all))}  1-hunk: {100*sum(1 for h in hunks_all if h==1)/len(hunks_all):.0f}%")

# ---- file concentration per repo
p("\n=== FILE CONCENTRATION (which files hold the bugs?) ===")
for r in byrepo:
    c = collections.Counter()
    for t in recs:
        if repo_short(t)==r:
            for f in nontest_files(t["patch"]): c[f]+=1
    top = c.most_common(6)
    cover = sum(n for _,n in top)
    p(f"  {r} ({byrepo[r]} tasks, {len(c)} distinct files): top6 cover {cover}/{sum(c.values())} edits")
    for f,n in top: p(f"      {n:>3}  {f}")

# ---- the no-signal tasks (hardest localization)
p(f"\n=== NO-SIGNAL TASKS ({len(rows_none)}) — hardest to localize (concept->symbol needed) ===")
for iid, gf, syms in rows_none[:25]:
    p(f"  {iid:16} -> {gf}   syms={syms}")
OUT.close(); print("done")
