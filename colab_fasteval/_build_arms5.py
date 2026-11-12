"""Batch 5 arms: the two best single levers on PACK 1 (H is closed), plus their combination.
  C_pack1  84f904c63afd (control)
  R_reads  4089b91f730f (pooled +1.10, n 10, no erosions)
  T5       pack 1 + temperature 0.5 (HT5 was +0.83, n 12, on top of the null H)
  RT5      R_reads + temperature 0.5
"""
import hashlib
import shutil
from pathlib import Path

A1, A5 = Path("colab_fasteval/arms"), Path("colab_fasteval/arms5")


def sub(path, old, new):
    b = path.read_bytes().decode("utf-8")
    assert b.count(old) == 1, f"{path}: {b.count(old)} matches"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if A5.exists():
    shutil.rmtree(A5)
A5.mkdir()
for a in ("C_pack1", "R_reads"):
    shutil.copytree(A1 / a, A5 / a)
assert fp(A5 / "C_pack1") == "84f904c63afd" and fp(A5 / "R_reads") == "4089b91f730f"
for name, base in (("T5", "C_pack1"), ("RT5", "R_reads")):
    shutil.copytree(A1 / base, A5 / name)
    sub(A5 / name / "sub_agents" / "configs" / "sampling.yaml", "temperature: 0.2\n", "temperature: 0.5\n")
for d in sorted(A5.iterdir()):
    print(f"{d.name:8s} sha {fp(d)}")
