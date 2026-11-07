"""Sanity-check the built e4b-pack-ab kernel: arm bundle hashes must equal the two submission packs."""
import base64
import hashlib
import json
import re

nb = json.load(open("kaggle_pkg/push_e4b_pack_ab/e4b-pack-ab.ipynb", encoding="utf-8"))
c2 = "".join(nb["cells"][2]["source"])
arms = json.loads(re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S).group(1))
want = {"ARM_P1_retry_fresh": "84f904c63afd", "ARM_P2_retry_vnone": "a5129fc56ffb"}
for a, f in arms.items():
    fs = {k: base64.b64decode(v) for k, v in f.items() if k != "tasks.jsonl_gz"}
    sha = hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]
    print(a, "bundle sha", sha, "OK" if sha == want[a] else "MISMATCH want " + want[a])
c4 = "".join(nb["cells"][4]["source"])
print("LIVE", len(json.loads(re.search(r"LIVE = (\[.*?\])", c4).group(1))), "|",
      re.search(r"NODE_ARM = (\{.*?\})", c4).group(1), "|", re.search(r"BUDGET_SECONDS = \d+", c4).group(0))
print(json.load(open("kaggle_pkg/push_e4b_pack_ab/kernel-metadata.json"))["id"])
