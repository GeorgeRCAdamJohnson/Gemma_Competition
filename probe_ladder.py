"""
PRE-REGISTERED PROBE 3: the escalation ladder's coverage ceiling.

For each gold patch, which TIER would recover its non-trivial ADDED lines?
  T1 function-sibling : >=X% of added lines each appear in SOME single other node's text
                        (one donor function supplies most of the fix).
  T2 line-context     : (if T1 misses) added lines appear in the patch's own local context
                        (removed/context lines near the edit) -- a local line-level analogy.
  T3 multi-donor      : (if T1&T2 miss) added lines are covered by the UNION of >=2 donor
                        nodes, no single one enough -> the literal "70% here, 30% there".
  MISS                : no donor set covers it -> genuine novel synthesis.

Per-line donor = a repo node line (or local context line) with token-Jaccard >= 0.8.
A tier "covers" a patch if >= COVER (0.8) of its non-trivial added lines have a donor
under that tier's rules.

Pre-registered bars:
  T1 should recover ~the clean-sibling slice (~40-50%).
  Each lower tier should add MARGINAL coverage.
  T3 is worth building ONLY if it adds >=10% on top of T1+T2; else drop it (complexity for a story).
  Report cumulative coverage and the honest ceiling (T1+T2+T3).
Judge: 115 tasks with graphs (fastapi/rich/requests at their commit). httpx + off-commit = skip.
Caveat (log it): "recoverable from donors" is the CEILING (raw material exists), NOT proof the
frozen model emits the patch. Only swegemma eval confirms that.
"""
import json, re, io
from pathlib import Path
from collections import defaultdict

TASKS = Path(r".\Gemma\comp_files\tasks.jsonl")
GRAPHDIR = Path(r".\Gemma\comp_files\graphs")   # per-task graphs: <repo>_<commit>.json
COVER = 0.8     # fraction of added lines that must have a donor for a tier to "cover"
JACCARD = 0.8   # per-line near-match threshold

def norm(l): return re.sub(r"\s+"," ",l.strip())
def trivial(l):
    s=l.strip()
    if len(s)<6: return True
    if s in ("pass","return","return None","continue","break","else:","try:"): return True
    if s.startswith(("import ","from ","#",'"""',"'''","@")): return True
    if re.fullmatch(r"[)\]}:,]+",s): return True
    return False

def tokens(s): return frozenset(norm(s).split())

def near(a_tok, pool_tok_list):
    """is there a donor line (token set) with jaccard>=JACCARD to a_tok?"""
    if len(a_tok) < 3:
        return False
    for d in pool_tok_list:
        if not d: continue
        inter = len(a_tok & d)
        if inter == 0: continue
        if inter/len(a_tok | d) >= JACCARD: return True
    return False

def parse_added_local(patch):
    added, local = [], []
    for line in patch.splitlines():
        if line.startswith(("+++","---","@@","diff ","index ")): continue
        if line.startswith("+"): added.append(line[1:])
        elif line.startswith("-"): local.append(line[1:])
        elif line.startswith(" "): local.append(line[1:])
    return added, local

def load_nodes_from(path):
    g=json.load(open(path,encoding="utf-8"))
    node_lines={}
    for n in g["nodes"]:
        s=set()
        for l in n.get("text","").splitlines():
            if l.strip() and not trivial(l): s.add(norm(l))
        if s: node_lines[n["id"]]=s
    return node_lines

def main():
    out=io.open(r".\Gemma\probe_ladder_results.txt","w",encoding="utf-8")
    def p(*a):
        s=" ".join(str(x) for x in a); print(s); out.write(s+"\n")

    tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
    tally=defaultdict(int)   # tier -> count
    repo_tally=defaultdict(lambda: defaultdict(int))
    N=0; skipped_nograph=0
    t3_donor_counts=[]       # how many donors T3 needed
    t3_split=[]              # (best single donor coverage, total coverage) for T3 cases
    graph_cache={}           # commit-path -> node_lines
    idx_cache={}             # commit-path -> (node_line_toks, inverted_index)

    for t in tasks:
        repo=t["repo"].split("/")[-1]
        gpath=GRAPHDIR/f"{repo}_{t['base_commit']}.json"
        if not gpath.exists():
            skipped_nograph+=1; continue
        if gpath not in graph_cache:
            graph_cache[gpath]=load_nodes_from(gpath)
        nodes=graph_cache[gpath]
        added, local = parse_added_local(t["patch"])
        A=[a for a in added if not trivial(a)]
        if not A:
            continue
        N+=1
        A_tok=[tokens(a) for a in A]
        A_norm=[norm(a) for a in A]

        # Build per-graph structures ONCE (cached): node line-token sets + inverted index.
        if gpath not in idx_cache:
            node_line_toks={}   # nid -> list[frozenset tokens]
            inv=defaultdict(set)  # token -> set(nid)
            for nid,lines in nodes.items():
                tl=[]
                for ln in lines:
                    ft=frozenset(ln.split())
                    tl.append(ft)
                    for tok in ft: inv[tok].add(nid)
                node_line_toks[nid]=tl
            idx_cache[gpath]=(node_line_toks, inv)
        node_line_toks, inv = idx_cache[gpath]

        # For each added line, find the SET of donor nodes (jaccard>=JACCARD on some line).
        # Candidate nodes = those sharing >=1 token (inverted index), not all nodes.
        donors_per_line=[]   # list over added lines -> set(nid) that can donate it
        for at in A_tok:
            cand=set()
            for tok in at:
                s=inv.get(tok)
                if s: cand |= s
            dn=set()
            for nid in cand:
                for ft in node_line_toks[nid]:
                    if not ft: continue
                    inter=len(at & ft)
                    if inter and inter/len(at | ft) >= JACCARD:
                        dn.add(nid); break
            donors_per_line.append(dn)

        # ---- T1: a SINGLE node donates >=COVER of added lines ----
        from collections import Counter as _C
        node_hit=_C()
        for dn in donors_per_line:
            for nid in dn: node_hit[nid]+=1
        best_cov = (max(node_hit.values())/len(A)) if node_hit else 0.0
        single_best = best_cov
        if best_cov>=COVER:
            tally["T1_function_sibling"]+=1; repo_tally[repo]["T1"]+=1; continue

        # ---- T2: local line-context donates >=COVER ----
        loc_norm=set(norm(l) for l in local if l.strip() and not trivial(l))
        loc_tok=[frozenset(x.split()) for x in loc_norm]
        loc_hit=sum(1 for at in A_tok if near(at,loc_tok))
        if loc_hit/len(A)>=COVER:
            tally["T2_line_context"]+=1; repo_tally[repo]["T2"]+=1; continue

        # ---- T3: union of local + multiple nodes covers >=COVER ----
        covered=[bool(near(at,loc_tok)) for at in A_tok]
        donors_used = 1 if any(covered) else 0
        # greedy set cover using donors_per_line
        while sum(covered)/len(A) < COVER:
            gain=_C()
            for i,dn in enumerate(donors_per_line):
                if covered[i]: continue
                for nid in dn: gain[nid]+=1
            if not gain: break
            best_nid,_=gain.most_common(1)[0]
            for i,dn in enumerate(donors_per_line):
                if best_nid in dn: covered[i]=True
            donors_used+=1
        if sum(covered)/len(A)>=COVER:
            tally["T3_multi_donor"]+=1; repo_tally[repo]["T3"]+=1
            t3_donor_counts.append(donors_used)
            t3_split.append((round(single_best,2), round(sum(covered)/len(A),2)))
            continue

        tally["MISS_novel_synthesis"]+=1; repo_tally[repo]["MISS"]+=1

    p(f"tasks measured (graph available): {N}   (skipped, no graph yet: {skipped_nograph})")
    p("-"*68)
    order=["T1_function_sibling","T2_line_context","T3_multi_donor","MISS_novel_synthesis"]
    cum=0
    for k in order:
        c=tally[k]; cum+=c
        p(f"  {k:24s}: {c:3d} ({100*c/N:4.1f}%)   [cumulative {100*cum/N:4.1f}%]")
    p("-"*68)
    t12=tally["T1_function_sibling"]+tally["T2_line_context"]
    p(f"T1+T2 coverage        : {100*t12/N:.1f}%")
    p(f"T3 marginal add       : {100*tally['T3_multi_donor']/N:.1f}%  "
      f"(build T3 only if >=10%)")
    p(f"CEILING (T1+T2+T3)    : {100*(t12+tally['T3_multi_donor'])/N:.1f}%")
    p(f"novel-synthesis floor : {100*tally['MISS_novel_synthesis']/N:.1f}%  (method cannot reach)")
    if t3_donor_counts:
        import statistics
        p("-"*68)
        p(f"T3 '70/30' check: median donors used = {statistics.median(t3_donor_counts)}, "
          f"max = {max(t3_donor_counts)}")
        p(f"  T3 single-best-donor coverage vs total (sample): {t3_split[:8]}")
        p("  (if single-best is already ~1.0 these are mislabeled T1; if ~0.5-0.7 the"
          " multi-donor assembly is real)")
    p("-"*68)
    p("PER-REPO tier counts:")
    for r in sorted(repo_tally):
        d=repo_tally[r]
        p(f"  {r:9s} " + " ".join(f"{k}:{d[k]}" for k in ('T1','T2','T3','MISS')))
    p("="*68)
    p("CAVEAT: this is the RECOVERY CEILING (donor material exists). It is NOT proof the")
    p("frozen quantized model emits the patch when given the donor. Only swegemma eval confirms.")
    out.close(); print("\n(written to Gemma\\probe_ladder_results.txt)")

if __name__=="__main__":
    main()
