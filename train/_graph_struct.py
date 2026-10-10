import json, glob, os
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_graph_struct.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)
gp = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\graphs\fastapi_2b212ddd7604891d42e2ffbafe764c334230bdb7.json"
g = json.load(open(gp, encoding="utf-8"))
p("TOP TYPE:", type(g).__name__)
if isinstance(g, dict):
    p("TOP KEYS:", list(g.keys()))
    for k in g:
        v = g[k]
        p(f"  {k}: {type(v).__name__} len={len(v) if hasattr(v,'__len__') else '-'}")
    for probe in ("nodes","links","edges"):
        if probe in g and isinstance(g[probe], list) and g[probe]:
            p(f"\n[{probe}] sample[0]: {json.dumps(g[probe][0])[:500]}")
            p(f"[{probe}] sample[1]: {json.dumps(g[probe][1])[:500]}")
# embeddings present?
emb = glob.glob(r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\**\*.npz", recursive=True)
p("\nEMBEDDINGS (.npz) found:", len(emb), emb[:3])
OUT.close(); print("done")
