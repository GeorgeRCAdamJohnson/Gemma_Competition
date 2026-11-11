#!/usr/bin/env bash
# Offline test of the V_vote gate (no GPU). Runs check.py exactly as the verifier would: cwd = repo, HOME = state dir.
set -u
G=/mnt/c/Users/biges/Gemma/Gemma_Competition/colab_fasteval/arms4/V_vote/skills/submit-gate/scripts/check.py
fail=0
new_repo() {
  R=$(mktemp -d); H=$(mktemp -d)
  cd "$R" && git init -q && git config user.email t@t && git config user.name t
  printf 'def f(x):\n    return x + 1\n' > a.py
  git add -A && git commit -qm base && git tag _swegemma_baseline
}
gate() { HOME="$H" PYTHONPATH="$R" python3 "$G"; }
expect() { if echo "$1" | grep -q "$2"; then echo "  ok: $2"; else echo "  FAIL: wanted '$2' got: $1"; fail=1; fi; }

echo "== scenario 1: attempt 1 accepted, attempt 2 makes the same change (different whitespace) -> submit"
new_repo
printf 'def f(x):\n    return x + 2\n' > a.py
o=$(gate); expect "$o" "CONFIRM"; expect "$o" "attempt 1 of 3"
expect "$(cat a.py)" "x + 1"                       # undone
printf 'def f(x):\n    return x  +  2\n' > a.py     # same change, whitespace differs
o=$(gate); expect "$o" "VOTE: 2 independent attempts"; expect "$o" "Call submit_patch now"
expect "$(cat a.py)" "x  +  2"                     # left in place for submit

echo "== scenario 2: three accepted attempts, all different -> restore attempt 1 (tie -> earliest)"
new_repo
for v in 2 3 4; do printf 'def f(x):\n    return x + %s\n' $v > a.py; o=$(gate); done
expect "$o" "no two attempts agreed; restored accepted attempt #1"
expect "$(cat a.py)" "x + 2"

echo "== scenario 3: accepted, rejected (syntax), accepted same as 1 -> submit on agreement"
new_repo
printf 'def f(x):\n    return x + 2\n' > a.py; o=$(gate); expect "$o" "CONFIRM"
printf 'def f(x):\n    return (x + \n' > a.py; o=$(gate); expect "$o" "syntax error"; expect "$o" "UNDONE"
expect "$(cat a.py)" "x + 1"
printf 'def f(x):\n    return x + 2\n' > a.py; o=$(gate); expect "$o" "VOTE: 2 independent attempts"

echo "== scenario 4: no change -> rejected as before"
new_repo
o=$(gate); expect "$o" "no change in the repo"
[ $fail -eq 0 ] && echo "ALL OK" || echo "SOME FAILED"
