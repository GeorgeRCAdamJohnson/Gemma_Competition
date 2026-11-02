"""CPU-only: are the FAILED real 31B runs on a task failing the same way (same file / near-identical edit) or differently?
Prints, per run, the files touched by edit_file / run_command-python-replace and a 90-char signature of the LAST edit.
python atif_patch_diversity.py rich_4079 rich_3471 rich_4076
"""
import collections, json, re, sys
import atif_behavior_outcomes as B


def edits(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for s in t.get("steps", []):
        for tc in (s.get("tool_calls") or []):
            fn, a = tc.get("function_name"), tc.get("arguments") or {}
            if fn == "edit_file":
                out.append(("edit_file", a.get("filepath"), (a.get("new_string") or "")))
            elif fn == "run_command":
                c = a.get("command") or ""
                if ("replace(" in c or "sed -i" in c or "write_text" in c or "open(" in c and "'w'" in c) and "pytest" not in c:
                    m = re.search(r"[\w/\.]+\.py", c)
                    out.append(("run_command", m.group(0) if m else "?", c))
    return out


def sig(s):
    s = re.sub(r"\s+", " ", s.replace("\\n", " "))
    return s[:90]


def main():
    tasks = sys.argv[1:] or ["rich_4079", "rich_3471", "rich_4076"]
    for task in tasks:
        print("=" * 100)
        print(task)
        rows = []
        for p in sorted(B.ROOT.glob(f"**/trace_{task}.json")):
            if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
                continue
            v = B.version_of(p)
            o = B.OUTCOME.get((v, task))
            if o is None or B.analyse(p) is None:
                continue
            e = edits(p)
            rows.append((v, bool(o["resolved"]), e))
        files = collections.Counter()
        for v, res, e in rows:
            last = e[-1] if e else None
            fs = sorted({x[1] for x in e})
            for f in fs:
                files[(res, f)] += 1
            print(f"{'PASS' if res else 'FAIL'} {v:42} n_edits={len(e):2} files={fs} last={'-' if not last else last[0] + ': ' + sig(last[2])}")
        print("files touched (resolved?, file) -> runs:")
        for k, c in sorted(files.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print("  ", k, c)


if __name__ == "__main__":
    main()
