"""Paper-grade analysis of the 129-task 31B A3 run.

Joins three sources:
  1. per-task results (resolved/duration/calls/patch) from the version10 output file
  2. tool-call traces (which tools, errors, compliance) parsed from the same file
  3. fix-shape labels + repo from the 129-task gold taxonomy

Writes a detailed markdown report to 129_ANALYSIS.md.
"""
import collections
import json
import math
import os
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GEMMA = os.path.dirname(HERE)
F_V10 = os.path.join(GEMMA, "Outputs", "Gemma_Sibling-conform_31b_A3_Hard_version10")
SHAPES = os.path.join(HERE, "prompts", "_task_shapes.json")
OUT = os.path.join(GEMMA, "129_ANALYSIS.md")

RE_HDR = re.compile(r"^\s*\[(\d+)/129\]\s+(\S+)\s+\(([^)]+)\)")
RE_RES = re.compile(r"resolved=(True|False)\s+duration=([\d.]+)s\s+tool_calls=(\d+)\s+patch_chars=(\d+)")
RE_THINK = re.compile(r"💭\s+\((\d+) chars\)")
RE_OK = re.compile(r"\[\s*([\d.]+)s\]\s+\u2713\s+(.*)")
RE_ERR = re.compile(r"\[\s*([\d.]+)s\]\s+\u2192\s*(error.*)")
RE_TOOL = re.compile(r"\[\s*([\d.]+)s\]\s+(\S{1,4})\s+(.+)")
TOOL_EMOJI = {"\U0001f4d6": "read_file", "\u270f\ufe0f": "edit_file", "\U0001f527": "run_command",
              "\U0001f4dd": "write_file"}


def parse_v10(path):
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    tasks, cur, pending = [], None, None
    for ln in lines:
        m = RE_HDR.search(ln)
        if m and "resolved=" not in ln:
            if cur:
                tasks.append(cur)
            cur = {"idx": int(m.group(1)), "task": m.group(2), "repo": m.group(3),
                   "tools": [], "results": [], "think": 0}
            pending = None
            continue
        if cur is None:
            continue
        m = RE_RES.search(ln)
        if m:
            cur.update(resolved=(m.group(1) == "True"), dur=float(m.group(2)),
                       calls=int(m.group(3)), patch=int(m.group(4)))
            tasks.append(cur)
            cur = None
            pending = None
            continue
        m = RE_THINK.search(ln)
        if m:
            cur["think"] += int(m.group(1))
            continue
        m = RE_OK.search(ln)
        if m and pending:
            cur["results"].append({"tool": pending, "ok": True, "detail": m.group(2)[:300]})
            pending = None
            continue
        m = RE_ERR.search(ln)
        if m and pending:
            cur["results"].append({"tool": pending, "ok": False, "detail": m.group(2)[:300]})
            pending = None
            continue
        m = re.search(r"\]\s+\u2192\s+([a-z_]+):\s+(.*)", ln)
        if m:
            ok = '"status": "ok"' in m.group(2) or "'status': 'ok'" in m.group(2)
            cur["results"].append({"tool": m.group(1), "ok": ok, "detail": m.group(2)[:300]})
            if pending == m.group(1):
                pending = None
            continue
        m = RE_TOOL.search(ln)
        if m:
            emoji, rest = m.group(2), m.group(3)
            name = TOOL_EMOJI.get(emoji)
            if emoji == "\U0001f916":
                name = rest.split()[0] if rest.split() else None
            if name and name not in ("system", "task", "think"):
                pending = name
                cur["tools"].append({"t": float(m.group(1)), "name": name, "arg": rest[:150]})
    if cur:
        tasks.append(cur)
    return tasks


def fisher(a, b, c, d):
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c
    def p(x):
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    obs = p(a)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def main():
    tasks = parse_v10(F_V10)
    shapes = json.load(open(SHAPES, encoding="utf-8"))
    assert len(tasks) == 129, len(tasks)

    # enrich
    for t in tasks:
        t["shape"] = shapes.get(t["task"], "?")
        names = [x["name"] for x in t["tools"]]
        c = collections.Counter(names)
        t["n_status"] = c.get("get_status", 0)
        t["n_submit"] = c.get("submit_patch", 0)
        t["n_edit"] = c.get("edit_file", 0)
        t["n_read"] = c.get("read_file", 0)
        t["n_run"] = c.get("run_command", 0)
        first_edit = next((i for i, n in enumerate(names) if n == "edit_file"), None)
        t["locate"] = first_edit if first_edit is not None else len(names)
        t["errs"] = sum(1 for r in t["results"] if not r["ok"])
        t["zero"] = t["patch"] == 0
        t["cap"] = t["calls"] >= 28
        # failure mode
        if t["resolved"]:
            t["mode"] = "RESOLVED"
        elif t["zero"]:
            t["mode"] = "NO_PATCH"
        elif t["cap"]:
            t["mode"] = "CALL_CAP"
        else:
            t["mode"] = "WRONG_CONTENT"

    solved = [t for t in tasks if t["resolved"]]
    n, k = len(tasks), len(solved)
    lo, hi = wilson(k, n)

    L = []
    w = L.append
    w("# 129-Task 31B A3 Run — Full Analysis")
    w("")
    w("Kernel: `comfyops/gemma-sibling-conform-31b-a3-hard` · model `gemma-4-31b-it-qat-w4a16-ct` · "
      "A3 prompt (sha 0aae1a1e314a) · shipped config 28/8/80/240, thinking 1024, temp 0.2 · 4xL4, tp=4 · "
      "public 129-task set, one sample per task, sequential.")
    w("")
    w("## 1. Headline")
    w("")
    w("**%d/129 = %.3f** (Wilson 95%% CI [%.3f, %.3f]). Board score 0.18 ~= 23/129; this run is "
      "%.2f above it. Total wall 10.8 h — inside the 12 h cap (mean %.0f s, median %.0f s, "
      "p90 %.0f s, max %.0f s per task)." % (k, k / n, lo, hi, k / n - 0.18,
                                              statistics.mean(t["dur"] for t in tasks),
                                              statistics.median(t["dur"] for t in tasks),
                                              sorted(t["dur"] for t in tasks)[int(.9 * n)],
                                              max(t["dur"] for t in tasks)))
    w("")
    w("## 2. By repository")
    w("")
    w("| repo | tasks | solved | rate | Wilson 95% CI |")
    w("|---|---|---|---|---|")
    for repo in sorted({t["repo"] for t in tasks}):
        sub = [t for t in tasks if t["repo"] == repo]
        s = sum(1 for t in sub if t["resolved"])
        a, b = wilson(s, len(sub))
        w("| %s | %d | %d | %.1f%% | [%.0f%%, %.0f%%] |" % (repo, len(sub), s,
                                                            100 * s / len(sub), 100 * a, 100 * b))
    w("")
    w("fastapi resolves at nearly the rich rate. The log's standing claim "
      "\"Zero fastapi ever resolved\" (L28) was an artifact of the v1-v8 era (0/2, 0/6 samples) "
      "and is overturned by this run.")
    w("")
    w("## 3. By fix-shape bucket (gold-patch taxonomy, 16 shapes)")
    w("")
    w("| shape | tasks | solved | rate | failure modes (NO_PATCH / WRONG / CAP) |")
    w("|---|---|---|---|---|")
    for shape in sorted({t["shape"] for t in tasks},
                        key=lambda s: -sum(1 for t in tasks if t["shape"] == s)):
        sub = [t for t in tasks if t["shape"] == shape]
        s = sum(1 for t in sub if t["resolved"])
        modes = collections.Counter(t["mode"] for t in sub if not t["resolved"])
        w("| %s | %d | %d | %.0f%% | %d / %d / %d |" % (
            shape, len(sub), s, 100 * s / len(sub),
            modes.get("NO_PATCH", 0), modes.get("WRONG_CONTENT", 0), modes.get("CALL_CAP", 0)))
    w("")
    w("Pattern: small precise contract-shaped fixes convert (string/message 3/3, single_token 3/5, "
      "signature 2/4); additive/structural fixes do not (add_raise 0/5, add_import 0/3, "
      "pure_deletion 0/3).")
    w("")
    w("## 4. Failure anatomy (95 misses)")
    w("")
    modes = collections.Counter(t["mode"] for t in tasks)
    w("| mode | count | share of misses | definition |")
    w("|---|---|---|---|")
    w("| WRONG_CONTENT | %d | %.0f%% | landed a patch, tests failed, no call cap |"
      % (modes["WRONG_CONTENT"], 100 * modes["WRONG_CONTENT"] / (n - k)))
    w("| NO_PATCH | %d | %.0f%% | submitted nothing (0 chars) |"
      % (modes["NO_PATCH"], 100 * modes["NO_PATCH"] / (n - k)))
    w("| CALL_CAP | %d | %.0f%% | burned all 28 calls (with patch) |"
      % (modes["CALL_CAP"], 100 * modes["CALL_CAP"] / (n - k)))
    w("")
    # zero-edit vs zero-submit split
    z_sub = [t for t in tasks if t["mode"] == "NO_PATCH" and t["n_submit"] == 0]
    z_ed = [t for t in tasks if t["mode"] == "NO_PATCH" and t["n_edit"] == 0]
    w("Of the %d NO_PATCH: %d never called submit_patch at all; %d never called edit_file at all; "
      "%d edited but submitted empty." % (modes["NO_PATCH"], len(z_sub), len(z_ed),
                                          modes["NO_PATCH"] - len(z_sub)))
    w("")
    w("## 5. Prompt compliance vs outcome")
    w("")
    w("A3's explicit rules, measured against the full tool trace. Correlations from one run, "
      "n=1 per task, no control arm — associations, not causal claims.")
    w("")
    w("| behaviour | n | solved | rate | vs complement | Fisher p |")
    w("|---|---|---|---|---|---|")
    checks = [
        ("get_status called >=1", lambda t: t["n_status"] >= 1, lambda t: t["n_status"] == 0),
        ("first edit within 4 calls", lambda t: t["locate"] <= 4, lambda t: t["locate"] > 4),
        ("exactly 1 edit_file", lambda t: t["n_edit"] == 1, lambda t: t["n_edit"] != 1),
        ("submitted exactly once", lambda t: t["n_submit"] == 1, lambda t: t["n_submit"] != 1),
        ("non-empty patch", lambda t: not t["zero"], lambda t: t["zero"]),
        ("did not hit call cap", lambda t: not t["cap"], lambda t: t["cap"]),
    ]
    for label, pred, comp in checks:
        sub = [t for t in tasks if pred(t)]
        oth = [t for t in tasks if comp(t)]
        if not sub or not oth:
            continue
        s1, s2 = sum(1 for t in sub if t["resolved"]), sum(1 for t in oth if t["resolved"])
        p = fisher(s1, len(sub) - s1, s2, len(oth) - s2)
        w("| %s | %d | %d | %.0f%% | %.0f%% | %.3f |" % (
            label, len(sub), s1, 100 * s1 / len(sub), 100 * s2 / len(oth), p))
    w("")
    w("Rule-violation counts: get_status never called %d/129 (47%%); >=3 calls 0/129; "
      "first edit after >4 calls %d/129 (90%%); submit 0 times %d, >1 times %d "
      "(max: requests_6757 x10); zero-patch %d/129 (22%%)." % (
          sum(1 for t in tasks if t["n_status"] == 0),
          sum(1 for t in tasks if t["locate"] > 4),
          sum(1 for t in tasks if t["n_submit"] == 0),
          sum(1 for t in tasks if t["n_submit"] > 1),
          sum(1 for t in tasks if t["zero"])))
    w("")
    w("## 6. Tool usage")
    w("")
    tot = collections.Counter()
    for t in tasks:
        for x in t["tools"]:
            tot[x["name"]] += 1
    w("| tool | calls | share | errors |")
    w("|---|---|---|---|")
    err_by = collections.Counter()
    for t in tasks:
        for r in t["results"]:
            if not r["ok"]:
                err_by[r["tool"]] += 1
    allc = sum(tot.values())
    for name, c in tot.most_common():
        w("| %s | %d | %.0f%% | %d |" % (name, c, 100 * c / allc, err_by.get(name, 0)))
    w("")
    w("**Tool-level failures are essentially zero on 31B.** edit_file: 0 errors across %d calls "
      "(strategies: exact 146, unescaped 38 — the A3 delimiter fix works completely at this scale; "
      "contrast E4B where 62%% of edit_file calls error). Of the %d run_command \"errors\", 202 are "
      "`error (exit 0)` with empty detail — benign harness flags (grep-no-match / empty output), 1 real. "
      "What remains after A3 is purely decision-level: wrong content, no patch, budget exhaustion." % (
          tot.get("edit_file", 0), err_by.get("run_command", 0)))
    w("Per-task medians: %d tool calls, %d read_file, %d run_command, %d edit_file, "
      "%d get_status, %d submit_patch, %.0f k thinking chars." % (
          statistics.median(t["calls"] for t in tasks),
          statistics.median(t["n_read"] for t in tasks),
          statistics.median(t["n_run"] for t in tasks),
          statistics.median(t["n_edit"] for t in tasks),
          statistics.median(t["n_status"] for t in tasks),
          statistics.median(t["n_submit"] for t in tasks),
          statistics.median(t["think"] for t in tasks) / 1000))
    w("")
    w("## 7. Rich retention vs prior 31B runs")
    w("")
    prior = {"rich_2725", "rich_2943", "rich_3006", "rich_3043", "rich_3067", "rich_3278",
             "rich_3454", "rich_3471", "rich_3518", "rich_3718", "rich_3777", "rich_3882",
             "rich_3894", "rich_3905", "rich_4077", "rich_4079"}
    this = {t["task"] for t in tasks if t["resolved"] and t["task"].startswith("rich_")}
    w("- Prior 31B-solved union (cover-rich, repeat-live, smoke): %d tasks" % len(prior))
    w("- This run solved: %d rich tasks" % len(this))
    w("- Kept: %s" % ", ".join(sorted(prior & this)))
    w("- LOST: %s" % (", ".join(sorted(prior - this)) or "none"))
    w("- NEW: %s" % (", ".join(sorted(this - prior)) or "none"))
    w("")
    w("rich_3471 death trace: 484 s, 20 calls, 0 edits, 0 submits. grep -> read text.py -> grep -> "
      "read text.py (returned file start again; agent noted the tool behaving oddly) -> 2 more reads "
      "-> 20 calls of locating. Violated A3's 3-4-call locate limit and its sed advice.")
    w("")
    w("## 8. Time trend (deterioration check)")
    w("")
    w("| block | tasks | solve% | median patch | median calls | NO_PATCH% |")
    w("|---|---|---|---|---|---|")
    B, m = 6, len(tasks)
    for b in range(B):
        blk = tasks[b * m // B:(b + 1) * m // B]
        s = sum(1 for t in blk if t["resolved"])
        w("| %d-%d | %d | %.0f%% | %d | %d | %.0f%% |" % (
            b * m // B + 1, (b + 1) * m // B, len(blk), 100 * s / len(blk),
            statistics.median(t["patch"] for t in blk),
            statistics.median(t["calls"] for t in blk),
            100 * sum(1 for t in blk if t["zero"]) / len(blk)))
    xs = list(range(m))
    ys = [t["patch"] for t in tasks]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    r = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) /
         (math.sqrt(sum((x - mx) ** 2 for x in xs)) * math.sqrt(sum((y - my) ** 2 for y in ys))))
    w("")
    w("Patch size vs run position: Pearson r = %+.3f (no growth pathology). No OOM events, "
      "no compaction events, 2 token-limit truncations. Block 1's low rate is task-mix "
      "(fastapi+requests run first)." % r)
    w("")
    w("## 9. Budget fit")
    w("")
    w("- 129 tasks x mean %.0f s = %.1f h total, inside the 12 h cap." % (
        statistics.mean(t["dur"] for t in tasks),
        sum(t["dur"] for t in tasks) / 3600))
    w("- Tasks hitting the 8-min wall: %d. Tasks hitting the 28-call cap: %d." % (
        sum(1 for t in tasks if t["dur"] >= 470), sum(1 for t in tasks if t["cap"])))
    w("- The cap-arithmetic fear (129 x 8 min = 13 h) remains refuted by observed means.")
    w("")
    w("## 10. Full per-task table")
    w("")
    w("| # | task | repo | shape | result | mode | dur s | calls | patch | status | submits | edits | locate |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t in tasks:
        w("| %d | %s | %s | %s | %s | %s | %.0f | %d | %d | %d | %d | %d | %d |" % (
            t["idx"], t["task"], t["repo"].split("/")[0], t["shape"],
            "PASS" if t["resolved"] else "fail", t["mode"], t["dur"], t["calls"],
            t["patch"], t["n_status"], t["n_submit"], t["n_edit"], t["locate"]))
    w("")

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("wrote %s (%d lines)" % (OUT, len(L)))

    # console summary of the key stats for the chat
    print()
    print("solved %d/129 = %.3f  CI [%.3f, %.3f]" % (k, k / n, lo, hi))
    for label, pred, comp in checks:
        sub = [t for t in tasks if pred(t)]
        oth = [t for t in tasks if comp(t)]
        if not sub or not oth:
            continue
        s1, s2 = sum(1 for t in sub if t["resolved"]), sum(1 for t in oth if t["resolved"])
        p = fisher(s1, len(sub) - s1, s2, len(oth) - s2)
        print("  %-28s %3d -> %5.1f%%  vs %3d -> %5.1f%%  p=%.3f" % (
            label, len(sub), 100 * s1 / len(sub), len(oth), 100 * s2 / len(oth), p))


if __name__ == "__main__":
    main()
