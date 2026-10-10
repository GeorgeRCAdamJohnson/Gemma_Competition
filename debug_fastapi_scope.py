"""
DEBUG: is 'fastapi 2/67' a real property or a prefix-matcher bug?
For a few fastapi tasks, print:
  - the file path(s) the patch touches (+++ b/...)
  - the dotted prefix my probe derived
  - sample node IDs in that task's graph
  - whether ANY node id actually starts-with / contains the derived prefix
If the derived prefix matches NO nodes while the graph clearly has relevant ones,
the probe's same-module filter is broken (execution bug), not a fastapi property.
"""
import json, re
from pathlib import Path
TASKS=Path(r".\Gemma\comp_files\tasks.jsonl")
GDIR=Path(r".\Gemma\comp_files\graphs")

def patch_files(patch):
    pref=set(); raw=set()
    for l in patch.splitlines():
        m=re.match(r'\+\+\+ b/(.+)', l)
        if m:
            p=m.group(1); raw.add(p)
            if p.endswith(".py"):
                dotted=p[:-3].replace("/",".")
                for root in ("src.","docs_src."):
                    if dotted.startswith(root): dotted=dotted[len(root):]
                pref.add(dotted)
    return raw,pref

tasks=[json.loads(l) for l in open(TASKS,encoding="utf-8")]
fa=[t for t in tasks if t["repo"].endswith("fastapi")][:6]
for t in fa:
    g=GDIR/f"fastapi_{t['base_commit']}.json"
    if not g.exists(): print("no graph", t["instance_id"]); continue
    J=json.load(open(g,encoding="utf-8"))
    ids=[n["id"] for n in J["nodes"]]
    raw,pref=patch_files(t["patch"])
    print("="*70)
    print("task:", t["instance_id"])
    print("  patch files (raw):", list(raw)[:4])
    print("  derived prefixes :", list(pref)[:4])
    # does any node id match?
    matched=[]
    for p in pref:
        m=[nid for nid in ids if nid.startswith(p) or p in nid]
        matched.append((p,len(m),m[:3]))
    for p,c,sample in matched:
        print(f"    prefix '{p[:40]}' -> {c} node matches  e.g. {sample}")
    # show what a relevant node id actually looks like: find nodes whose id contains the file stem
    for p in raw:
        stem=p.split("/")[-1][:-3] if p.endswith(".py") else p.split("/")[-1]
        rel=[nid for nid in ids if stem in nid][:4]
        print(f"    file stem '{stem}' appears in node ids: {rel}")
