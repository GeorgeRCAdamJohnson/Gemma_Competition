"""Batch 6 (Colab, swing-task test): pack 1 vs pack 1 + `locate` as a SECOND OPINION before the first edit.
  C_pack1  84f904c63afd
  L_loc    pack 1 + skills/locate (v3 offline: top5 74%, 6/7 swing tasks in top5) declared on the FIXER, plus one rule:
           before the first edit run locate; if the intended file is in its list -> proceed; if NOT -> re-read the problem and
           the #1 candidate's definition before deciding. (Second opinion, not an order: v3 top1 is only 41%.)
"""
import hashlib
import shutil
from pathlib import Path

A1, A6 = Path("colab_fasteval/arms"), Path("colab_fasteval/arms6")
SK = Path("colab_fasteval/skill_locate")


def sub(path, old, new):
    b = path.read_bytes().decode("utf-8")
    assert b.count(old) == 1, f"{path}: {b.count(old)} matches for {old[:60]!r}"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if A6.exists():
    shutil.rmtree(A6)
A6.mkdir()
shutil.copytree(A1 / "C_pack1", A6 / "C_pack1")
assert fp(A6 / "C_pack1") == "84f904c63afd"
L = A6 / "L_loc"
shutil.copytree(A1 / "C_pack1", L)
(L / "skills" / "locate" / "scripts").mkdir(parents=True)
for rel in ("SKILL.md", "scripts/locate.py"):
    (L / "skills" / "locate" / rel).write_bytes((SK / rel).read_bytes().replace(b"\r\n", b"\n"))
sub(L / "sub_agents" / "fixer.yaml", "  - get_code_subgraph\n",
    "  - get_code_subgraph\nskills:\n  - skills/locate\n")
f = L / "sub_agents" / "prompts" / "fixer.md"
sub(f, "2. BEFORE the edit: grep your anchor",
    "2. SECOND OPINION (once, before your FIRST edit): call `run_skill_script` with skill_name \"locate\", file_path "
    "\"scripts/locate.py\", args {\"q\": \"<the class/function/attribute names, error text and file names from the "
    "problem, copied exactly>\"}. It lists the files that DEFINE those names. If the file you intend to edit is in its list, "
    "proceed. If it is NOT, re-read the problem and `sed -n` the #1 candidate's definition before you decide which file to "
    "edit. Do not call it again.\n"
    "3. BEFORE the edit: grep your anchor")
# renumber the later workflow steps (2..5 -> 3..6) so the list stays consistent
for old, new in (("3. You do NOT submit", "4. You do NOT submit"), ("4. A VERIFIER agent", "5. A VERIFIER agent"),
                 ("5. RETRY RULE", "6. RETRY RULE")):
    sub(f, old, new)
for d in sorted(A6.iterdir()):
    print(f"{d.name:8s} sha {fp(d)}")
