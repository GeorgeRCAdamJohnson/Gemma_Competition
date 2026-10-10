"""
COMBINED SCOPED LADDER: what do the tiers get TOGETHER, with scoped->widening search?

Tiers (escalate only if the cheaper tier misses):
  T1 same-MODULE sibling : donor restricted to nodes whose id shares the buggy file's module
                           prefix (FastAPI code near FastAPI code). cheapest, highest precision.
  T2 local line-context  : the patch's own context/removed lines (line before/after).
  T3 same-REPO sibling   : donor = any node in the repo (widen beyond module).
  T4 multi-donor assembly: union of >=2 repo nodes (the 70/30 case).
  MISS                   : none cover -> novel synthesis.

A tier "covers" if >=COVER (0.8) of non-trivial added lines have a donor under that tier.
We attribute each patch to the FIRST (cheapest) tier that covers it -> this is the realistic
agent behavior and gives the honest CUMULATIVE coverage of the whole ladder.

Also report coverage at COVER=0.6 (partial-fix regime, since a near-miss patch may still pass
tests) as a sensitivity band.
Buggy module prefix: inferred from the patch's +++/--- file path, mapped to dotted id prefix.
"""
import json, re
from pathlib import Path
from collections import defaultdict, Counter

TASKS=Path(r".\Gemma\comp_files\tasks.jsonl")
GDIR=Path(r".\Gemma\comp_files\graphs")
J=0.8

def norm(l): return re.sub(r"\s+"," ",l.strip())
def trivial(l):
    s=l.strip()
    if len(s)<6: return True
    if s in ("pass","return","return None","continue","break","else:","try:"): return True
    if s.startswith(("import ","from ","#",'"""',"'''","@")): return True
    if re.fullmatch(r"[)\]}:,]+",s): return True
    return False

def patch_files(patch):
    """dotted module-ish prefixes touched by the patch (from +++ b/path lines)."""
    pref=set()
    for l in patch.splitlines():
        m=re.match(r'\+\+\+ b/(.+)', l)
        if m:
            p=m.group(1)
            if p.endswith(".py"):
                dotted=p[:-3].replace("/",".")
                # strip common src roots to match graph id convention
                for root in ("src.","docs_src."):
                    if dotted.startswith(root): dotted=dotted[len(root):]
                pref.add(dotted)
    return pref

def added_local(patch):
    a=[]; loc=[]
    for l in patch.splitlines():
        if l.startswith(("+++","---","@@","diff ","index ")): continue
        if l.startswith("+"): a.append(l[1:])
        elif l.startswith(("-"," ")): loc.append(l[1:])
    return a,loc

def covers(donor_sets, A_n, frac):
    hit=sum(1 for d in donor_sets if d)/len(A_n)
    return hit>=frac

def main():
    tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
    idx={}
    def run(COVER):
        tally=Counter(); repo_tally=defaultdict(Counter); N=0
        for t in tasks:
            repo=t["repo"].split("/")[-1]
            g=GDIR/f"{repo}_{t['base_commit']}.json"
            if not g.exists(): continue
            if g not in idx:
                JJ=json.load(open(g,encoding="utf-8"))
                inv=defaultdict(set); nt={}; ids=[]
                for n in JJ["nodes"]:
                    nid=n["id"]; ids.append(nid); tl=[]
                    for ln in n.get("text","").splitlines():
                        if ln.strip() and not trivial(ln):
                            ft=frozenset(norm(ln).split()); tl.append(ft)
                            for tok in ft: inv[tok].add(nid)
                    nt[nid]=tl
                idx[g]=(inv,nt,ids)
            inv,nt,ids=idx[g]
            a,loc=added_local(t["patch"])
            A=[x for x in a if not trivial(x)]
            if not A: continue
            N+=1
            Atok=[frozenset(norm(x).split()) for x in A]
            prefixes=patch_files(t["patch"])

            def donors_for(at, node_filter=None):
                cand=set()
                for tok in at:
                    s=inv.get(tok)
                    if s: cand|=s
                if node_filter is not None:
                    cand={nid for nid in cand if node_filter(nid)}
                for nid in cand:
                    for ft in nt[nid]:
                        if ft and len(at&ft)/len(at|ft)>=J: return nid
                return None

            # T1: same-module nodes only
            def inmod(nid): return any(nid.startswith(p) or p in nid for p in prefixes) if prefixes else False
            d1=[donors_for(at, inmod) for at in Atok]
            if covers(d1,A,COVER): tally["T1_same_module"]+=1; repo_tally[repo]["T1"]+=1; continue
            # T2: local context
            locset=[frozenset(norm(l).split()) for l in loc if l.strip() and not trivial(l)]
            d2=[]
            for at in Atok:
                ok=any(ls and len(at&ls)/len(at|ls)>=J for ls in locset) if len(at)>=3 else False
                d2.append(ok)
            if covers(d2,A,COVER): tally["T2_line_context"]+=1; repo_tally[repo]["T2"]+=1; continue
            # T3: whole repo single-donor-per-line
            d3=[donors_for(at) for at in Atok]
            if covers(d3,A,COVER): tally["T3_same_repo"]+=1; repo_tally[repo]["T3"]+=1; continue
            # T4: multi-donor union (any coverage across all tiers' per-line donors)
            union=[bool(x) or bool(y) for x,y in zip(d3,d2)]
            if sum(union)/len(A)>=COVER: tally["T4_assembly"]+=1; repo_tally[repo]["T4"]+=1; continue
            tally["MISS"]+=1; repo_tally[repo]["MISS"]+=1
        return tally,repo_tally,N

    for COVER in (0.8, 0.6):
        tally,repo_tally,N=run(COVER)
        print("="*70)
        print(f"COMBINED SCOPED LADDER  (coverage threshold = {COVER})   N={N}")
        order=["T1_same_module","T2_line_context","T3_same_repo","T4_assembly","MISS"]
        cum=0
        for k in order:
            c=tally[k]; cum+=c
            tag="" if k=="MISS" else f"  [cumulative solvable {100*cum/N:.1f}%]" if k!="MISS" else ""
            print(f"  {k:16s}: {c:3d} ({100*c/N:4.1f}%){tag}")
        solvable=N-tally["MISS"]
        print(f"  --> LADDER TOTAL COVERAGE: {solvable}/{N} = {100*solvable/N:.1f}%")
        print(f"  per-repo:")
        for r in sorted(repo_tally):
            d=repo_tally[r]; tot=sum(d.values())
            cov=tot-d['MISS']
            print(f"     {r:9s} {cov}/{tot} covered  (" + " ".join(f"{k}:{d[k]}" for k in ('T1','T2','T3','T4','MISS')) + ")")

if __name__=="__main__":
    main()
