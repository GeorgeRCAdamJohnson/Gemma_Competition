"""How many prompt characters does each declared fixer tool add to EVERY model turn? (function declaration =
name + docstring + signature, built by ADK from the swegemma tool functions). Also: does the harness task prompt
advertise only DECLARED tools (build_agent_prompt(declared_tools=...))?"""
import ast
import re
from pathlib import Path

T = Path("harness_src/x/swegemma")
want = ["run_command", "read_file", "edit_file", "write_file", "get_status", "get_code_neighbors",
        "search_similar_code", "get_code_subgraph"]
found = {}
for p in T.rglob("*.py"):
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in want and n.name not in found:
            doc = ast.get_docstring(n) or ""
            args = [a.arg for a in n.args.args if a.arg not in ("self", "tool_context", "ctx")]
            found[n.name] = (len(doc) + len(n.name) + sum(len(a) + 30 for a in args), p.relative_to(T).as_posix(), args)
tot = 0
for w in want:
    if w in found:
        sz, f, args = found[w]
        tot += sz
        print(f"  {w:20s} ~{sz:5d} chars  ({f}) args={args}")
    else:
        print(f"  {w:20s} not found as a function")
print(f"  all 8 fixer tools ~{tot} chars (~{tot//4} tokens) per turn")
dead = sum(found[w][0] for w in ("get_code_neighbors", "search_similar_code", "get_code_subgraph", "write_file", "get_status") if w in found)
print(f"  graph x3 + write_file + get_status ~{dead} chars (~{dead//4} tokens) per turn")
src = (T / "harness" / "agent_runner.py").read_text(encoding="utf-8")
i = src.find("def build_agent_prompt")
seg = src[i:i + 9000]
for m in re.finditer(r".{0,120}declared_tools.{0,160}", seg):
    print("  prompt:", m.group(0).replace("\n", " ")[:260])
