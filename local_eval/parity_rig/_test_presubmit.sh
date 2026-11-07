#!/usr/bin/env bash
# Offline unit test of agent_31b_ca5_presubmit/skills/presubmit-check/scripts/check.py (WSL, no model).
set -u
RIG="$(cd "$(dirname "$0")" && pwd)"
CHECK="$RIG/agent_31b_ca5_presubmit/skills/presubmit-check/scripts/check.py"
PASS=0; FAIL=0
ok()  { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
mk() {
  T=$(mktemp -d); export HOME="$T/home"; mkdir -p "$HOME" "$T/ws/pkg" "$T/ws/tests"; cd "$T/ws"
  git init -q; git config user.email t@t; git config user.name t
  printf 'import os\n\ndef add(a, b):\n    return a - b\n' > pkg/mathx.py; : > pkg/__init__.py
  printf 'from pkg.mathx import add\n' > tests/test_mathx.py
  git add -A; git commit -qm base; git tag _swegemma_baseline; export PYTHONPATH="$T/ws"
}
run() { python3 "$CHECK" 2>&1; }
echo "== empty patch";        mk;                                                         o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "PROBLEM: your patch is EMPTY" && ok empty || bad empty
echo "== good edit";          mk; printf 'import os\n\ndef add(a, b):\n    return a + b\n' > pkg/mathx.py; o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "^OK: edit landed" && ok good || bad good
echo "== syntax error";       mk; printf 'def add(a, b)\n    return a + b\n' > pkg/mathx.py;  o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "PROBLEM: syntax error in pkg/mathx.py" && ok syntax || bad syntax
echo "== import-time error";  mk; printf 'import os\nX = undefined_name\n' > pkg/mathx.py;  o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "PROBLEM: importing pkg.mathx fails" && ok import || bad import
echo "== env import failure ignored"; mk; printf 'import not_installed_dep\n' > pkg/__init__.py; git commit -qam env; git tag -f _swegemma_baseline >/dev/null
printf 'import os\n\ndef add(a, b):\n    return a + b\n' > pkg/mathx.py; o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "^OK" && ok envignored || bad envignored
echo "== test-only edit";     mk; printf 'from pkg.mathx import add\nX=1\n' > tests/test_mathx.py; o=$(run); echo "     $o" | head -1; echo "$o" | grep -q "PROBLEM: you only changed test files" && ok testonly || bad testonly
echo "== workspace untouched"; mk; printf 'import os\n\ndef add(a, b):\n    return a + b\n' > pkg/mathx.py; before=$(git diff | sha1sum); run >/dev/null; after=$(git diff | sha1sum); [ "$before" = "$after" ] && ok untouched || bad untouched
echo; echo "RESULT: $PASS passed, $FAIL failed"
