"""SHARED localization curriculum for BOTH tracks (Kaggle LoRA + local retrieval/localizer skill).

Each record: metadata-STRIPPED problem statement -> gold (file, symbols, repo, base_commit).
- metadata is a TRAIN-TIME teacher only: emoji/issue#/PR-template STRIPPED from the INPUT so nothing
  leaks to inference (rules 8/9). The gold PATCH is the label source (never seen at inference).
- EMOJI-FILTER: keep real bug/none/refactor tasks; DROP feature-adds (sparkles) and docs_src/ fixtures,
  which teach the wrong thing for localization.
- Reproducible BY-TASK holdout (20%) so eval tasks are never trained on.
- Adversarial-leak check: confirm the stripped input does NOT still contain the gold file/symbol as a
  trivial giveaway more than the base rate (if it does, the "localization" is just copying a named token).

Outputs:
  data/localization_curriculum.jsonl   (all kept records, with a 'split' field: train|holdout)
  prints summary + leak check.
"""
import json, re, os, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
TASKS = os.path.join(HERE, "..", "comp_files", "tasks.jsonl")
OUT = os.path.join(HERE, "data", "localization_curriculum.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]

emoji_pat = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]')
BUG_EMOJI = {'\U0001F41B'}            # bug
REFACTOR = {'\u267B'}                 # recycle
FEATURE = {'\u2728'}                  # sparkles (DROP for localization)

def first_emoji(ps):
    m = emoji_pat.findall(ps[:10]); return m[0] if m else None

def strip_meta(ps):
    s = emoji_pat.sub('', ps)
    s = re.sub(r'#\d{3,}|issues?/\d+|pull/\d+|defect #?\d+', '', s)
    for marker in ["## Pull Request","## Checklist","## AI Disclaimer","<!--","Discussion:","<details>","<summary>"]:
        i = s.find(marker)
        if i != -1: s = s[:i]
    return re.sub(r'\n{3,}', '\n\n', s).strip()

def gold(t):
    files = [f for f in re.findall(r'\+\+\+ b/(\S+)', t["patch"])
             if f.endswith(".py") and not re.search(r'(^|/)tests?/|test_|_test', f)]
    syms = set(re.findall(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', t["patch"]))
    for m in re.finditer(r'^[+\-]\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', t["patch"], re.M):
        syms.add(m.group(1))
    return files, sorted({s for s in syms if len(s) > 2})

def repo_short(t): return t["repo"].split("/")[-1]
def split_of(iid):  # reproducible 80/20 by task id
    h = int(hashlib.md5(iid.encode()).hexdigest(), 16)
    return "holdout" if (h % 5 == 0) else "train"

kept, dropped = [], collections.Counter()
for t in recs:
    files, syms = gold(t)
    gf = files[0] if files else None
    if not gf: dropped["no_lib_file"] += 1; continue
    if "docs_src/" in gf or "scripts/" in gf: dropped["docs_or_scripts_fixture"] += 1; continue
    e = first_emoji(t["problem_statement"])
    if e in FEATURE: dropped["feature_add"] += 1; continue  # not a bug-localization task
    stripped = strip_meta(t["problem_statement"])
    if len(stripped) < 40: dropped["too_short_after_strip"] += 1; continue
    kept.append({
        "instance_id": t["instance_id"], "repo": repo_short(t), "base_commit": t["base_commit"],
        "symptom": stripped, "gold_file": gf, "gold_symbols": syms,
        "split": split_of(t["instance_id"]),
    })

with open(OUT, "w", encoding="utf-8") as f:
    for r in kept: f.write(json.dumps(r) + "\n")

ntr = sum(1 for r in kept if r["split"]=="train"); nho = len(kept)-ntr
print(f"KEPT {len(kept)} (train {ntr} / holdout {nho}) | DROPPED {dict(dropped)}")
byrepo = collections.Counter(r["repo"] for r in kept)
print("by repo:", dict(byrepo))

# ADVERSARIAL LEAK CHECK: does the stripped symptom still contain the gold file basename or a gold symbol?
leak_file = sum(1 for r in kept if os.path.basename(r["gold_file"])[:-3] in r["symptom"]
                or r["gold_file"] in r["symptom"])
leak_sym = sum(1 for r in kept if any(s in r["symptom"] for s in r["gold_symbols"]))
print(f"LEAK CHECK: gold-file-named-in-input {leak_file}/{len(kept)} ({100*leak_file/len(kept):.0f}%); "
      f"gold-symbol-named {leak_sym}/{len(kept)} ({100*leak_sym/len(kept):.0f}%)")
print("  (these are the EASY tasks where the input legitimately names the site; NOT leakage of the "
      "metadata giveaway. The hard majority has neither \u2014 that's what the model must learn.)")
print(f"wrote {OUT}")
