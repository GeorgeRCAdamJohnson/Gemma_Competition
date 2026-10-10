"""
PRE-REGISTERED PROBE 2: do the 129 gold fixes collapse into a SMALL set of recurring
mistake-shapes? If yes, "infer intended form + check common mistakes" is a tractable,
finite checklist (trainable into a LoRA / encodable as a skill). If fixes are too diverse,
the checklist idea is dead.

Pre-registered bar:
  >=50% of patches fall into the top-10 shape categories  -> TRACTABLE checklist exists
  25-50%                                                  -> PARTIAL
  <25%                                                    -> DEAD (fixes too diverse)
Also report: how many patches are a SINGLE-line / SINGLE-hunk change (the easy, high-yield
targets for a conform-the-deviation agent), and the diff-size distribution.

Method (model-free, over all 129 gold patches): classify each patch by structural shape of
its (removed -> added) edit using AST-ish / regex signatures. Categories are the common SWE
mistake taxonomy (cf. PAGENT arXiv 2506.17772): wrong-constant, wrong-operator, off-by-one,
added-guard/none-check, wrong-exception, signature/arg change, added-return, wrong-attribute,
added-condition-branch, string/message change, import/dep, pure-addition (new code), etc.
"""
import json, re, io
from pathlib import Path
from collections import Counter, defaultdict

TASKS = Path(r".\Gemma\comp_files\tasks.jsonl")

def parse_hunks(patch):
    """Return list of hunks; each hunk = (removed_lines, added_lines)."""
    hunks = []
    cur_r, cur_a = [], []
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("@@"):
            if in_hunk and (cur_r or cur_a):
                hunks.append((cur_r, cur_a)); cur_r, cur_a = [], []
            in_hunk = True; continue
        if line.startswith(("+++","---","diff ","index ")):
            if in_hunk and (cur_r or cur_a):
                hunks.append((cur_r, cur_a)); cur_r, cur_a = [], []
            in_hunk = False; continue
        if not in_hunk: continue
        if line.startswith("+"): cur_a.append(line[1:])
        elif line.startswith("-"): cur_r.append(line[1:])
    if cur_r or cur_a: hunks.append((cur_r, cur_a))
    return hunks

def nontrivial(l):
    s=l.strip()
    return len(s)>=3 and not s.startswith(("#",'"""',"'''"))

def classify(removed, added):
    """Return a shape label for one patch (coarsest dominant edit)."""
    r = [l for l in removed if nontrivial(l)]
    a = [l for l in added if nontrivial(l)]
    rj = "\n".join(r); aj = "\n".join(a)

    # pure addition (no real removed lines) vs modification vs pure deletion
    if not r and a:
        # what KIND of addition?
        if any(re.search(r'\braise\b', l) for l in a): return "add_raise/except"
        if any(re.search(r'^\s*(if|elif)\b', l) for l in a): return "add_condition_branch"
        if any(re.search(r'\breturn\b', l) for l in a): return "add_return"
        if any(re.search(r'\b(is None|is not None|== None|!= None)\b', l) for l in a): return "add_none_guard"
        if any(re.search(r'^\s*(def|async def|class)\b', l) for l in a): return "add_def/class"
        if any(re.search(r'^\s*(import|from)\b', l) for l in a): return "add_import"
        if any(re.search(r'^\s*@', l) for l in a): return "add_decorator"
        return "add_other"
    if r and not a:
        return "pure_deletion"

    # modification: compare the aligned change
    # single-line swap?
    if len(r)==1 and len(a)==1:
        ro, ao = r[0].strip(), a[0].strip()
        # numeric constant change
        rn = re.findall(r'-?\b\d+\b', ro); an = re.findall(r'-?\b\d+\b', ao)
        if rn and an and rn!=an and re.sub(r'-?\b\d+\b','#',ro)==re.sub(r'-?\b\d+\b','#',ao):
            # off-by-one if differ by 1
            try:
                if any(abs(int(x)-int(y))==1 for x,y in zip(rn,an)): return "off_by_one"
            except: pass
            return "wrong_constant"
        # string/message change
        rs = re.findall(r'["\'].*?["\']', ro); as_ = re.findall(r'["\'].*?["\']', ao)
        if rs and as_ and re.sub(r'["\'].*?["\']','#',ro)==re.sub(r'["\'].*?["\']','#',ao):
            return "string/message_change"
        # operator change
        if re.sub(r'[<>=!]=?|\bis\b|\bnot\b|\band\b|\bor\b','#',ro)!=ro and \
           re.sub(r'[<>=!]=?|\bis\b|\bnot\b|\band\b|\bor\b','#',ro)==re.sub(r'[<>=!]=?|\bis\b|\bnot\b|\band\b|\bor\b','#',ao) and ro!=ao:
            return "operator/comparison_change"
        # attribute/name change (same structure, one identifier differs)
        rt, at = ro.split(), ao.split()
        if len(rt)==len(at) and sum(1 for x,y in zip(rt,at) if x!=y)==1:
            return "single_token_change"
        # signature / args
        if ("def " in ro or "(" in ro) and ro.count(",")!=ao.count(","):
            return "signature/arg_change"
        return "single_line_other"

    # multi-line modification
    if "def " in rj or "def " in aj: return "multiline_logic_in_func"
    return "multiline_other"

def main():
    out = io.open(r".\Gemma\probe_mistakes_results.txt","w",encoding="utf-8")
    def p(*a):
        s=" ".join(str(x) for x in a); print(s); out.write(s+"\n")

    tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
    shapes=Counter(); per_repo_shapes=defaultdict(Counter)
    hunk_counts=Counter(); added_line_counts=[]
    single_hunk=single_line=0
    examples=defaultdict(list)

    for t in tasks:
        hunks=parse_hunks(t["patch"])
        # size stats
        n_added=sum(len([x for x in a if nontrivial(x)]) for _,a in hunks)
        added_line_counts.append(n_added)
        code_hunks=[(r,a) for (r,a) in hunks if any(nontrivial(x) for x in r+a)]
        hunk_counts[min(len(code_hunks),5)]+=1
        if len(code_hunks)==1: single_hunk+=1
        if n_added<=1: single_line+=1
        # dominant shape: classify the largest code hunk
        if not code_hunks:
            shapes["trivial/empty"]+=1; continue
        big=max(code_hunks,key=lambda h:len(h[0])+len(h[1]))
        lbl=classify(big[0],big[1])
        shapes[lbl]+=1
        per_repo_shapes[t["repo"].split("/")[-1]][lbl]+=1
        if len(examples[lbl])<2:
            examples[lbl].append(t["instance_id"])

    N=len(tasks)
    p("="*66); p(f"total tasks: {N}"); p("="*66)
    p("DIFF SIZE:")
    import statistics
    p(f"  single-hunk patches : {single_hunk}/{N} ({100*single_hunk/N:.0f}%)")
    p(f"  <=1 added line      : {single_line}/{N} ({100*single_line/N:.0f}%)")
    p(f"  added-lines median  : {statistics.median(added_line_counts):.0f}  "
      f"mean {statistics.mean(added_line_counts):.1f}  max {max(added_line_counts)}")
    p(f"  code-hunks/patch    : " + ", ".join(f"{k}:{v}" for k,v in sorted(hunk_counts.items())))
    p("-"*66)
    p("MISTAKE-SHAPE DISTRIBUTION (dominant hunk per patch):")
    top=shapes.most_common()
    cum=0
    for i,(lbl,c) in enumerate(top):
        cum+=c
        star=" <-- top10 cum" if i<10 else ""
        p(f"  {c:3d} ({100*c/N:4.1f}%)  {lbl:28s} e.g. {','.join(examples[lbl])}"
          + (f"   [cum {100*cum/N:.0f}%]" if i<10 else ""))
    top10=sum(c for _,c in top[:10])
    p("-"*66)
    p(f"TOP-10 SHAPES COVER: {top10}/{N} = {100*top10/N:.1f}%")
    p("PRE-REGISTERED BAR: >=50% TRACTABLE | 25-50% PARTIAL | <25% DEAD")
    p(f"distinct shapes total: {len(shapes)}")
    out.close(); print("\n(written to Gemma\\probe_mistakes_results.txt)")

if __name__=="__main__":
    main()
