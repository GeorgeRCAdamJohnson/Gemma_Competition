"""
NULL INVESTIGATION: Exp1 said 74% sibling-conformable; Exp3 said 4.7%. Why?
Exp1 bar: EACH added line has SOME donor anywhere (per-line, lenient, union of all nodes).
Exp3 bar: a SINGLE node supplies >=80% of added lines (concentrated donor).
Reconcile: measure, per patch, the per-LINE donor rate under Exp1 rules EXACTLY (any node,
any line, jaccard>=0.8) using the real per-task graph (Exp1 only had 3 graphs; now we have 127).
Then show the gap: lenient per-line coverage vs concentrated single-node coverage.
Also: how trivial are the "donated" lines? (maybe Exp1's hits were boilerplate.)
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

def added_lines(patch):
    out=[]
    for l in patch.splitlines():
        if l.startswith(("+++","---","@@","diff ","index ")): continue
        if l.startswith("+"): out.append(l[1:])
    return out

def main():
    tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
    idxcache={}
    per_line_lenient=[]  # per-patch: fraction of added lines with ANY donor (Exp1 rule, full graph)
    per_line_concentrated=[]  # per-patch: max fraction from a single node (Exp3 rule)
    examples=[]
    for t in tasks:
        repo=t["repo"].split("/")[-1]
        g=GDIR/f"{repo}_{t['base_commit']}.json"
        if not g.exists(): continue
        if g not in idxcache:
            J_=json.load(open(g,encoding="utf-8"))
            inv=defaultdict(set); nodetok={}
            for n in J_["nodes"]:
                tl=[]
                for ln in n.get("text","").splitlines():
                    if ln.strip() and not trivial(ln):
                        ft=frozenset(norm(ln).split()); tl.append(ft)
                        for tok in ft: inv[tok].add(n["id"])
                nodetok[n["id"]]=tl
            idxcache[g]=(inv,nodetok)
        inv,nodetok=idxcache[g]
        A=[a for a in added_lines(t["patch"]) if not trivial(a)]
        if not A: continue
        Atok=[frozenset(norm(a).split()) for a in A]
        # per line: which nodes donate it
        donors=[]
        for at in Atok:
            cand=set()
            for tok in at:
                s=inv.get(tok)
                if s: cand|=s
            dn=set()
            for nid in cand:
                for ft in nodetok[nid]:
                    if ft and len(at&ft)/len(at|ft)>=J: dn.add(nid); break
            donors.append(dn)
        lenient=sum(1 for d in donors if d)/len(A)       # Exp1-style
        nodehit=Counter()
        for d in donors:
            for nid in d: nodehit[nid]+=1
        concentrated=(max(nodehit.values())/len(A)) if nodehit else 0.0  # Exp3-style
        per_line_lenient.append(lenient)
        per_line_concentrated.append(concentrated)
        if len(examples)<5 and lenient>0.6 and concentrated<0.4:
            examples.append((t["instance_id"],round(lenient,2),round(concentrated,2),len(A)))

    import statistics as st
    n=len(per_line_lenient)
    print(f"patches measured: {n}")
    print(f"LENIENT per-line donor coverage (Exp1 rule, full graph): "
          f"mean={st.mean(per_line_lenient):.2f} median={st.median(per_line_lenient):.2f}")
    print(f"CONCENTRATED single-node coverage (Exp3 rule): "
          f"mean={st.mean(per_line_concentrated):.2f} median={st.median(per_line_concentrated):.2f}")
    print(f"patches with lenient>=0.5: {sum(1 for x in per_line_lenient if x>=0.5)} "
          f"({100*sum(1 for x in per_line_lenient if x>=0.5)/n:.0f}%)")
    print(f"patches with concentrated>=0.8: {sum(1 for x in per_line_concentrated if x>=0.8)} "
          f"({100*sum(1 for x in per_line_concentrated if x>=0.8)/n:.0f}%)")
    print(f"THE GAP = scattered donors: fix lines exist but across MANY nodes, not one sibling.")
    print("examples (lenient high, concentrated low = scattered):")
    for e in examples: print("  ",e)

if __name__=="__main__":
    main()
