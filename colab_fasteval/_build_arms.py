"""Build the E4B A/B arms from the exact pack-1 bytes (colab_fasteval/_smoke_inputs/agent_pack1, sha 84f904c63afd).
Each arm changes ONE thing vs pack 1. Every replacement must match exactly once; files are written LF-only, no BOM.

  C_pack1    control: pack 1 byte-identical
  L_lean     fixer declares only run_command / read_file / edit_file (drops get_status, write_file, 3 graph tools);
             fixer.md loses the get_status "budget oracle" and its triggers are re-based on calls MADE (same
             28-call fake budget, which every arm keeps)
  H_hygiene  gate mechanics: undo reverts ALL non-test changes (not only .py), undo checks git apply -R and falls
             back to checkout, empty-patch message points at the python-replace fallback; fixer.md bans
             doc/config edits
  R_reads    fixer.md read discipline: locate with grep -n, read only spans with sed -n (<= 80 lines), never
             read_file a whole file, never re-read a span already seen
"""
import hashlib
from pathlib import Path

A = Path("colab_fasteval/arms")


def sub(path, old, new, count=1):
    b = path.read_bytes().decode("utf-8")
    n = b.count(old)
    assert n == count, f"{path}: expected {count} match(es), got {n}: {old[:70]!r}"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


# ---------------- C_pack1: untouched ----------------
assert fp(A / "C_pack1") == "84f904c63afd", fp(A / "C_pack1")

# ---------------- L_lean ----------------
L = A / "L_lean" / "sub_agents"
sub(L / "fixer.yaml",
    "  - run_command\n  - read_file\n  - edit_file\n  - write_file\n  - get_status\n  - get_code_neighbors\n"
    "  - search_similar_code\n  - get_code_subgraph\n",
    "  - run_command\n  - read_file\n  - edit_file\n")
f = L / "prompts" / "fixer.md"
t = f.read_text(encoding="utf-8")
i, j = t.index("## THE BUDGET ORACLE"), t.index("## COMMIT-BY-REMAINING")
t = t[:i] + t[j:]
f.write_text(t, encoding="utf-8", newline="\n")
sub(f, "## COMMIT-BY-REMAINING — the rule that decides whether you score",
    "## COMMIT-BY-COUNT — the rule that decides whether you score")
sub(f, "After EVERY `get_status()`, apply this trigger:\n"
       "- **tool_calls_remaining <= 14** -> you are past locating.",
    "Count the tool calls you have made. Apply this trigger after EVERY call:\n"
    "- **14 or more calls made** -> you are past locating.")
sub(f, "- **tool_calls_remaining <= 7**  -> you are in the danger zone.",
    "- **21 or more calls made** -> you are in the danger zone.")
sub(f, "- **tool_calls_remaining <= 3**  -> emit the edit immediately. Nothing else.",
    "- **25 or more calls made** -> emit the edit immediately. Nothing else.")
sub(f, "Find the code with 1 `run_command` grep, or `read_file` for a whole file. Then call `get_status` (free) to see where you stand.",
    "Find the code with 1 `run_command` grep, or `read_file` for a whole file.")
sub(f, "- NEVER end your turn saying you are out of calls and cannot edit. That is always wrong: check `get_status` (free) and bank the edit you can still make.",
    "- NEVER end your turn saying you are out of calls and cannot edit. That is always wrong: bank the edit you can still make.")
assert "get_status" not in f.read_text(encoding="utf-8"), "L_lean fixer.md still mentions get_status"

# ---------------- H_hygiene ----------------
H = A / "H_hygiene"
c = H / "skills" / "submit-gate" / "scripts" / "check.py"
sub(c, 'print("REJECTED: no change in the repo - your edit did not land. Re-apply it with edit_file.")',
    'print("REJECTED: no change in the repo - your edit did not land. Re-apply it with ONE run_command python '
    'replace: read the file, assert OLD in s, write s.replace(OLD, NEW, 1), print OK.")')
# undo/attempt bookkeeping covers every non-test, non-harness change (toml/md/yaml/cfg edits were surviving the undo)
sub(c, '    return [n.strip() for n in names.splitlines() if n.strip().endswith(".py") and not is_test(n.strip())\n'
       '            and n.strip() not in harness_files and not os.path.basename(n).startswith(".adk_exec_")]',
    '    return [n.strip() for n in names.splitlines() if n.strip() and not is_test(n.strip())\n'
    '            and n.strip() not in harness_files and not os.path.basename(n).startswith(".adk_exec_")]')
sub(c, '        if src and os.path.getsize(dpath) > 0:\n'
       '            sh("git apply -R %s" % dpath)  # undo this attempt: files back to the original text\n',
    '        if src and os.path.getsize(dpath) > 0:\n'
    '            rcu, _ = sh("git apply -R %s" % dpath)  # undo this attempt: files back to the original text\n'
    '            if rcu != 0:  # reverse failed: force the files back to the baseline instead of leaving a dirty tree\n'
    '                sh("git checkout %s -- %s" % (base, " ".join(src)))\n')
f = H / "sub_agents" / "prompts" / "fixer.md"
sub(f, "- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.",
    "- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.\n"
    "- Edit ONLY Python source files (.py). NEVER edit docs or metadata (*.md, *.rst, *.toml, *.yaml, *.cfg, *.cff, LICENSE, CHANGELOG): the gate rejects those attempts and they waste a retry.")

# ---------------- R_reads ----------------
f = A / "R_reads" / "sub_agents" / "prompts" / "fixer.md"
sub(f, "## Workflow (tight)",
    "## READ ONLY WHAT YOU NEED (every read stays in your context for the rest of the task)\n"
    "- Do NOT `read_file` a whole file. Locate first with `run_command` `grep -n '<symbol>' <file>`, then read ONLY the\n"
    "  span you need with `run_command` `sed -n 'A,Bp' <file>` (at most 80 lines per read).\n"
    "- NEVER re-read a span you already have: scroll back to it. Read a NEW span only when you need lines you have not seen.\n"
    "- If an edit fails because old_string was not found, `sed -n` the few exact lines around the anchor (not the whole file).\n\n"
    "## Workflow (tight)")
sub(f, "Find the code with 1 `run_command` grep, or `read_file` for a whole file.",
    "Find the code with 1 `run_command` grep, then `sed -n` just that span.")

for d in sorted(A.iterdir()):
    print(f"{d.name:10s} sha {fp(d)}")
