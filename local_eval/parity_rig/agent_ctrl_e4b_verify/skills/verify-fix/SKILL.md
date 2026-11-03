---
name: verify-fix
description: Compiles the edited source file and runs the single most-relevant existing test for that module, printing VERIFY PASS or FAIL with the first failure line. One call, deterministic, no LLM.
---
Run `scripts/verify.py <source_file_path>` (path relative to the repository root, e.g. rich/table.py).
It py_compiles the file and runs the one existing test file that imports that module, then prints
`VERIFY: PASS`, `VERIFY: FAIL <first failure line>`, or `VERIFY: NO_TEST`.
