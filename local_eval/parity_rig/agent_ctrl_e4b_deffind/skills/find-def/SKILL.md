---
name: find-def
description: Greps the repo for where a class/function/method symbol is DEFINED (def/class) and prints the defining file(s), so edits land in the definition not a call site.
---
Run `scripts/find_def.py <Symbol>` (a class/function/method name, e.g. FileProxy or isatty).
Prints the file(s) containing `def <Symbol>` or `class <Symbol>`, with the matching line.
