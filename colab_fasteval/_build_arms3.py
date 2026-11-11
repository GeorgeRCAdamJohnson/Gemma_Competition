"""Batch 3 arms, built on H_hygiene (batch-1 provisional winner). One change each; exact-once replacements; LF only.
  C_pack1    control (84f904c63afd)
  H_hygiene  base (eccf4b1af3f3)
  HT5        H + sampling temperature 0.5 (was 0.2; fixer and verifier share sampling.yaml): more diverse attempts on
             flaky tasks, where solves depend on the draw
  HG4        H + the gate runs up to 4 existing test files covering the edit (was 2): more regressions caught, more
             specific failure text handed to the retry
"""
import hashlib
import shutil
from pathlib import Path

A1, A3 = Path("colab_fasteval/arms"), Path("colab_fasteval/arms3")


def sub(path, old, new):
    b = path.read_bytes().decode("utf-8")
    assert b.count(old) == 1, f"{path}: {b.count(old)} matches for {old[:70]!r}"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if A3.exists():
    shutil.rmtree(A3)
A3.mkdir()
for a in ("C_pack1", "H_hygiene"):
    shutil.copytree(A1 / a, A3 / a)
assert fp(A3 / "C_pack1") == "84f904c63afd" and fp(A3 / "H_hygiene") == "eccf4b1af3f3"
shutil.copytree(A1 / "H_hygiene", A3 / "HT5")
sub(A3 / "HT5" / "sub_agents" / "configs" / "sampling.yaml", "temperature: 0.2\n", "temperature: 0.5\n")
shutil.copytree(A1 / "H_hygiene", A3 / "HG4")
sub(A3 / "HG4" / "skills" / "submit-gate" / "scripts" / "check.py", "    picked = picked[:2]\n", "    picked = picked[:4]\n")
for d in sorted(A3.iterdir()):
    print(f"{d.name:10s} sha {fp(d)}")
