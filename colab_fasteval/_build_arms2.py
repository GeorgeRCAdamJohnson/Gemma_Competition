"""Batch 2 arms (built from batch-1 arm bytes; every replacement must match exactly once; LF only).
  C_pack1    = batch-1 control, unchanged (84f904c63afd)
  H_hygiene  = batch-1 winner, unchanged (eccf4b1af3f3)
  HR         = H_hygiene + R_reads' fixer.md read-discipline edits (the only batch-1 R change)
  HR4        = HR + 4 attempts instead of 3 (LoopAgent max_iterations AND the gate's MAX_ATTEMPTS, kept equal)
"""
import hashlib
import shutil
from pathlib import Path

A1 = Path("colab_fasteval/arms")
A2 = Path("colab_fasteval/arms2")


def sub(path, old, new):
    b = path.read_bytes().decode("utf-8")
    assert b.count(old) == 1, f"{path}: {b.count(old)} matches for {old[:70]!r}"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if A2.exists():
    shutil.rmtree(A2)
A2.mkdir()
for a in ("C_pack1", "H_hygiene"):
    shutil.copytree(A1 / a, A2 / a)
assert fp(A2 / "C_pack1") == "84f904c63afd" and fp(A2 / "H_hygiene") == "eccf4b1af3f3"

# HR: R's fixer.md diff applied onto H's fixer.md (H only appended one Hard-rules line, so R's two edits still match)
shutil.copytree(A1 / "H_hygiene", A2 / "HR")
f = A2 / "HR" / "sub_agents" / "prompts" / "fixer.md"
sub(f, "## Workflow (tight)",
    "## READ ONLY WHAT YOU NEED (every read stays in your context for the rest of the task)\n"
    "- Do NOT `read_file` a whole file. Locate first with `run_command` `grep -n '<symbol>' <file>`, then read ONLY the\n"
    "  span you need with `run_command` `sed -n 'A,Bp' <file>` (at most 80 lines per read).\n"
    "- NEVER re-read a span you already have: scroll back to it. Read a NEW span only when you need lines you have not seen.\n"
    "- If an edit fails because old_string was not found, `sed -n` the few exact lines around the anchor (not the whole file).\n\n"
    "## Workflow (tight)")
sub(f, "Find the code with 1 `run_command` grep, or `read_file` for a whole file.",
    "Find the code with 1 `run_command` grep, then `sed -n` just that span.")
# the R block must be byte-identical to R_reads' (same text, same position relative to the workflow header)
r = (A1 / "R_reads" / "sub_agents" / "prompts" / "fixer.md").read_text(encoding="utf-8")
blk = r[r.index("## READ ONLY WHAT YOU NEED"):r.index("## Workflow (tight)")]
assert blk in f.read_text(encoding="utf-8")

# HR4: one more attempt (both counters, so the gate's 'attempt n of N' / restore-best logic stays consistent)
shutil.copytree(A2 / "HR", A2 / "HR4")
sub(A2 / "HR4" / "agent.yaml", "max_iterations: 3\n", "max_iterations: 4\n")
sub(A2 / "HR4" / "agent.yaml", "retries fresh (max 3)", "retries fresh (max 4)")
sub(A2 / "HR4" / "skills" / "submit-gate" / "scripts" / "check.py", "MAX_ATTEMPTS = 3\n", "MAX_ATTEMPTS = 4\n")

for d in sorted(A2.iterdir()):
    print(f"{d.name:10s} sha {fp(d)}")
