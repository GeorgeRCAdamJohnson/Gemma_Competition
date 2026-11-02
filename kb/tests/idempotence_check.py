#   usage: python idempotence_check.py snapshot <out.json> | compare <a.json> <b.json>
import hashlib, json, pathlib, sys
KB = pathlib.Path(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb")
STAMP_FILE = "build_stamp.json"
STAMP_PREFIXES = (b"<!-- build-stamp:", b"Build stamp:")
def generated_files():
    meta = json.loads((KB / "build_meta.json").read_text(encoding="utf-8"))
    return sorted(set(meta["generated_files"]) - {STAMP_FILE})
def digest(rel):
    data = (KB / rel).read_bytes()
    if rel.endswith((".md", ".txt")):
        data = b"".join(l for l in data.splitlines(keepends=True) if not l.startswith(STAMP_PREFIXES))
    return hashlib.sha256(data).hexdigest()
if sys.argv[1] == "snapshot":
    pathlib.Path(sys.argv[2]).write_text(json.dumps({f: digest(f) for f in generated_files()}, indent=1))
else:
    a, b = (json.loads(pathlib.Path(x).read_text()) for x in sys.argv[2:4])
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    print("IDENTICAL" if not diff else "DIFFERENT: " + ", ".join(diff)); sys.exit(1 if diff else 0)
