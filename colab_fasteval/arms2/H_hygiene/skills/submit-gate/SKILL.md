---
name: submit-gate
description: Checks the current edit in /workspace before submitting. Run scripts/check.py; it prints ACCEPTED or REJECTED with the first failure.
---
Run `scripts/check.py` with no arguments. It compiles the changed source files and runs the repository's existing tests for the edited module(s), on the patched code and on the original code, and reports only NEW failures caused by the edit.
- `ACCEPTED ...` -> submit.
- `REJECTED ...` -> fix the source (never the tests) and run it again.
