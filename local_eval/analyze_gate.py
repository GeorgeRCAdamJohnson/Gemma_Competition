"""Per-task breakdown of a gate run: where did the agent stop, did it ever look at the gold file, did its edit
land on the gold hunk, did it pass.  CPU only.   python analyze_gate.py g12p_on g12p_off ...
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
TASKS = {}
for line in open(HERE.parent / "comp_files" / "tasks.jsonl", encoding="utf-8"):
    t = json.loads(line)
    TASKS[t["instance_id"]] = t


def hunks(diff):
    """{file: [(start, end)]} in old-file line numbers."""
    out, cur = {}, None
    for line in diff.splitlines():
        m = re.match(r"^\+\+\+ b/(\S+)", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? ", line)
        if m and cur:
            a, n = int(m.group(1)), int(m.group(2) or 1)
            out[cur].append((a, a + max(n, 1)))
    return out


def overlap(h1, h2, slack=10):
    return any(a1 - slack < b2 and a2 - slack < b1 for f, r1 in h1.items() for (a1, b1) in r1 for (a2, b2) in h2.get(f, []))


def load(tag):
    res = {}
    p = HERE / "runs" / f"{tag}.results.jsonl"
    if p.exists():
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            res[r["task"]] = r
    tr = {}
    p = HERE / "runs" / f"{tag}.trace.jsonl"
    if p.exists():
        for line in open(p, encoding="utf-8"):
            try:
                e = json.loads(line)
            except Exception:
                continue
            tr.setdefault(e.get("task"), []).append(e)
    return res, tr


def row(tid, r, ev):
    gold = hunks(TASKS[tid]["patch"])
    gold_files = set(gold)
    turns = [e for e in ev if e.get("kind") == "turn"]
    tools = [e for e in ev if e.get("kind") == "tool"]
    first_notool = next((e["turn"] for e in turns if not e.get("tools")), None)
    first_edit = next((e["turn"] for e in tools if e.get("tool") == "edit_file"), None)
    touched = {e.get("path") for e in tools if e.get("tool") == "read_file" and e.get("path")}
    touched_gold = any(any(str(p).endswith(g) or g.endswith(str(p)) for g in gold_files) for p in touched if p)
    diff = r.get("diff", "") if r else ""
    mine = hunks(diff)
    nudge_rows = [e for e in ev if e.get("kind") == "nudge"]
    recovered = 0
    for n in nudge_rows:
        nxt = next((t for t in turns if t.get("turn", 0) > n.get("turn", 0)), None)
        if nxt is not None and nxt.get("tools"):
            recovered += 1
    reads = {}
    for e in tools:
        if e.get("tool") == "read_file" and e.get("path"):
            reads[e["path"]] = reads.get(e["path"], 0) + 1
    return {
        "task": tid,
        "resolved": (r or {}).get("resolved"),
        "end": (r or {}).get("end_reason"),
        "turns": (r or {}).get("turns"),
        "first_edit": first_edit,
        "first_notool": first_notool,
        "nudges": len(nudge_rows),
        "recovered": recovered,
        "max_consec": (r or {}).get("max_consecutive_nudges"),
        "max_reads_one_path": max(reads.values()) if reads else 0,
        "len_turns": sum(1 for e in turns if e.get("finish") == "length"),
        "read_gold": touched_gold,
        "edit_gold_file": bool(set(mine) & gold_files),
        "edit_gold_hunk": overlap(mine, gold) if mine else False,
        "patch": (r or {}).get("patch_chars"),
        "dur": (r or {}).get("dur"),
    }


def main():
    tags = sys.argv[1:] or ["g12p_on", "g12p_off"]
    for tag in tags:
        res, tr = load(tag)
        print(f"\n=== {tag}  ({len(res)} tasks done)")
        print(f"{'task':10}{'pass':>5} {'end':17}{'turns':>6}{'1stEdit':>8}{'1stNoTool':>10}{'nudge':>6}{'recov':>6}{'maxC':>5}{'rd1p':>5}{'len':>4}{'readGold':>9}{'editFile':>9}{'editHunk':>9}{'patch':>7}{'secs':>6}")
        rows = [row(t, res.get(t), tr.get(t, [])) for t in res]
        for x in rows:
            print(f"{x['task']:10}{str(x['resolved'])[:1]:>5} {str(x['end']):17}{str(x['turns']):>6}{str(x['first_edit']):>8}{str(x['first_notool']):>10}"
                  f"{x['nudges']:>6}{x['recovered']:>6}{str(x['max_consec']):>5}{x['max_reads_one_path']:>5}"
                  f"{x['len_turns']:>4}{str(x['read_gold'])[:1]:>9}{str(x['edit_gold_file'])[:1]:>9}{str(x['edit_gold_hunk'])[:1]:>9}{str(x['patch']):>7}{str(x['dur']):>6}")
        if rows:
            n = len(rows)
            nullp = sum(1 for x in rows if x["first_notool"] is not None and (x["first_edit"] is None or x["first_notool"] < x["first_edit"]))
            ends = {}
            for x in rows:
                ends[x["end"]] = ends.get(x["end"], 0) + 1
            print(f"-- resolved {sum(bool(x['resolved']) for x in rows)}/{n} | submitted {sum(x['end']=='submitted' for x in rows)}/{n} | "
                  f"read gold file {sum(x['read_gold'] for x in rows)}/{n} | edited gold file {sum(x['edit_gold_file'] for x in rows)}/{n} | "
                  f"edited gold hunk {sum(x['edit_gold_hunk'] for x in rows)}/{n} | first no-tool turn before first edit {nullp}/{n}")
            print(f"-- ends {ends} | nudges {sum(x['nudges'] for x in rows)} recovered {sum(x['recovered'] for x in rows)} | "
                  f"empty/no patch {sum(1 for x in rows if not x['patch'])}/{n}")


if __name__ == "__main__":
    main()
