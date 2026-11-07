#!/usr/bin/env bash
# Offline unit test of agent_e4b_retry_repro's submit-gate (check.py). Runs in WSL. No model.
# Scenarios: (1) good repro + correct fix -> ACCEPTED, repro file out of the patch;
#            (2) good repro + wrong fix   -> REJECTED REPRO_FAIL, edit undone (retry);
#            (3) 3 wrong attempts         -> best restored = EARLIEST attempt;
#            (4) bad repro (reproduces on the fix too / never reproduces) -> repro ignored, ACCEPTED;
#            (5) fresh arm (REPRO=False) ignores repro_issue.py entirely.
set -u
RIG="$(cd "$(dirname "$0")" && pwd)"
CHECK_R="$RIG/agent_e4b_retry_repro/skills/submit-gate/scripts/check.py"
CHECK_F="$RIG/agent_e4b_retry_fresh/skills/submit-gate/scripts/check.py"
PASS=0; FAIL=0
ok()  { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

mkrepo() {
  T=$(mktemp -d); export HOME="$T/home"; mkdir -p "$HOME" "$T/ws/pkg" "$T/ws/tests"
  cd "$T/ws"
  git init -q; git config user.email t@t; git config user.name t
  printf 'def add(a, b):\n    return a - b\n' > pkg/mathx.py
  : > pkg/__init__.py
  printf 'from pkg.mathx import add\n\ndef test_zero():\n    assert add(0, 0) == 0\n' > tests/test_mathx.py
  git add -A; git commit -qm base
  export PYTHONPATH="$T/ws${EXTRA_PY:+:$EXTRA_PY}"
}
good_repro() {
  cat > repro_issue.py <<'EOF'
from pkg.mathx import add

def test_issue():
    try:
        r = add(2, 3)
    except Exception as e:
        print("Other issues", repr(e))
        return
    try:
        assert r == 5
        print("Issue resolved")
    except AssertionError:
        print("Issue reproduced")

test_issue()
EOF
}
fix_correct() { printf 'def add(a, b):\n    return a + b\n' > pkg/mathx.py; }
fix_wrong()   { printf 'def add(a, b):\n    return a * b if a else b - a\n' > pkg/mathx.py; }   # add(0,0)=0 ok, add(2,3)=6
gate() { python3 "$1" 2>&1; }

echo "== 1. good repro + correct fix"
mkrepo; good_repro; fix_correct
out=$(gate "$CHECK_R"); echo "$out" | head -3 | sed 's/^/     /'
echo "$out" | grep -q "Call submit_patch now" && ok "accepted" || bad "not accepted"
echo "$out" | grep -q "Issue resolved" && ok "repro credited" || bad "repro not credited"
[ ! -e repro_issue.py ] && ok "repro moved out of workspace" || bad "repro still in workspace"
git add -N . ; git diff HEAD --name-only | grep -q repro_issue && bad "repro in diff" || ok "repro not in diff"
grep -q "a + b" pkg/mathx.py && ok "fix still applied" || bad "fix lost"

echo "== 2/3. good repro + wrong fixes x3 (attempt 1 differs from attempt 3)"
mkrepo; good_repro; fix_wrong
out=$(gate "$CHECK_R"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "REPRO_FAIL" && ok "attempt1 REPRO_FAIL" || bad "attempt1 not REPRO_FAIL"
echo "$out" | grep -q "Reply RETRY" && ok "asks for retry" || bad "no retry"
grep -q "a - b" pkg/mathx.py && ok "attempt1 undone" || bad "attempt1 not undone"
printf 'def add(a, b):\n    return a * 2 if a else b * 0\n' > pkg/mathx.py   # attempt 2: also wrong
out=$(gate "$CHECK_R"); echo "$out" | grep -q "REPRO_FAIL" && ok "attempt2 REPRO_FAIL" || bad "attempt2"
printf 'def add(a, b):\n    return 7 if a else 0\n' > pkg/mathx.py           # attempt 3: also wrong
out=$(gate "$CHECK_R"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "Restored the best attempt so far (#1" && ok "restored EARLIEST (#1)" || bad "did not restore #1"
grep -q "a \* b if a else b - a" pkg/mathx.py && ok "attempt1 text back" || bad "attempt1 text not back"

echo "== 4a. bad repro that reproduces on the correct fix too -> ignored"
mkrepo
cat > repro_issue.py <<'EOF'
print("Issue reproduced")
EOF
fix_correct
out=$(gate "$CHECK_R"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "Call submit_patch now" && bad "should reject: base reproduces AND fix reproduces (valid test, says unresolved)" || ok "rejected (test is 'valid' by construction, cannot be told apart at runtime)"

echo "== 4b. repro that never reproduces on base (prints Other issues) -> ignored"
mkrepo
cat > repro_issue.py <<'EOF'
import nonexistent_module
EOF
fix_correct
out=$(gate "$CHECK_R"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "Call submit_patch now" && ok "accepted (invalid repro ignored)" || bad "invalid repro blocked a fix"

echo "== 4c. existing-test regression still rejected"
mkrepo; good_repro
printf 'def add(a, b):\n    return a + b + 1\n' > pkg/mathx.py   # breaks test_zero
out=$(gate "$CHECK_R"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "Reply RETRY" && ok "regression rejected" || bad "regression accepted"

echo "== 5. fresh arm ignores repro_issue.py"
mkrepo; good_repro; fix_wrong
out=$(gate "$CHECK_F"); echo "$out" | head -2 | sed 's/^/     /'
echo "$out" | grep -q "REPRO_FAIL" && bad "fresh arm used repro" || ok "fresh arm: no repro gating"

echo; echo "RESULT: $PASS passed, $FAIL failed"
