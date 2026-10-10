"""Stage-1 data: FastAPI IDIOM corpus from official source (at a TRAIN-task base commit, no held-out leak).
Teaches 'how FastAPI is written' - validator/param/dependency/error conventions - as plain code windows.
NO SWE-bench task framing, so it cannot leak fix answers. Output: JSONL of {"text": <code window>}.

Design: pull function- and class-level chunks from the convention-heavy modules where bugs concentrate.
Each chunk is wrapped with a light natural-language frame so the LM learns 'this is idiomatic FastAPI X'."""
import ast, json, os, sys
from pathlib import Path

FA = Path(__file__).parent.parent / "local_eval" / "repos" / "fastapi" / "fastapi"
OUT = Path(__file__).parent / "data" / "stage1_fastapi_idioms.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

# convention-heavy modules (where FastAPI bugs concentrate per our inventory) + core idiom files
PRIORITY = ["dependencies/utils.py","dependencies/models.py","routing.py","params.py",
            "_compat.py","openapi/utils.py","exceptions.py","exception_handlers.py",
            "datastructures.py","applications.py","responses.py"]

def chunks_from_file(path, relname):
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception:
        return []
    lines = src.splitlines()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start+1)
            body = "\n".join(lines[start:end])
            if not (40 <= len(body) <= 4000):   # skip trivially short / huge
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            frame = (f"Idiomatic FastAPI source ({relname}) - {kind} `{node.name}`. "
                     f"This shows how FastAPI implements {kind}s: conventions, validation wiring, "
                     f"error handling, and naming to follow when editing this codebase.\n\n```python\n{body}\n```")
            out.append({"text": frame})
    return out

def main():
    all_chunks = []
    seen_files = []
    # priority files first, then the rest of the package
    rel_all = []
    for p in sorted(FA.rglob("*.py")):
        rel = str(p.relative_to(FA)).replace("\\","/")
        rel_all.append((rel, p))
    order = sorted(rel_all, key=lambda rp: (rp[0] not in PRIORITY, rp[0]))
    for rel, p in order:
        ch = chunks_from_file(p, rel)
        if ch:
            all_chunks += ch
            seen_files.append((rel, len(ch)))
    with open(OUT, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c) + "\n")
    print(f"wrote {len(all_chunks)} idiom chunks to {OUT}")
    toks = sum(len(c["text"].split()) for c in all_chunks)
    print(f"~{toks} whitespace-tokens total (~{toks*1.3:.0f} model tokens est.)")
    print("top files by chunk count:")
    for rel, n in sorted(seen_files, key=lambda x:-x[1])[:12]:
        print(f"  {n:3}  {rel}")

if __name__ == "__main__":
    main()
