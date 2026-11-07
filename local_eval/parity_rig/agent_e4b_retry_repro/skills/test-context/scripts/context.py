"""test-context: deterministic context for writing a reproduction test (no LLM). Prints <= ~5 KB."""
import ast
import os
import re
import subprocess
import sys


def find_workspace():
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace"]
    home = os.environ.get("HOME", "")
    if home:
        cands.append(os.path.join(os.path.dirname(home.rstrip("/")), "workspace"))
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace"))
        d = os.path.dirname(d)
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


W = find_workspace()


def sigs(path, limit=60):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception as e:
        return ["  (could not parse: %s)" % e]
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append("  def %s(%s)  # line %d" % (node.name, ast.unparse(node.args)[:120], node.lineno))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)[:80]
            out.append("  class %s(%s)  # line %d" % (node.name, bases, node.lineno))
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append("      def %s(%s)" % (b.name, ast.unparse(b.args)[:110]))
        if len(out) >= limit:
            out.append("  ...")
            break
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: context.py <source_file_path>")
        return
    rel = sys.argv[1].strip().lstrip("/")
    if rel.startswith("workspace/"):
        rel = rel[len("workspace/"):]
    src = os.path.join(W, rel)
    if not os.path.exists(src):
        print("not found: %s (paths are relative to the repo root)" % rel)
        return
    dotted = os.path.splitext(rel)[0].replace("/", ".")
    print("== import path for %s:\n  import %s   /   from %s import <name>" % (rel, dotted, dotted))
    print("== classes/functions in %s:" % rel)
    print("\n".join(sigs(src)))
    stem = os.path.splitext(os.path.basename(rel))[0].lstrip("_")
    tests = []
    for d in ("tests", "test"):
        td = os.path.join(W, d)
        if os.path.isdir(td):
            for f in sorted(os.listdir(td)):
                if f.endswith(".py") and re.search(r"test_?%s(\.py|_)" % re.escape(stem), f):
                    tests.append(os.path.join(d, f))
    if not tests:
        r = subprocess.run("grep -rlE '(from|import) +%s\\b' tests test --include='test_*.py' 2>/dev/null | head -2" % re.escape(dotted),
                           shell=True, cwd=W, capture_output=True, text=True)
        tests = [t for t in r.stdout.split() if t]
    if not tests:
        print("== no existing test file found for %s" % rel)
        return
    t = tests[0]
    text = open(os.path.join(W, t), encoding="utf-8", errors="replace").read()
    imports = [l for l in text.splitlines() if re.match(r"^(from|import) ", l)][:25]
    print("== existing test file %s - its imports (copy this style):" % t)
    print("\n".join("  " + l for l in imports))
    names = re.findall(r"^def (test_\w+)", text, re.M)
    print("== %d tests in it, e.g.: %s" % (len(names), ", ".join(names[:12])))
    m = re.search(r"^def test_\w+\(.*?(?=^def |\Z)", text, re.M | re.S)
    if m:
        body = "\n".join(m.group(0).rstrip().splitlines()[:30])
        print("== example test from %s:\n%s" % (t, body))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("test-context error: %s: %s" % (type(e).__name__, e))
