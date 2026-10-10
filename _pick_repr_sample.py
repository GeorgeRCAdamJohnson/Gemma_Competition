"""Pick a representative SMALL_SINGLE_FILE, repo-stratified eval sample (deterministic).
Anchors: keep rich_4077/rich_4079/rich_4076 (prior-run bridge). Fill to ~10 with fresh small-single-file
tasks across rich/fastapi/requests. Prints a ready-to-paste Python list for v9 cell 4."""
import json, re, random
from collections import defaultdict

TASKS = "Gemma/comp_files/tasks.jsonl"
rows = [json.loads(l) for l in open(TASKS, encoding="utf-8") if l.strip()]
by_id = {r["instance_id"]: r for r in rows}

def cls(rec):
    patch = rec["patch"]
    files = re.findall(r'^\+\+\+ b/(.+)$', patch, re.M)
    adds = len(re.findall(r'^\+(?!\+\+)', patch, re.M))
    creates = '\n@@ -0,0 +1,' in patch
    nonfiles = sorted(set(f for f in files if not f.startswith("tests/") and "test_" not in f))
    if creates: return "NEW_FILE_FEATURE", nonfiles, adds
    if len(nonfiles) == 0: return "DOCS_OR_TEST_ONLY", nonfiles, adds
    if len(nonfiles) == 1 and adds <= 25: return "SMALL_SINGLE_FILE", nonfiles, adds
    if len(nonfiles) == 1: return "LARGE_SINGLE_FILE", nonfiles, adds
    return "MULTI_FILE", nonfiles, adds

small = defaultdict(list)   # repo -> [(id, nfile, adds)]
for r in rows:
    c, nf, adds = cls(r)
    if c == "SMALL_SINGLE_FILE":
        small[r["repo"].split("/")[-1]].append((r["instance_id"], nf[0], adds))

ANCHORS = ["rich_4077", "rich_4079", "rich_4076"]   # prior-run bridge (all small-single-file)
# target composition: rich 4 (incl 3 anchors +1), fastapi 4, requests 2  = 10, repo-stratified
rng = random.Random(42)
chosen = list(ANCHORS)

def fill(repo, n, exclude):
    pool = [t for t in small[repo] if t[0] not in exclude]
    rng.shuffle(pool)
    return [t[0] for t in pool[:n]]

chosen += fill("rich", 1, set(chosen))        # +1 fresh rich
chosen += fill("fastapi", 4, set(chosen))     # 4 fastapi
chosen += fill("requests", 2, set(chosen))    # 2 requests

print("REPRESENTATIVE SAMPLE (deterministic seed=42), all SMALL_SINGLE_FILE:")
for iid in chosen:
    r = by_id[iid]; c, nf, adds = cls(r)
    ps = r["problem_statement"].strip().replace("\n", " ")[:60]
    print(f"   {iid:14s} {r['repo'].split('/')[-1]:9s} file={nf[0]:30s} adds={adds:3d}  '{ps}'")

print("\nREPR_SAMPLE_IDS = [")
for iid in chosen:
    print(f'    "{iid}",')
print("]")
print(f"\ncount={len(chosen)}  by repo:", {k: sum(1 for i in chosen if by_id[i]['repo'].endswith(k)) for k in ['rich','fastapi','requests']})
