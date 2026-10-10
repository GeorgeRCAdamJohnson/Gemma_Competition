"""
Probe: is the code-graph node set redundant enough that pattern-dedup saves
tokens, and does dedup preserve the fix-site symbols?

Decisive outputs (no model, no submission needed):
  1. dedup ratio   = distinct AST skeletons / total nodes   (compression ceiling)
  2. token proxy   = chars raw vs chars (distinct skeletons only)
  3. fix survival  = for each gold patch on this commit, are the edited symbols
                     in a UNIQUE skeleton (safe) or merged with twins (destroyed)?

Canonicalization: parse node['text'] -> AST -> rename all identifiers/args to
positional placeholders (v0,v1,... per scope) and blank out literals -> unparse.
Two nodes with the same skeleton are the "same pattern, different names".
"""
import ast, json, re, sys, io
from pathlib import Path
from collections import Counter, defaultdict

PROBE = Path(r".\Gemma\comp_files\probe")
TASKS = Path(r".\Gemma\comp_files\tasks.jsonl")

GRAPHS = {
    "fastapi":  "fastapi_016ab760faba1813ba235d5582a014a58bd2f417.json",
    "rich":     "rich_fc41075a3206d2a5fd846c6f41c4d2becab814fa.json",
    "requests": "requests_6f205ff422bccd5e4c4fc0b64c5f3e7df5181db6.json",
}
# commit each graph is at (from the filename)
COMMIT = {
    "fastapi":  "016ab760faba1813ba235d5582a014a58bd2f417",
    "rich":     "fc41075a3206d2a5fd846c6f41c4d2becab814fa",
    "requests": "6f205ff422bccd5e4c4fc0b64c5f3e7df5181db6",
}


class Canon(ast.NodeTransformer):
    """Rename identifiers to positional placeholders, blank literals.
    Produces a structural skeleton: same shape+ops => same string."""
    def __init__(self):
        self.names = {}
    def _ph(self, orig):
        if orig not in self.names:
            self.names[orig] = f"v{len(self.names)}"
        return self.names[orig]
    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id=self._ph(node.id), ctx=node.ctx), node)
    def visit_arg(self, node):
        node.arg = self._ph(node.arg)
        node.annotation = None
        return node
    def visit_FunctionDef(self, node):
        node.name = "_f"
        node.decorator_list = []
        node.returns = None
        self.generic_visit(node)
        return node
    def visit_AsyncFunctionDef(self, node):
        node.name = "_f"; node.decorator_list=[]; node.returns=None
        self.generic_visit(node); return node
    def visit_ClassDef(self, node):
        node.name = "_C"
        node.decorator_list = []
        self.generic_visit(node)
        return node
    def visit_Attribute(self, node):
        self.generic_visit(node)
        node.attr = "_a"
        return node
    def visit_Constant(self, node):
        # blank the literal value, keep the type shape
        return ast.copy_location(ast.Constant(value=0 if isinstance(node.value,(int,float)) else ""), node)


def skeleton(text: str):
    """Return canonical skeleton string, or None if unparseable."""
    text = text.strip()
    if not text:
        return None
    # node text may be a bare class/def; try as-is then dedented
    for candidate in (text, _dedent(text)):
        try:
            tree = ast.parse(candidate)
        except SyntaxError:
            continue
        try:
            Canon().visit(tree)
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except Exception:
            return None
    return None


def _dedent(t):
    lines = t.splitlines()
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    if not indents:
        return t
    m = min(indents)
    return "\n".join(l[m:] if len(l) >= m else l for l in lines)


def load_tasks_for(repo):
    """gold patches for this repo at the probe commit (and all commits)."""
    out = []
    for line in open(TASKS, encoding="utf-8"):
        t = json.loads(line)
        if t["repo"].split("/")[-1] == repo:
            out.append(t)
    return out


def patched_symbols(patch_text):
    """Rough: pull the file paths + def/class names touched by a unified diff.
    We can't map to exact node ids without the repo tree, so we extract the
    function/class names that appear on changed hunks as a proxy for fix-site."""
    syms = set()
    for line in patch_text.splitlines():
        # hunk header often shows the enclosing def/class: @@ ... @@ def foo(
        m = re.search(r'@@.*@@\s*(?:async\s+)?(?:def|class)\s+(\w+)', line)
        if m:
            syms.add(m.group(1))
        # added/removed def/class lines
        m2 = re.match(r'[+\-]\s*(?:async\s+)?(?:def|class)\s+(\w+)', line)
        if m2:
            syms.add(m2.group(1))
    return syms


def run():
    out = io.open(r".\Gemma\probe_results.txt", "w", encoding="utf-8")
    def p(*a):
        s = " ".join(str(x) for x in a)
        print(s); out.write(s + "\n")

    for repo, fname in GRAPHS.items():
        path = PROBE / fname
        if not path.exists():
            p(f"[{repo}] MISSING {fname}"); continue
        g = json.load(open(path, encoding="utf-8"))
        nodes = g["nodes"]
        texts = [(n["id"], n.get("text", "")) for n in nodes]
        total = len(texts)

        skels = {}
        unparse_fail = 0
        skel_members = defaultdict(list)
        for nid, txt in texts:
            sk = skeleton(txt)
            if sk is None:
                unparse_fail += 1
                sk = "<<RAW>>" + txt  # treat unparseable as unique-by-text
            skels[nid] = sk
            skel_members[sk].append(nid)

        distinct = len(set(skels.values()))
        raw_chars = sum(len(t) for _, t in texts)
        distinct_chars = sum(len(sk) for sk in set(skels.values()))

        p("=" * 64)
        p(f"[{repo}]  {fname[:28]}...")
        p(f"  nodes total           : {total}")
        p(f"  distinct skeletons    : {distinct}")
        p(f"  dedup ratio           : {total/max(distinct,1):.2f}x  "
          f"(distinct = {100*distinct/total:.1f}% of nodes)")
        p(f"  unparseable nodes     : {unparse_fail} ({100*unparse_fail/total:.1f}%)")
        p(f"  raw text chars        : {raw_chars:,}")
        p(f"  distinct-skel chars   : {distinct_chars:,}  "
          f"(char saving {100*(1-distinct_chars/max(raw_chars,1)):.1f}%)")

        # biggest duplicate clusters
        big = sorted(skel_members.items(), key=lambda kv: -len(kv[1]))[:5]
        p(f"  top duplicate clusters (count : sample ids):")
        for sk, ids in big:
            if len(ids) < 2:
                continue
            p(f"     {len(ids):4d}  : {ids[0][:46]}  (+{len(ids)-1} twins)")

        # ---- fix-site survival ----
        node_ids = {nid for nid, _ in texts}
        node_short = defaultdict(list)  # last dotted segment -> node ids
        for nid in node_ids:
            node_short[nid.split(".")[-1]].append(nid)

        tasks = [t for t in load_tasks_for(repo) if t["base_commit"] == COMMIT[repo]]
        p(f"  gold tasks at THIS commit: {len(tasks)}")
        checked = unique_safe = merged = unmatched = 0
        for t in tasks:
            syms = patched_symbols(t["patch"])
            for s in syms:
                cands = node_short.get(s, [])
                if not cands:
                    unmatched += 1
                    continue
                checked += 1
                # is at least one candidate node in a singleton skeleton?
                safe = any(len(skel_members[skels[c]]) == 1 for c in cands)
                if safe:
                    unique_safe += 1
                else:
                    merged += 1
        p(f"  fix-site symbols checked : {checked}  "
          f"(unmatched-in-graph {unmatched})")
        if checked:
            p(f"     in UNIQUE skeleton (safe) : {unique_safe} "
              f"({100*unique_safe/checked:.0f}%)")
            p(f"     MERGED with twins (risk)  : {merged} "
              f"({100*merged/checked:.0f}%)")
    out.close()
    print("\n(results also written to Gemma\\probe_results.txt)")


if __name__ == "__main__":
    run()
