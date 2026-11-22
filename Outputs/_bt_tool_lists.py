"""Which tool lists have the project's agents actually had? (YAML-parsed from every bundle's agent configs.)"""
import sqlite3
from collections import defaultdict

import yaml


class L(yaml.SafeLoader):
    pass


L.add_constructor("!include", lambda loader, node: None)
db = sqlite3.connect("kb/attempts.sqlite")
combos = defaultdict(set)
for path, rel, content in db.execute("""SELECT b.path, f.relpath, f.content FROM bundle_files f JOIN bundles b USING (bundle_id)
                                       WHERE f.relpath LIKE '%.yaml' AND f.content LIKE '%tools%'"""):
    try:
        d = yaml.load(content, Loader=L) or {}
    except Exception:
        continue
    if not isinstance(d, dict) or not isinstance(d.get("tools"), list):
        continue
    role = d.get("name") or rel
    tools = tuple(sorted(str(t if isinstance(t, str) else (t.get("name") if isinstance(t, dict) else t)) for t in d["tools"]))
    combos[(role if role in ("fixer", "verifier", "tester") else "main/" + str(role)[:20], tools)].add(path)
for (role, tools), paths in sorted(combos.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(paths):3d} bundles  {role:28s} read_file={'read_file' in tools!s:5s} {list(tools)}")
