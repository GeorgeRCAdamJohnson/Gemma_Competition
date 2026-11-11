"""Verify the built e4b-batch3 notebook: embedded arm hashes, node mapping, task list, budget."""
import base64
import hashlib
import json
import re

nb = json.load(open("kaggle_pkg/push_e4b_batch3/e4b-batch3.ipynb", encoding="utf-8"))
c2 = "".join(nb["cells"][2]["source"])
arms = json.loads(re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S).group(1))
for a, f in arms.items():
    fs = {k: base64.b64decode(v) for k, v in f.items() if k != "tasks.jsonl_gz"}
    print(a, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
c4 = "".join(nb["cells"][4]["source"])
print(re.search(r"NODE_ARM = (\{.*?\})", c4).group(1))
print("tasks", len(json.loads(re.search(r"LIVE = (\[.*?\])", c4).group(1))), re.search(r"BUDGET_SECONDS = \d+", c4).group(0))
