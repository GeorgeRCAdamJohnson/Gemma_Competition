"""Deep analysis of the 129-task 31B A3 run from the version10 output file.

Parses the per-task trace blocks (tool calls with emoji markers, results,
timings) and checks agent behaviour against the A3 prompt's explicit rules.

Usage: python analyse_v10.py
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

F = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\Outputs\Gemma_Sibling-conform_31b_A3_Hard_version10"
GEMMA = r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma"

RE_HDR = re.compile(r"^\s*\[(\d+)/129\]\s+(\S+)\s+\(([^)]+)\)")
RE_RES = re.compile(r"resolved=(True|False)\s+duration=([\d.]+)s\s+tool_calls=(\d+)\s+patch_chars=(\d+)")
# tool invocation lines: "  [  14.9s] 📖 read_file (rich/logging.py)"
RE_TOOL = re.compile(r"\[\s*([\d.]+)s\]\s+(\S+)\s+(.+)")
# result lines: "  [  14.9s]   ✓ {...}" or "  [  76.1s]   → error ..."
RE_OK = re.compile(r"\[\s*([\d.]+)s\]\s+✓\s+(.*)")
RE_ERR = re.compile(r"\[\s*([\d.]+)s\]\s+→\s*(error.*)")
RE_THINK = re.compile(r"💭\s+\((\d+) chars\)")

TOOL_EMOJI = {
    "📖": "read_file", "✏️": "edit_file", "🔧": "run_command",
    "📋": "system", "🎯": "task", "💭": "think",
}


def parse(path):
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    tasks = []
    cur = None
    pending_tool = None
    for ln in lines:
        m = RE_HDR.search(ln)
        if m and "resolved=" not in ln:
            if cur:
                tasks.append(cur)
            cur = {"idx": int(m.group(1)), "task": m.group(2), "repo": m.group(3),
                   "tools": [], "results": [], "think_chars": 0}
            pending_tool = None
            continue
        if cur is None:
            continue
        m = RE_RES.search(ln)
        if m:
            cur.update(resolved=(m.group(1) == "True"), dur=float(m.group(2)),
                       calls=int(m.group(3)), patch=int(m.group(4)))
            tasks.append(cur)
            cur = None
            pending_tool = None
            continue
        m = RE_THINK.search(ln)
        if m:
            cur["think_chars"] += int(m.group(1))
            continue
        m = RE_OK.search(ln)
        if m and pending_tool is not None:
            cur["results"].append({"tool": pending_tool, "ok": True, "detail": m.group(2)[:200]})
            pending_tool = None
            continue
        m = RE_ERR.search(ln)
        if m and pending_tool is not None:
            cur["results"].append({"tool": pending_tool, "ok": False, "detail": m.group(2)[:200]})
            pending_tool = None
            continue
        # "→ get_status: {...}" / "→ submit_patch: {...}" result lines
        m = re.search(r"\]\s+→\s+([a-z_]+):\s+(.*)", ln)
        if m:
            ok = '"status": "ok"' in m.group(2) or "'status': 'ok'" in m.group(2)
            cur["results"].append({"tool": m.group(1), "ok": ok, "detail": m.group(2)[:200]})
            if pending_tool == m.group(1):
                pending_tool = None
            continue
        m = RE_TOOL.search(ln)
        if m:
            emoji = m.group(2)
            rest = m.group(3)
            name = TOOL_EMOJI.get(emoji)
            if emoji == "🤖":          # get_status / submit_patch: name follows
                name = rest.split()[0] if rest.split() else None
            if name and name not in ("system", "task", "think"):
                pending_tool = name
                cur["tools"].append({"t": float(m.group(1)), "name": name, "arg": rest[:120]})
    if cur:
        tasks.append(cur)
    return tasks


def main():
    tasks = parse(F)
    print("parsed %d tasks" % len(tasks))
    rich = [t for t in tasks if t["task"].startswith("rich_")]
    print("rich: %d" % len(rich))

    # ---- PART 1: rich solves prior vs this run ----
    prior = set()
    # cover-rich + repeat-live (log L10701, L10761)
    prior |= {"rich_2725", "rich_2943", "rich_3006", "rich_3043", "rich_3067",
              "rich_3454", "rich_3518", "rich_3777", "rich_3894", "rich_3905"}
    # out_k_31ba3 smoke (log: 4077 T, 3278 T, 3471 T, 3718 T, 3772 F)
    prior |= {"rich_4077", "rich_3278", "rich_3471", "rich_3718"}
    # scan other 31B output logs for rich resolved=True
    for root, dirs, files in os.walk(GEMMA):
        if "local_eval" in root and "runs" in root:
            continue
        for fn in files:
            if not fn.endswith(".log"):
                continue
            p = os.path.join(root, fn)
            if os.path.abspath(p) == os.path.abspath(F):
                continue
            try:
                txt = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if "31b" not in txt[:2000].lower() and "31b" not in fn.lower():
                continue
            # find task->resolved pairs
            cur_task = None
            for ln in txt.splitlines():
                m = re.search(r"\[\d+/\d+\]\s+(rich_\d+)", ln)
                if m:
                    cur_task = m.group(1)
                m = re.search(r"resolved=(True|False)", ln)
                if m and cur_task:
                    if m.group(1) == "True":
                        prior.add(cur_task)
                    cur_task = None

    this_solved = {t["task"] for t in rich if t.get("resolved")}
    lost = sorted(prior - this_solved)
    gained = sorted(this_solved - prior)
    kept = sorted(this_solved & prior)
    print("\n=== RICH: prior 31B solves vs this run ===")
    print("prior-solved union: %d | this run solved: %d" % (len(prior), len(this_solved)))
    print("kept (%d): %s" % (len(kept), ", ".join(kept)))
    print("LOST - solved before, missed this time (%d): %s" % (len(lost), ", ".join(lost)))
    print("NEW - never solved before (%d): %s" % (len(gained), ", ".join(gained)))

    # detail on lost tasks
    for t in rich:
        if t["task"] in lost:
            print("  LOST %-12s dur=%.0fs calls=%d patch=%d tools=%s" % (
                t["task"], t.get("dur", 0), t.get("calls", 0), t.get("patch", 0),
                collections.Counter(x["name"] for x in t["tools"])))

    # ---- PART 2: prompt compliance ----
    print("\n=== PROMPT COMPLIANCE (A3 rules) ===")
    all_t = [t for t in tasks if "tools" in t]
    stats = collections.Counter()
    per_task = []
    for t in all_t:
        tools = t["tools"]
        names = [x["name"] for x in tools]
        c = collections.Counter(names)
        first_edit = next((i for i, n in enumerate(names) if n == "edit_file"), None)
        n_status = c.get("get_status", 0)
        n_submit = c.get("submit_patch", 0)
        n_edit = c.get("edit_file", 0)
        # calls before first edit (rule: AT MOST 3-4 locating)
        locate = first_edit if first_edit is not None else len(names)
        # errors
        errs = [r for r in t.get("results", []) if not r["ok"]]
        # identical re-send after failure: same tool+arg twice with error between
        resend = 0
        last_err = None
        for x in tools:
            if last_err and x["name"] == last_err["name"] and x["arg"][:60] == last_err["arg"][:60]:
                resend += 1
            last_err = None
            # mark if this tool errored (match by order is approximate; use results list)
        # simpler: count results errors by tool
        row = dict(task=t["task"], resolved=t.get("resolved"), calls=t.get("calls"),
                   patch=t.get("patch"), n_status=n_status, n_submit=n_submit,
                   n_edit=n_edit, locate=locate, errs=len(errs),
                   zero_patch=(t.get("patch", 1) == 0),
                   cap=(t.get("calls", 0) >= 28))
        per_task.append(row)
        stats["tasks"] += 1
        stats["status0"] += (n_status == 0)
        stats["status_ge3"] += (n_status >= 3)
        stats["submit_ne1"] += (n_submit != 1)
        stats["submit_gt1"] += (n_submit > 1)
        stats["edit_gt1"] += (n_edit > 1)
        stats["locate_gt4"] += (locate > 4)
        stats["zero_patch"] += row["zero_patch"]
        stats["cap"] += row["cap"]
        stats["errs"] += len(errs)
        if t.get("resolved"):
            stats["solved"] += 1

    n = stats["tasks"]
    print("tasks parsed: %d (solved %d)" % (n, stats["solved"]))
    print()
    print("RULE: get_status right after 2nd call + on new investigation (free, use often)")
    print("  never called get_status : %d/%d (%.0f%%)" % (stats["status0"], n, 100*stats["status0"]/n))
    print("  called >=3 times        : %d/%d (%.0f%%)" % (stats["status_ge3"], n, 100*stats["status_ge3"]/n))
    print()
    print("RULE: submit_patch ONCE, never twice")
    print("  submitted exactly once  : %d/%d" % (n - stats["submit_ne1"], n))
    print("  submitted 0 times       : %d" % sum(1 for r in per_task if r["n_submit"] == 0))
    print("  submitted >1 times      : %d  <-- VIOLATION" % stats["submit_gt1"])
    print()
    print("RULE: minimal fix with ONE edit_file call")
    print("  exactly 1 edit_file     : %d/%d" % (sum(1 for r in per_task if r["n_edit"] == 1), n))
    print("  >1 edit_file            : %d" % stats["edit_gt1"])
    print("  0 edit_file             : %d" % sum(1 for r in per_task if r["n_edit"] == 0))
    print()
    print("RULE: AT MOST 3-4 tool calls locating, then MAKE YOUR EDIT")
    print("  first edit after >4 calls: %d/%d (%.0f%%)" % (stats["locate_gt4"], n, 100*stats["locate_gt4"]/n))
    print("  never edited at all      : %d" % sum(1 for r in per_task if r["n_edit"] == 0))
    print()
    print("RULE: never conclude without a non-empty patch")
    print("  zero-patch submissions   : %d/%d (%.0f%%)" % (stats["zero_patch"], n, 100*stats["zero_patch"]/n))
    print()
    print("BUDGET: 28 calls / 8 min")
    print("  hit the 28-call cap      : %d/%d" % (stats["cap"], n))
    print("  total tool errors        : %d" % stats["errs"])

    # compliance vs outcome
    print("\n=== COMPLIANCE vs OUTCOME ===")
    for label, pred in [
        ("status never called", lambda r: r["n_status"] == 0),
        ("status called >=3", lambda r: r["n_status"] >= 3),
        ("first edit after <=4 calls", lambda r: r["locate"] <= 4),
        ("first edit after >4 calls", lambda r: r["locate"] > 4),
        ("exactly 1 edit_file", lambda r: r["n_edit"] == 1),
        ("zero patch", lambda r: r["zero_patch"]),
        ("hit call cap", lambda r: r["cap"]),
    ]:
        sub = [r for r in per_task if pred(r)]
        if not sub:
            continue
        k = sum(1 for r in sub if r["resolved"])
        print("  %-28s n=%3d  solved %2d = %5.1f%%" % (label, len(sub), k, 100*k/len(sub)))

    # save rows for later
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_v10_compliance.json")
    json.dump(per_task, open(out, "w"), indent=1)
    print("\nsaved", out)


if __name__ == "__main__":
    main()
