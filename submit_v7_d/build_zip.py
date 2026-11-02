"""Assemble out/submission.zip for candidate D.

D = v6w + thinking_budget 4096 + two prompt paragraphs (batched lookups, edit_file failure recovery,
written in our own wording) + agent name swe_agent (matches the 0.22 package). Sampling is otherwise v6w's.

Entries use forward slashes and mirror the layout of the v6w zip. After building, every entry is
compared byte-for-byte against the v6w zip and the diffs are printed.
"""
import difflib
import hashlib
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "out" / "submission"
OUT = HERE / "out" / "submission.zip"
BASE = HERE.parent / "submit_v6w" / "out_v6w" / "submission.zip"

DIRS = ["configs/", "prompts/"]
FILES = ["agent.yaml", "eval_config.yaml", "configs/sampling.yaml", "prompts/system.md"]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for d in DIRS:
        z.writestr(zipfile.ZipInfo(d), b"")
    for f in FILES:
        z.write(SRC / f, f)

with zipfile.ZipFile(OUT) as new, zipfile.ZipFile(BASE) as old:
    assert new.testzip() is None
    n_names, o_names = sorted(new.namelist()), sorted(old.namelist())
    print("entries:", n_names)
    assert n_names == o_names, f"entry mismatch: {n_names} vs {o_names}"
    for name in n_names:
        if name.endswith("/"):
            continue
        a, b = old.read(name), new.read(name)
        if a == b:
            print(f"  identical  {name}  ({len(b)} bytes)")
        else:
            print(f"  CHANGED    {name}  ({len(a)} -> {len(b)} bytes)")
            for line in difflib.unified_diff(
                a.decode().splitlines(), b.decode().splitlines(), "v6w", "D", lineterm="", n=0
            ):
                print("     ", line)
print("wrote", OUT, OUT.stat().st_size, "bytes, sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())
