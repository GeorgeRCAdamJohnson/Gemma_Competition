import gzip, base64, json, re, os
# extract the _DATA_B64GZ literal from notebook_src.py and decode it, compare to the original jsonl
src = open(os.path.join(os.path.dirname(__file__), "notebook_src.py"), encoding="utf-8").read()
m = re.search(r"_DATA_B64GZ = \((.*?)\)\n", src, re.S)
assert m, "blob literal not found"
b64 = "".join(re.findall(r'"([^"]+)"', m.group(1)))
raw = gzip.decompress(base64.b64decode(b64)).decode("utf-8")
decoded = [json.loads(l) for l in raw.splitlines() if l.strip()]
orig_path = os.path.join(os.path.dirname(__file__), "..", "train", "data", "localization_traj_train.jsonl")
orig = [json.loads(l) for l in open(orig_path, encoding="utf-8") if l.strip()]
print("decoded", len(decoded), "orig", len(orig), "match:", decoded == orig)
assert decoded == orig, "blob does not round-trip!"
print("sample assistant turn:", decoded[0]["messages"][1]["content"][:120])
