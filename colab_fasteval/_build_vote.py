"""Build the VOTE arm (colab_fasteval/arms4/V_vote) from pack 1 (C_pack1, 84f904c63afd) + control copy.

Mechanism (gate check.py _finalize): an ACCEPTED attempt is no longer submitted immediately. It is recorded (normalized diff
= the +/- lines with whitespace removed, plus file names), UNDONE, and the fixer re-solves independently. As soon as two
ACCEPTED attempts have the same normalized diff, that diff is restored and submitted. After MAX_ATTEMPTS without agreement:
restore the most frequent ACCEPTED diff (tie -> earliest); if none was accepted, the old best-score restore. Rejections behave
as in pack 1. fixer.md: a CONFIRM retry means "solve again independently, the same way you judge best" (not "be different").
"""
import hashlib
import shutil
from pathlib import Path

A1, A4 = Path("colab_fasteval/arms"), Path("colab_fasteval/arms4")


def sub(path, old, new):
    b = path.read_bytes().decode("utf-8")
    assert b.count(old) == 1, f"{path}: {b.count(old)} matches for {old[:70]!r}"
    path.write_bytes(b.replace(old, new).encode("utf-8"))


def fp(d):
    fs = {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*") if p.is_file()}
    for k, v in fs.items():
        assert b"\r" not in v and not v.startswith(b"\xef\xbb\xbf"), f"{d}/{k}: CRLF/BOM"
    return hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]


if A4.exists():
    shutil.rmtree(A4)
A4.mkdir()
shutil.copytree(A1 / "C_pack1", A4 / "C_pack1")
assert fp(A4 / "C_pack1") == "84f904c63afd"
V = A4 / "V_vote"
shutil.copytree(A1 / "C_pack1", V)
c = V / "skills" / "submit-gate" / "scripts" / "check.py"

sub(c, 'def _finalize(msg):\n',
    'def _norm_diff(path):\n'
    '    """Comparable form of an attempt: changed file names + added/removed lines with ALL whitespace removed."""\n'
    '    try:\n'
    '        t = open(path, errors="replace").read()\n'
    '    except OSError:\n'
    '        return ""\n'
    '    keep = []\n'
    '    for ln in t.splitlines():\n'
    '        if ln.startswith("+++ ") or ln.startswith("--- "):\n'
    '            keep.append(ln[:4] + ln[4:].strip())\n'
    '        elif (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---")):\n'
    '            s = re.sub(r"\\s+", "", ln[1:])\n'
    '            if s:\n'
    '                keep.append(ln[0] + s)\n'
    '    return "\\n".join(keep)\n'
    '\n'
    '\n'
    'def _finalize(msg):\n')

OLD_ACC = ('    if msg.startswith("ACCEPTED"):\n'
           '        print("%s\\nCall submit_patch now." % msg)\n'
           '        return\n')
NEW_ACC = ('    if msg.startswith("ACCEPTED"):\n'
           '        st["attempts"][-1]["norm"] = hashlib.sha1(_norm_diff(dpath).encode()).hexdigest() if os.path.getsize(dpath) > 0 else ""\n'
           '        json.dump(st, open(sp, "w"))\n'
           '        acc = [a for a in st["attempts"] if a.get("norm")]\n'
           '        cur = st["attempts"][-1].get("norm")\n'
           '        agree = [a for a in acc if a["norm"] == cur]\n'
           '        if cur and len(agree) >= 2:\n'
           '            print("%s\\nVOTE: %d independent attempts made the SAME change. Call submit_patch now." % (msg, len(agree)))\n'
           '            return\n'
           '        if n < MAX_ATTEMPTS:\n'
           '            if src and os.path.getsize(dpath) > 0:\n'
           '                rcu, _ = sh("git apply -R %s" % dpath)\n'
           '                if rcu != 0:\n'
           '                    sh("git checkout %s -- %s" % (base, " ".join(src)))\n'
           '            print("%s (attempt %d of %d)\\nCONFIRM: this fix passed the checks. It has been UNDONE so a SECOND independent '
           'attempt can confirm it.\\nReply RETRY (no tool calls). The fixer will solve the task again from scratch."\n'
           '                  % (head, n, MAX_ATTEMPTS))\n'
           '            return\n'
           '        # last attempt accepted but no agreement: keep the most frequent accepted diff (tie -> earliest)\n'
           '        cnt = {}\n'
           '        for a in acc:\n'
           '            cnt[a["norm"]] = cnt.get(a["norm"], 0) + 1\n'
           '        best = min(acc, key=lambda a: (-cnt[a["norm"]], a["n"]))\n'
           '        if best["n"] != n:\n'
           '            if src and os.path.getsize(dpath) > 0:\n'
           '                sh("git apply -R %s" % dpath)\n'
           '            sh("git apply %s || git apply --3way %s" % (best["diff"], best["diff"]))\n'
           '        print("%s\\nVOTE: no two attempts agreed; restored accepted attempt #%d. Call submit_patch now." % (msg, best["n"]))\n'
           '        return\n')
sub(c, OLD_ACC, NEW_ACC)
# when attempts run out on a REJECT, prefer an earlier ACCEPTED attempt (score 0) over anything else: already true via
# the score sort (ACCEPTED = 0). Make sure hashlib is imported in the gate.
sub(c, "import os\nimport re\nimport subprocess\nimport sys\n", "import hashlib\nimport os\nimport re\nimport subprocess\nimport sys\n")

f = V / "sub_agents" / "prompts" / "fixer.md"
sub(f, "5. RETRY RULE: if the latest message is `RETRY: ...`, a previous attempt was rejected and UNDONE",
    "5. CONFIRM RULE: if the latest message says CONFIRM, your previous fix PASSED and was undone only so it can be confirmed. "
    "Solve the task again from scratch, independently, and make the fix you judge BEST (do NOT try to be different, and do "
    "NOT try to recall the previous fix). Then reply `DONE:` as usual.\n"
    "6. RETRY RULE: if the latest message is `RETRY: ...` (and does not say CONFIRM), a previous attempt was rejected and UNDONE")
vf = V / "sub_agents" / "prompts" / "verifier.md"
sub(vf, "3. If the output contains `Reply RETRY`: make NO tool calls. Reply with exactly one line: `RETRY: <the failure in a few words>`.",
    "3. If the output contains `Reply RETRY`: make NO tool calls. Reply with exactly one line: `RETRY: <the failure in a few words>`. "
    "If the output contains `CONFIRM`, reply exactly `RETRY: CONFIRM - the fix passed; solve again independently to confirm`.")
compile(c.read_text(encoding="utf-8"), "check.py", "exec")
for d in sorted(A4.iterdir()):
    print(f"{d.name:10s} sha {fp(d)}")
