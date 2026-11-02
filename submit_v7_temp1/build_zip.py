"""Assemble out/submission.zip for v7 (= v6w with temperature 1.0 / top_k 64 as the only change).

Entries use forward slashes and mirror the layout of the v6w zip. After building, every entry is
compared byte-for-byte against the v6w zip so the diff is exactly configs/sampling.yaml.
"""
import difflib
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
                a.decode().splitlines(), b.decode().splitlines(), "v6w", "v7", lineterm=""
            ):
                print("     ", line)
print("wrote", OUT, OUT.stat().st_size, "bytes")
