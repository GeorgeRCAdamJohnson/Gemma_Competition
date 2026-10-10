"""
TARGET CHARACTERIZATION: don't aggregate -- NAME the recoverable slice.
For every task (full 127 graphs), compute:
  - lenient per-line donor coverage (any node, jaccard>=0.8, nontrivial lines)
  - concentrated single-node coverage
  - diff shape (from probe_mistakes classify, inlined)
  - n added lines
Then list the HIGH-coverage tasks (the ~12% target) with shape + size, and cross-tab
coverage x shape so we see whether the recoverable slice == the clean-deviation slice.
Also: measure how NON-trivial the recovered lines are (avg tokens) so 12% isn't boilerplate.
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

def hunks(patch):
    H=[]; r=[]; a=[]; inh=False
    for l in patch.splitlines():
        if l.startswith("@@"):
            if inh and (r or a): H.append((r,a)); r=[];a=[]
            inh=True; continue
        if l.startswith(("+++","---","diff ","index ")):
            if inh and (r or a): H.append((r,a)); r=[];a=[]
            inh=False; continue
        if not inh: continue
        if l.startswith("+"): a.append(l[1:])
        elif l.startswith("-"): r.append(l[1:])
    if r or a: H.append((r,a))
    return H

def classify(removed,added):
    r=[l for l in removed if not trivial(l)]; a=[l for l in added if not trivial(l)]
    if not r and a:
        if any(re.search(r'\braise\b',l) for l in a): return "add_raise/except"
        if any(re.search(r'^\s*(if|elif)\b',l) for l in a): return "add_condition"
        if any(re.search(r'\breturn\b',l) for l in a): return "add_return"
        if any(re.search(r'^\s*(def|async def|class)\b',l) for l in a): return "add_def/class"
        return "add_other"
    if r and not a: return "pure_deletion"
    if len(r)==1 and len(a)==1:
        ro,ao=r[0].strip(),a[0].strip()
        rn=re.findall(r'-?\b\d+\b',ro); an=re.findall(r'-?\b\d+\b',ao)
        if rn and an and rn!=an and re.sub(r'-?\b\d+\b','#',ro)==re.sub(r'-?\b\d+\b','#',ao): return "const_change"
        rt,at=ro.split(),ao.split()
        if len(rt)==len(at) and sum(1 for x,y in zip(rt,at) if x!=y)==1: return "single_token"
        return "single_line_other"
    if "def " in "\n".join(r+a): return "multiline_logic"
    return "multiline_other"

def main():
    tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
    idx={}
    rows=[]
    for t in tasks:
        repo=t["repo"].split("/")[-1]
        g=GDIR/f"{repo}_{t['base_commit']}.json"
        if not g.exists(): continue
        if g not in idx:
            JJ=json.load(open(g,encoding="utf-8"))
            inv=defaultdict(set); nt={}
            for n in JJ["nodes"]:
                tl=[]
                for ln in n.get("text","").splitlines():
                    if ln.strip() and not trivial(ln):
                        ft=frozenset(norm(ln).split()); tl.append(ft)
                        for tok in ft: inv[tok].add(n["id"])
                nt[n["id"]]=tl
            idx[g]=(inv,nt)
        inv,nt=idx[g]
        H=hunks(t["patch"])
        added=[x for _,a in H for x in a]
        A=[a for a in added if not trivial(a)]
        if not A: continue
        Atok=[frozenset(norm(a).split()) for a in A]
        donors=[]
        for at in Atok:
            cand=set()
            for tok in at:
                s=inv.get(tok)
                if s: cand|=s
            dn=set()
            for nid in cand:
                for ft in nt[nid]:
                    if ft and len(at&ft)/len(at|ft)>=J: dn.add(nid); break
            donors.append(dn)
        lenient=sum(1 for d in donors if d)/len(A)
        hit=Counter()
        for d in donors:
            for nid in d: hit[nid]+=1
        conc=(max(hit.values())/len(A)) if hit else 0.0
        # dominant shape from largest code hunk
        code=[(r,a) for r,a in H if any(not trivial(x) for x in r+a)]
        shape=classify(*max(code,key=lambda h:len(h[0])+len(h[1]))) if code else "trivial"
        avgtok=sum(len(x) for x in Atok)/len(Atok)
        rows.append((t["instance_id"],repo,len(A),round(lenient,2),round(conc,2),shape,round(avgtok,1)))

    rows.sort(key=lambda x:-x[3])
    N=len(rows)
    print(f"tasks: {N}")
    print("="*72)
    print("TARGET SLICE (lenient donor coverage >= 0.5):")
    tgt=[r for r in rows if r[3]>=0.5]
    print(f"  count: {len(tgt)} ({100*len(tgt)/N:.0f}%)")
    print(f"  {'task':15s}{'repo':9s}{'nA':>3s} {'lenient':>7s} {'conc':>5s}  {'shape':16s} avgtok")
    for iid,repo,nA,le,co,sh,av in tgt:
        print(f"  {iid:15s}{repo:9s}{nA:3d} {le:7.2f} {co:5.2f}  {sh:16s} {av}")
    print("-"*72)
    print("SHAPE x COVERAGE crosstab (does recoverable == clean-deviation?):")
    byshape=defaultdict(lambda:[0,0])  # shape -> [n, n_recoverable]
    for r in rows:
        byshape[r[5]][0]+=1
        if r[3]>=0.5: byshape[r[5]][1]+=1
    for sh,(n,rec) in sorted(byshape.items(),key=lambda kv:-kv[1][1]):
        print(f"  {sh:18s} total {n:3d}  recoverable {rec:3d}  ({100*rec/max(n,1):.0f}% of this shape)")
    print("-"*72)
    # is the target slice boilerplate? avg tokens of recovered vs all
    import statistics as st
    print(f"avg tokens/added-line: target slice = "
          f"{st.mean([r[6] for r in tgt]) if tgt else 0:.1f}, all = {st.mean([r[6] for r in rows]):.1f}")
    print("  (if target avgtok is much LOWER, the 12% is boilerplate not real fixes)")

if __name__=="__main__":
    main()
