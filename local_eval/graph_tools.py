"""Local reimplementation of the competition harness code-intelligence tools, backed by the per-task
NetworkX node-link graphs in comp_files/graphs/<repo>_<commit>.json.

================================================================================================
!!! DELIBERATELY CRIPPLED TO MATCH swegemma 0.2.7 (the SCORED harness). DO NOT "FIX". !!!
================================================================================================
The competition README advertises a richer tool than ships. A forum audit of the swegemma 0.2.7 wheel
(cross-checked against our own comp_files/graphs on 2026-10-04 — see GEMMA_EXPERIMENT_LOG) found the REAL
tool is far more limited than its docs. We MATCH the real behavior exactly, because a local tool that is
MORE capable than the scored one produces an eval that LIES: a localization lever validated here would
then fail at scoring. (Same class of bug as the GGUF base-mismatch: match the real artifact or the local
result is worthless.)

VERIFIED-REAL behavior we replicate (and the README lies we must NOT implement):
  get_code_neighbors(node, edge_type, max_neighbors=50):
    * EXACT full-dotted-id match ONLY. The README's 4-tier resolver (exact -> suffix -> case-insensitive
      -> substring) is NOT in 0.2.7. If the agent doesn't pass the FULL id (e.g. 'fastapi.sse.ServerSentEvent'),
      it gets []. We DO NOT implement suffix/ci/substring fallback. (verified: ids are 100% dotted paths.)
    * edge_type is an exact lowercase string match; EVERY stored edge is type 'calls'. 'CALLS'/'DEFINED_IN'/
      'IMPORTS' all return []. (verified: edge types = {'calls'} only.)
    * neighbors are stored BOTH directions (caller & callee indistinguishable), sorted ALPHABETICALLY and
      cut at max_neighbors (default 50) -> the first 50 alphabetical, which can DROP real callers.
    * coverage is sparse: ~14-21% of real call pairs; NO self.m()/super() call edges; async defs under-
      represented in the call graph. An empty result can mean "bad lookup" OR "missing edge", not "no caller".
  search_similar_code(query, k): the offline wheel looks a stored vector up by node id / node source;
    free-text / fuzzy queries return []. We approximate with EXACT-id / exact-source match only (NOT fuzzy).
  get_code_subgraph(node, depth): neighborhood via the same exact-id + 'calls'-only edges.
get_node_text(symbol): EXACT-id only (bonus: localized symbol -> its source).

If a NEWER wheel restores the richer resolver, update this module AND the log entry together.
"""
import json, os, functools

GRAPHS_DIR = os.path.join(os.path.dirname(__file__), "..", "comp_files", "graphs")

@functools.lru_cache(maxsize=8)
def _load_graph(repo_short, base_commit):
    fp = os.path.join(GRAPHS_DIR, f"{repo_short}_{base_commit}.json")
    if not os.path.exists(fp):
        return None
    g = json.load(open(fp, encoding="utf-8"))
    nodes = {}
    for n in g.get("nodes", []):
        key = n.get("id") or n.get("name")
        if key:
            nodes[key] = n
    out_edges = {}; in_edges = {}
    for e in g.get("edges", []):
        s, t, et = e.get("source"), e.get("target"), e.get("type")
        out_edges.setdefault(s, []).append((t, et))
        in_edges.setdefault(t, []).append((s, et))
    return {"nodes": nodes, "out": out_edges, "in": in_edges}


def _resolve(nodes, name):
    """EXACT full-dotted-id match ONLY — matches swegemma 0.2.7. The README's suffix/case-insensitive/
    substring tiers are NOT implemented in the scored harness, so we DO NOT implement them here. A short
    name (e.g. 'ServerSentEvent' instead of 'fastapi.sse.ServerSentEvent') returns None, exactly as the
    real tool returns []. (See module docstring: crippled on purpose; do not add fallbacks.)"""
    return name if name in nodes else None


class GraphTools:
    def __init__(self, repo_short, base_commit):
        self.g = _load_graph(repo_short, base_commit)
        self.available = self.g is not None

    def get_code_neighbors(self, node, edge_type=None, max_neighbors=50):
        if not self.available:
            return {"status": "error", "error": "no graph for this task"}
        key = _resolve(self.g["nodes"], str(node))
        if not key:
            return {"status": "ok", "node": node, "neighbors": [], "count": 0, "note": "symbol not found"}
        outs = self.g["out"].get(key, []); ins = self.g["in"].get(key, [])
        def fil(pairs):
            return [sym for sym, et in pairs if (edge_type is None or et == edge_type)]
        neigh = {"outgoing": fil(outs)[:max_neighbors], "incoming": fil(ins)[:max_neighbors]}
        return {"status": "ok", "node": key,
                "neighbors": neigh,
                "count": len(neigh["outgoing"]) + len(neigh["incoming"])}

    def search_similar_code(self, query, k=10):
        """CRIPPLED to match swegemma 0.2.7: the offline wheel looks a stored vector up by node id (or
        exact node source) and returns [] for free-text/fuzzy queries. We therefore match EXACT id only
        (and exact-id prefix of the dotted path), NOT fuzzy name/suffix/substring. Passing a bare short
        name or an NL sentence returns []. Do NOT re-add fuzzy ranking — it would make local eval overstate
        this tool vs the scored harness (see module docstring)."""
        if not self.available:
            return {"status": "error", "error": "no graph for this task"}
        q = str(query).strip()
        # exact id match only (the real tool's node-id vector lookup)
        if q in self.g["nodes"]:
            return {"status": "ok", "query": query, "results": [q], "count": 1}
        return {"status": "ok", "query": query, "results": [], "count": 0,
                "note": "no exact-id match (0.2.7 does not do fuzzy/NL search; pass a full dotted id)"}

    def get_code_subgraph(self, node, depth=1):
        if not self.available:
            return {"status": "error", "error": "no graph for this task"}
        key = _resolve(self.g["nodes"], str(node))
        if not key:
            return {"status": "ok", "node": node, "subgraph": [], "note": "symbol not found"}
        seen = {key}; frontier = {key}
        for _ in range(max(1, int(depth))):
            nxt = set()
            for s in frontier:
                for t, _et in self.g["out"].get(s, []): nxt.add(t)
                for u, _et in self.g["in"].get(s, []): nxt.add(u)
            seen |= nxt; frontier = nxt
        return {"status": "ok", "node": key, "subgraph": sorted(seen)[:60], "count": len(seen)}

    def get_node_text(self, symbol):
        """Return the source text of a symbol (bonus: localized symbol -> its code)."""
        if not self.available:
            return None
        key = _resolve(self.g["nodes"], str(symbol))
        if not key:
            return None
        return self.g["nodes"][key].get("text")
