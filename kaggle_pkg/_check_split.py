"""Verify the split-design patches landed in both single-pack kernels and that cell 4 compiles."""
import json
import re

for slug in ("e4b-pack1-val", "e4b-pack2-val"):
    nb = json.load(open(f"kaggle_pkg/push_{slug.replace('-', '_')}/{slug}.ipynb", encoding="utf-8"))
    c = "".join(nb["cells"][4]["source"])
    checks = {s: c.count(s) for s in ("SCORE_IDS = ", "RUNTIME_IDS = ", "ids = RUNTIME_IDS if", 'kind == "score39"',
                                      "RUNTIME90 node", '"kind": kind')}
    compile(c, "c4", "exec")
    s = json.loads(re.search(r"SCORE_IDS = (\[.*?\])", c).group(1))
    r = json.loads(re.search(r"RUNTIME_IDS = (\[.*?\])", c).group(1))
    print(slug, checks, "| score", len(s), "runtime", len(r), "overlap", len(set(s) & set(r)),
          "|", re.search(r"BUDGET_SECONDS = \d+", c).group(0), "| compiles")
