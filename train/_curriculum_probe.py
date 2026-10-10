"""Can we mine a clean (metadata-STRIPPED symptom -> gold location) curriculum from the 129 patches?
The gold patch is a TRAIN-TIME-ONLY teacher. We build: input = problem_statement with metadata giveaways
STRIPPED (emoji, issue #s, PR-template boilerplate), target = gold (file, symbol, line). Count how many
clean labels we can produce, and show a few, so we know the curriculum is viable before training on it.
This is label-generation from metadata, NOT an inference feature (user's distinction).
"""
import json, re, os, collections
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_curriculum_probe.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)
TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
recs = [json.loads(l) for l in open(TASKS, encoding="utf-8")]

emoji_pat = re.compile(r'[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF\uFE0F]')
def strip_meta(ps):
    s = emoji_pat.sub('', ps)                                   # emoji
    s = re.sub(r'#\d{3,}|issues?/\d+|pull/\d+|defect #?\d+', '', s)  # issue/PR numbers
    # strip GitHub PR template sections
    for marker in ["## Pull Request","## Checklist","## AI Disclaimer","<!--","Discussion:","<details>"]:
        i = s.find(marker)
        if i != -1: s = s[:i]
    return s.strip()

def gold_loc(t):
    files = [f for f in re.findall(r'\+\+\+ b/(\S+)', t["patch"]) if f.endswith(".py") and not re.search(r'(^|/)tests?/|test_|_test', f)]
    hunks = re.findall(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@\s*(?:async def|def|class)?\s*([A-Za-z_]\w*)?', t["patch"])
    syms = set(re.findall(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', t["patch"]))
    return (files[0] if files else None), sorted(syms), hunks[:2]

clean=0; usable=0; src_only=0
samples=[]
for t in recs:
    gf, syms, hunks = gold_loc(t)
    stripped = strip_meta(t["problem_statement"])
    # "clean label" = we have a gold file AND a non-trivial stripped statement to learn from
    if gf and len(stripped) >= 40:
        clean += 1
        if "docs_src/" in gf or "scripts/" in gf: src_only += 1   # fixture/non-library edits
        else: usable += 1
        if len(samples) < 6:
            samples.append((t["instance_id"], gf, syms[:3], hunks, stripped[:200]))

p(f"TOTAL {len(recs)} | clean (file+>=40char symptom): {clean} | library-code targets: {usable} | docs/scripts fixtures: {src_only}")
p("\n=== SAMPLE (metadata-stripped symptom -> gold location) ===")
for iid, gf, syms, hunks, strip in samples:
    p(f"\n[{iid}] -> FILE {gf}  SYMS {syms}  HUNKS {hunks}")
    p(f"  STRIPPED SYMPTOM: {strip!r}")
OUT.close(); print("done")
