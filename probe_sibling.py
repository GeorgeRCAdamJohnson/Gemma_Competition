"""
PRE-REGISTERED PROBE: is the gold fix "conform to an existing sibling pattern"?

Hypothesis: SWE fixes are often "make the buggy code look like code that already
exists elsewhere in the repo" rather than novel synthesis. If true, a sibling-copy
agent sidesteps the synthesis bottleneck (Coherence Collapse, arXiv 2603.24631).

Metric (model-free, over all 129 gold patches in tasks.jsonl):
  For each patch, extract ADDED lines (the fix). For each non-trivial added line,
  ask: does a near-identical line ALREADY EXIST elsewhere?
    - LOCAL donor : the same/near line appears in the patch's own context/removed
                    lines or elsewhere in the diff (fix mirrors nearby code).
    - REPO donor  : (where we have the graph) the added line appears in some OTHER
                    node's text in the same repo.
  A patch is "sibling-conformable" if a large fraction of its non-trivial added
  lines have a donor.

Pre-registered thresholds:
  >=30% of patches sibling-conformable  -> INTERESTING (method has legs)
  15-30%                                -> WEAK / partial
  <15%                                  -> DEAD (fix is genuine novel synthesis)
Control: trivial lines (import/return None/pass/blank/braces) measured separately;
they must NOT be what's driving any positive signal.
"""
import json, re, io
from pathlib import Path
from collections import defaultdict

TASKS = Path(r".\Gemma\comp_files\tasks.jsonl")
PROBE = Path(r".\Gemma\comp_files\probe")
GRAPHS = {
    "fastapi":  "fastapi_016ab760faba1813ba235d5582a014a58bd2f417.json",
    "rich":     "rich_fc41075a3206d2a5fd846c6f41c4d2becab814fa.json",
    "requests": "requests_6f205ff422bccd5e4c4fc0b64c5f3e7df5181db6.json",
}

def norm(line: str) -> str:
    """normalize a code line for comparison: strip, collapse whitespace."""
    return re.sub(r"\s+", " ", line.strip())

def is_trivial(l: str) -> bool:
    s = l.strip()
    if len(s) < 6: return True
    if s in ("pass", "return", "return None", "continue", "break", "else:", "try:"):
        return True
    if s.startswith(("import ", "from ", "#", '"""', "'''", "@")):
        return True
    if re.fullmatch(r"[)\]}:,]+", s): return True
    return False

def parse_diff(patch: str):
    """return (added_lines, removed_lines, context_lines) across all hunks."""
    added, removed, ctx = [], [], []
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@") \
           or line.startswith("diff ") or line.startswith("index "):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith(" "):
            ctx.append(line[1:])
    return added, removed, ctx

def load_graph_lines(repo):
    """all normalized lines appearing in any node text for this repo's graph."""
    fn = GRAPHS.get(repo)
    if not fn or not (PROBE / fn).exists():
        return None
    g = json.load(open(PROBE / fn, encoding="utf-8"))
    lines = set()
    for n in g["nodes"]:
        for l in n.get("text", "").splitlines():
            nl = norm(l)
            if nl and not is_trivial(l):
                lines.add(nl)
    return lines

def main():
    out = io.open(r".\Gemma\probe_sibling_results.txt", "w", encoding="utf-8")
    def p(*a):
        s = " ".join(str(x) for x in a); print(s); out.write(s+"\n")

    repo_lines = {r: load_graph_lines(r) for r in GRAPHS}
    for r, s in repo_lines.items():
        p(f"graph lines loaded for {r}: {len(s) if s else 'NONE'}")
    p("="*66)

    tasks = [json.loads(l) for l in open(TASKS, encoding="utf-8")]
    p(f"total tasks: {len(tasks)}")

    per_repo = defaultdict(lambda: {"n":0, "conformable":0, "frac_sum":0.0})
    detail = []
    GLOBAL_conformable = 0
    GLOBAL_n = 0
    trivial_driven = 0

    for t in tasks:
        repo = t["repo"].split("/")[-1]
        added, removed, ctx = parse_diff(t["patch"])
        nontrivial_added = [a for a in added if not is_trivial(a)]
        if not nontrivial_added:
            continue  # pure-trivial patch (docs/version bumps); skip from denom
        GLOBAL_n += 1
        per_repo[repo]["n"] += 1

        # donor pools:
        local_pool = set(norm(l) for l in (removed + ctx) if l.strip())
        repo_pool = repo_lines.get(repo) or set()

        hits = 0
        repo_hits = 0          # STRICT: donor is an OTHER node in the repo (true sibling)
        exact_repo_hits = 0    # STRICTEST: exact normalized line exists elsewhere in repo
        for a in nontrivial_added:
            na = norm(a)
            local = (na in local_pool)
            repo_exact = (na in repo_pool)
            repo_near = False
            if not repo_exact and repo_pool:
                atok = set(na.split())
                if len(atok) >= 3:
                    for d in repo_pool:
                        dtok = set(d.split())
                        if dtok:
                            j = len(atok & dtok) / len(atok | dtok)
                            if j >= 0.8:
                                repo_near = True; break
            donor = local or repo_exact or repo_near
            if donor: hits += 1
            if repo_exact or repo_near: repo_hits += 1
            if repo_exact: exact_repo_hits += 1
        frac = hits / len(nontrivial_added)
        repo_frac = repo_hits / len(nontrivial_added)
        exact_frac = exact_repo_hits / len(nontrivial_added)
        per_repo[repo].setdefault("repo_frac_sum", 0.0)
        per_repo[repo].setdefault("exact_frac_sum", 0.0)
        per_repo[repo].setdefault("repo_conformable", 0)
        # only count repo_frac where we actually HAVE a graph for the repo
        if repo_pool:
            per_repo[repo]["repo_frac_sum"] += repo_frac
            per_repo[repo]["exact_frac_sum"] += exact_frac
            if repo_frac >= 0.5:
                per_repo[repo]["repo_conformable"] += 1
        per_repo[repo]["frac_sum"] += frac
        conformable = frac >= 0.5   # half+ of fix lines have an existing donor
        if conformable:
            per_repo[repo]["conformable"] += 1
            GLOBAL_conformable += 1
        detail.append((t["instance_id"], repo, len(nontrivial_added), round(frac,2)))

    p("="*66)
    p("PER-REPO (patches with >=1 non-trivial added line):")
    p("  LOCAL = donor next to edit (context/removed) | REPO = donor in ANOTHER node")
    for r, d in sorted(per_repo.items()):
        if d["n"]==0: continue
        rfs = d.get("repo_frac_sum",0.0); efs = d.get("exact_frac_sum",0.0)
        rc = d.get("repo_conformable",0)
        p(f"  {r:9s}  n={d['n']:3d}  LOCAL-conformable={d['conformable']:3d} "
          f"({100*d['conformable']/d['n']:.0f}%)  mean_local_frac={d['frac_sum']/d['n']:.2f}")
        p(f"             REPO-conformable={rc:3d} ({100*rc/d['n']:.0f}%)  "
          f"mean_REPO_frac={rfs/d['n']:.2f}  mean_EXACT_repo_frac={efs/d['n']:.2f}")
    p("-"*66)
    p(f"GLOBAL: {GLOBAL_conformable}/{GLOBAL_n} patches sibling-conformable "
      f"= {100*GLOBAL_conformable/max(GLOBAL_n,1):.1f}%")
    p("PRE-REGISTERED BAR:  >=30% INTERESTING | 15-30% WEAK | <15% DEAD")
    p("="*66)
    # distribution of per-patch donor fraction
    import statistics
    fracs = [d[3] for d in detail]
    if fracs:
        p(f"per-patch donor-fraction: mean={statistics.mean(fracs):.2f} "
          f"median={statistics.median(fracs):.2f} "
          f"n(frac=1.0)={sum(1 for f in fracs if f==1.0)} "
          f"n(frac=0.0)={sum(1 for f in fracs if f==0.0)}")
    # show a few high and low examples
    detail.sort(key=lambda x:-x[3])
    p("\ntop sibling-conformable patches:")
    for iid, r, nl, fr in detail[:6]:
        p(f"   {fr:.2f}  {iid:14s} {r:9s} ({nl} added lines)")
    p("\nleast conformable (novel synthesis):")
    for iid, r, nl, fr in detail[-6:]:
        p(f"   {fr:.2f}  {iid:14s} {r:9s} ({nl} added lines)")
    out.close()
    print("\n(written to Gemma\\probe_sibling_results.txt)")

if __name__ == "__main__":
    main()
