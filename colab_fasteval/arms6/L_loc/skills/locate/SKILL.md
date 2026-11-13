---
name: locate
description: Finds the source files that DEFINE the names in the problem. Run scripts/locate.py with args q set to the identifiers and error text from the problem.
---
Run `scripts/locate.py` with `args` = `{"q": "..."}`, where q holds the names from the problem statement: function/class/attribute names, error messages, file or module names (copy them exactly).
It prints up to 5 candidate files, best first, with the line numbers where each name is DEFINED.
- Open candidate #1 with `sed -n` around its definition line and make the fix THERE.
- Do not edit tests, docs, README, LICENSE or packaging files.
