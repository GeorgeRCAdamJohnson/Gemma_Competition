"""Verify the competitor's graph-audit claims against OUR comp_files/graphs before re-architecting.
Claims to check:
 1. node ids are full dotted paths; exact-match is what the real tool needs.
 2. NO async defs in node sources; NO self.m() edges.
 3. edges all type 'calls' lowercase; stored both directions.
 4. embeddings track graph distance not text (we only have 1 .npz; check it exists/shape).
 5. TF-IDF over def names+source: can we localize? (quick proxy, not full 122-task run)
"""
import json, re, os, glob, collections
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_verify_graph_audit.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

gp = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\graphs\fastapi_cb83b83dcf78eab4ea17d504db5abcda705fbdc4.json"  # 15588 (sse) commit
g = json.load(open(gp, encoding="utf-8"))
nodes = g["nodes"]; edges = g["edges"]
p(f"nodes={len(nodes)} edges={len(edges)}")

# 1. id format
ids = [n.get("id") or n.get("name") for n in nodes]
p(f"\n[1] id samples: {ids[:4]}")
dotted = sum(1 for i in ids if "." in i)
p(f"    dotted-path ids: {dotted}/{len(ids)}")

# 2. async defs + self calls in node TEXT
async_nodes = sum(1 for n in nodes if "async def" in (n.get("text") or ""))
self_calls_in_text = sum((n.get("text") or "").count("self.") for n in nodes)
p(f"\n[2] nodes whose source contains 'async def': {async_nodes}")
p(f"    total 'self.' occurrences across node sources: {self_calls_in_text}")
# are any NODE NAMES async (can't tell from name); check edges for any self-ish target
edge_types = collections.Counter(e.get("type") for e in edges)
p(f"\n[3] edge types: {dict(edge_types)}")
# both-direction check: for a sample edge, is reverse present?
sample = edges[0]; s,t = sample["source"], sample["target"]
rev = any(e["source"]==t and e["target"]==s for e in edges)
p(f"    sample edge {s}->{t}; reverse present: {rev}")

# 4. embeddings
emb = glob.glob(r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\**\*.npz", recursive=True)
p(f"\n[4] .npz embeddings found: {len(emb)} -> {emb[:2]}")

# 5. TF-IDF-ish localization proxy on 15588: does the gold symbol rank high by naive token overlap
#    of problem-statement tokens vs node (name+source)?
TASKS = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl"
t = next(json.loads(l) for l in open(TASKS,encoding="utf-8") if json.loads(l)["instance_id"]=="fastapi_15588")
ps = t["problem_statement"].lower()
ps_toks = set(re.findall(r"[a-z_]{3,}", ps))
def score(n):
    blob = ((n.get("id") or "") + " " + (n.get("text") or "")).lower()
    toks = set(re.findall(r"[a-z_]{3,}", blob))
    return len(ps_toks & toks)
ranked = sorted(nodes, key=score, reverse=True)
gold = "ServerSentEvent"
pos = next((i for i,n in enumerate(ranked) if gold.lower() in (n.get("id") or "").lower()), -1)
p(f"\n[5] 15588 gold 'ServerSentEvent' rank by naive token-overlap: {pos+1 if pos>=0 else 'NOT FOUND'} of {len(nodes)}")
p(f"    top5 by overlap: {[ (n.get('id') or '')[:50] for n in ranked[:5] ]}")
OUT.close(); print("done")
