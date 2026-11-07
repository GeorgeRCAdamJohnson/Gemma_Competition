---
name: presubmit-check
description: Fast pre-submit sanity check of your edit - did it land, do the changed files parse and import. Run scripts/check.py with no arguments before submit_patch.
---
Run `scripts/check.py` (no arguments). Prints `OK ...` or `PROBLEM: ...` naming the file and line.
