"""Inspect the one .npz embedding we have, to verify the audit's claim #4 (embeddings track GRAPH
distance, not code text) as far as we can without the swegemma source."""
import numpy as np, json, os
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_inspect_npz.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)
npz = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\probe\fastapi_016ab760faba1813ba235d5582a014a58bd2f417.npz"
z = np.load(npz, allow_pickle=True)
p("npz files/keys:", list(z.files))
for k in z.files:
    arr = z[k]
    p(f"  {k}: shape={getattr(arr,'shape',None)} dtype={getattr(arr,'dtype',None)}")
    if arr.dtype == object or (hasattr(arr,'ndim') and arr.ndim==1 and arr.size<6000 and arr.dtype.kind in 'UO'):
        p(f"    sample: {arr[:5]}")
# If there's a key->vector mapping, show how many nodes have vectors vs the graph node count
gp = npz.replace(".npz",".json")
if os.path.exists(gp):
    g = json.load(open(gp,encoding="utf-8"))
    p(f"\n  matching graph nodes: {len(g['nodes'])}")
OUT.close(); print("done")
