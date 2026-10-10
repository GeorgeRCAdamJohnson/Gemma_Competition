"""Metadata fingerprint scan. For each task, extract META that is NOT the code itself and see if any of
it reveals/correlates with the bug (repo, file, size, difficulty). CLASSIFY each signal as:
  USABLE   = present in what the agent sees at solve time (problem_statement, repo@base_commit)
  LEAKAGE  = metadata that won't exist at eval time or encodes the answer (created_at order, issue #s,
             PR template fields, author) -> keying off these = overfit to public 129, collapse on private.
We MEASURE correlations but LABEL leakage so we never 'key off' it. (rules 1, 8, 9)
"""
import json, re, os, collections, statistics as st
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_metadata_scan.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]
def repo_short(t): return t["repo"].split("/")[-1]
def gold_file(t):
    fs = [f for f in re.findall(r'\+\+\+ b/(\S+)', t["patch"]) if f.endswith(".py") and not re.search(r'(^|/)tests?/|test_|_test', f)]
    return fs[0] if fs else None

p("=== FIELD INVENTORY (what metadata exists) ===")
p("fields: " + ", ".join(recs[0].keys()))

# --- created_at: is there an ordering/temporal fingerprint?
p("\n=== created_at (LEAKAGE RISK: temporal ordering) ===")
dates = [(t["instance_id"], t.get("created_at","")) for t in recs]
present = [d for _,d in dates if d]
p(f"  present on {len(present)}/{len(recs)} tasks. sample: {dates[:3]}")
yrs = collections.Counter(d[:4] for _,d in dates if d)
p(f"  year distribution: {dict(yrs)}")

# --- issue/PR number references in problem statement (LEAKAGE: points to external content)
p("\n=== issue/PR number refs in problem_statement (LEAKAGE: #NNNN, 'defect #', PR #) ===")
nref=0
for t in recs:
    if re.search(r'#\d{3,}|issues?/\d+|pull/\d+|defect #?\d+', t["problem_statement"]): nref+=1
p(f"  {nref}/{len(recs)} tasks reference an issue/PR number (external content we DON'T have).")

# --- problem statement structure fingerprints (PR template, emoji, length)
p("\n=== problem_statement STRUCTURE ===")
emoji=0; template=0; lens=[]
emoji_pat = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF]')
for t in recs:
    ps=t["problem_statement"]; lens.append(len(ps))
    if emoji_pat.search(ps[:50]): emoji+=1
    if '## Pull Request' in ps or '## Checklist' in ps or 'AI Disclaimer' in ps: template+=1
p(f"  leading-emoji titles: {emoji}/{len(recs)}  ({100*emoji/len(recs):.0f}%)")
p(f"  GitHub PR-template boilerplate present: {template}/{len(recs)}  ({100*template/len(recs):.0f}%)")
p(f"  length: median {int(st.median(lens))}  min {min(lens)}  max {max(lens)}  <100 chars: {sum(1 for l in lens if l<100)}")

# --- emoji-prefix -> bug-type fingerprint? (USABLE: it's in the problem statement)
p("\n=== EMOJI PREFIX -> signal? (USABLE: in problem_statement) ===")
emoji_map = collections.Counter()
for t in recs:
    m = emoji_pat.findall(t["problem_statement"][:10])
    key = m[0] if m else "(none)"
    emoji_map[key]+=1
for e,n in emoji_map.most_common(12):
    p(f"  {repr(e):12} {n}")

# --- title first-line verb/keyword -> repo or file correlation? (USABLE)
p("\n=== TITLE KEYWORD -> gold-file hotspot? (USABLE signal test) ===")
# does the FIRST LINE of the PS contain words that map to the gold file's module?
hit_mod=0; checked=0
for t in recs:
    gf = gold_file(t)
    if not gf: continue
    checked+=1
    mod = os.path.splitext(os.path.basename(gf))[0].lower()
    first = t["problem_statement"].split("\n")[0].lower()
    if mod in first and len(mod)>3: hit_mod+=1
p(f"  module-name appears in PS first line: {hit_mod}/{checked} ({100*hit_mod/max(checked,1):.0f}%)")

# --- base_commit uniqueness (every task a different commit? shared?)
p("\n=== base_commit (USABLE: it's the repo state) ===")
bc = collections.Counter(t["base_commit"] for t in recs)
p(f"  distinct base_commits: {len(bc)} across {len(recs)} tasks. shared commits: {sum(1 for c,n in bc.items() if n>1)}")

# --- hints_text ever populated?
p("\n=== hints_text ===")
hc = sum(1 for t in recs if (t.get('hints_text') or '').strip())
p(f"  non-empty hints_text: {hc}/{len(recs)}")
OUT.close(); print("done")
