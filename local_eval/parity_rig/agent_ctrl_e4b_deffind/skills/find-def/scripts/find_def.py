"""find-def: deterministic definition locator. Prints files that DEFINE the given symbol.

One tool call. Greps `def <sym>` / `class <sym>` (and `<sym> =` for module-level assignments / properties)
across the repo source, ranks by definition kind, prints the defining file(s). No LLM, no guessing.
"""
import os
import re
import subprocess
import sys


def find_workspace():
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace"]
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace")); d = os.path.dirname(d)
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c,
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


def argsym():
    for a in sys.argv[1:]:
        a = a.strip()
        if a and a != "--" and not a.startswith("--"):
            return a
    return ""


def main():
    sym = argsym()
    if not sym:
        print("FIND-DEF: no symbol (usage: find_def.py <Symbol>)")
        return
    # strip dotted/paren noise: take the last identifier component
    m = re.search(r"[A-Za-z_]\w*$", sym.split("(")[0].strip().rstrip(":"))
    sym = m.group(0) if m else sym
    W = find_workspace()
    hits = []  # (kind_rank, file, lineno, line)
    patterns = [
        (0, re.compile(r"^\s*class\s+%s\b" % re.escape(sym))),
        (0, re.compile(r"^\s*(async\s+)?def\s+%s\b" % re.escape(sym))),
        (1, re.compile(r"^\s*%s\s*(:\s*[\w\[\], .\"']+)?\s*=" % re.escape(sym))),  # module/class attr
    ]
    for root, dirs, files in os.walk(W):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".tox", "node_modules", "build", "dist")]
        # skip test trees: definitions we want are in the package, not tests
        if os.path.basename(root) in ("tests", "test"):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines, 1):
                for rank, pat in patterns:
                    if pat.match(ln):
                        hits.append((rank, os.path.relpath(fp, W).replace(os.sep, "/"), i, ln.strip()[:100]))
                        break
    if not hits:
        print("FIND-DEF: no `def %s` / `class %s` found in the repo. Fall back to normal grep." % (sym, sym))
        return
    hits.sort(key=lambda h: (h[0], len(h[1]), h[1]))
    defs = [h for h in hits if h[0] == 0] or hits
    print("FIND-DEF: `%s` is DEFINED in:" % sym)
    for rank, f, i, ln in defs[:6]:
        print("  %s:%d   %s" % (f, i, ln))
    if len(defs) == 1:
        print("-> edit %s" % defs[0][1])
    else:
        print("-> %d candidates; pick the module matching the problem topic, edit there." % len(defs))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FIND-DEF: error %s: %s (fall back to grep)" % (type(e).__name__, e))
