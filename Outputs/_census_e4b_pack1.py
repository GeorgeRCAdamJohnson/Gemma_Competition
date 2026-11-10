"""Census of the E4B pack-1 validation traces (Outputs/e4b_pack1_val/results: 8 score39 passes x 39 + runtime90),
to test the claimed pack-1 'bugs' against what actually happened. One question per section."""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

R = Path("Outputs/e4b_pack1_val/results")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
CALL = re.compile(r"\] \S+ (edit_file|write_file) \(")

runs = []
for tr in sorted(R.glob("node*/run_*/task_results.jsonl")):
    d = tr.parent
    kind = "runtime90" if (d.parent.name == "node0" and d.name == "run_1") else "score39"
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        lp = d / "logs" / f"{r['instance_id']}.log"
        log = ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace")) if lp.exists() else ""
        e = str(r.get("error") or "")
        b = ("solved" if r["resolved"] else "overflow" if "ContextWindow" in e else
             "timeout" if "session timeout" in e else "call_limit" if "turns budget" in e or "LLM turns" in e else
             "failed")
        runs.append(dict(r=r, log=log, b=b, kind=kind, src=str(d)))
print(f"runs {len(runs)}  by kind {Counter(x['kind'] for x in runs)}")
S = [x for x in runs if x["kind"] == "score39"]
print("score39 outcomes:", dict(Counter(x["b"] for x in S)))


def edits(log):
    out, lines = [], log.splitlines()
    for i, ln in enumerate(lines):
        m = CALL.search(ln)
        if not m:
            continue
        res = lines[i + 1] if i + 1 < len(lines) else ""
        if "\u2713" in res and "'status': 'ok'" in res:
            out.append((m.group(1), True, "ok"))
        else:
            k = re.search(r"error_type': '(\w+)'", res)
            kind = k.group(1) if k else ("arg_error" if "Invoking" in res else "other")
            if "old_string not found" in res:
                kind += ":not_found"
            out.append((m.group(1), False, kind))
    return out


for x in runs:
    x["ed"] = edits(x["log"])
    x["ok"] = sum(1 for _, ok, _ in x["ed"] if ok)
    x["fail"] = sum(1 for _, ok, _ in x["ed"] if not ok)
    x["attempts"] = len(re.findall(r"\(attempt \d of 3", x["log"]))
    x["retry"] = len(re.findall(r"RETRY:", x["log"]))
    x["calls"] = x["r"].get("tool_calls") or 0

print("\n=== 1. EDIT FAILURES (claim: rich_3063 ~7.1 edit_file misses/run; 3/4 of failed edits are verbatim resends)")
kinds = Counter(k for x in S for _, ok, k in x["ed"] if not ok)
n_ed = sum(len(x["ed"]) for x in S)
print(f"  score39: {n_ed} edit/write calls, {sum(x['fail'] for x in S)} failed ({100*sum(x['fail'] for x in S)/max(1,n_ed):.0f}%) kinds {kinds.most_common(6)}")
per = defaultdict(list)
for x in S:
    per[x["r"]["instance_id"]].append(x)
rows = sorted(per.items(), key=lambda kv: -st.mean(y["fail"] for y in kv[1]))
print(f"  {'task':15s} {'solve':>6s} {'fail/run':>8s} {'ok/run':>7s} {'neverLanded':>11s}")
for t, xs in rows[:12]:
    nl = sum(1 for y in xs if y["ed"] and y["ok"] == 0)
    print(f"  {t:15s} {sum(y['b']=='solved' for y in xs):2d}/{len(xs):<3d} {st.mean(y['fail'] for y in xs):8.1f} "
          f"{st.mean(y['ok'] for y in xs):7.1f} {nl:5d}/{len(xs)}")
# verbatim resend: consecutive failed edit_file calls with identical following-result text = same args (proxy)
dup = tot = 0
for x in S:
    lines = x["log"].splitlines()
    prev = None
    for i, ln in enumerate(lines):
        if CALL.search(ln) and "edit_file" in ln:
            res = lines[i + 1] if i + 1 < len(lines) else ""
            if "\u274c" in res:
                tot += 1
                if prev is not None and prev == res[:400]:
                    dup += 1
                prev = res[:400]
            else:
                prev = None
print(f"  consecutive identical failed edit_file results (resend proxy): {dup}/{tot}")
never = [x for x in S if x["ed"] and x["ok"] == 0]
noedit = [x for x in S if not x["ed"]]
print(f"  runs that tried to edit but NEVER landed one: {len(never)}/{len(S)} -> {dict(Counter(x['b'] for x in never))}")
print(f"  runs with NO edit attempt at all: {len(noedit)}/{len(S)} -> {dict(Counter(x['b'] for x in noedit))}")

print("\n=== 2. FAKE BUDGET (claim: '~28 calls / 8 min' in fixer.md vs real 80/30; triggers never fire)")
calls = [x["calls"] for x in S]
print(f"  tool_calls per run: median {st.median(calls)}, p90 {sorted(calls)[int(.9*len(calls))]}, max {max(calls)}; "
      f"runs >= 66 calls (where the <=14 trigger would fire on the real budget): {sum(c >= 66 for c in calls)}/{len(S)}")
for b in ("solved", "failed", "overflow", "timeout", "call_limit"):
    xs = [x for x in S if x["b"] == b]
    if xs:
        print(f"  {b:10s} n={len(xs):3d} calls median {st.median(x['calls'] for x in xs):4.0f} | dur median "
              f"{st.median(x['r']['duration_seconds'] for x in xs):5.0f}s | retries median {st.median(x['retry'] for x in xs)}")
gs = [len(re.findall(r"\] \S+ get_status", x["log"])) for x in S]
print(f"  get_status calls per run: median {st.median(gs)}; runs with 0: {sum(g == 0 for g in gs)}")
rem = [int(m) for x in S for m in re.findall(r"tool_calls_remaining['\"]?:\s*(\d+)", x["log"])]
if rem:
    print(f"  tool_calls_remaining values the fixer saw: min {min(rem)}, median {st.median(rem)}, <=14: {sum(r <= 14 for r in rem)}/{len(rem)}")

print("\n=== 3. RETRY LOOP (claim: empty-patch RETRY pushes edit_file; undo .py-only; git apply -R rc ignored)")
print(f"  runs reaching attempt 2+: {sum(x['retry'] >= 1 for x in S)}/{len(S)}; attempt 3: {sum(x['retry'] >= 2 for x in S)}")
conv = Counter()
for x in S:
    if x["retry"] >= 1:
        conv[x["b"]] += 1
print("  outcome of runs that retried:", dict(conv))
emp = sum(len(re.findall(r"no change in the repo", x["log"])) for x in S)
nonsrc = sum(len(re.findall(r"only non-source/test files changed", x["log"])) for x in S)
print(f"  gate 'no change - Re-apply it with edit_file' verdicts: {emp}; 'only non-source/test files' verdicts: {nonsrc}")
# after a 'no change' verdict: what did the next fixer turn do, and did that run end solved?
after = Counter()
for x in S:
    for m in re.finditer(r"no change in the repo", x["log"]):
        tail = x["log"][m.end():m.end() + 6000]
        nxt = re.search(r"\] \S+ (edit_file|write_file|run_command)", tail)
        after[(nxt.group(1) if nxt else "none", x["b"])] += 1
print("  next tool after a no-change verdict (tool, final outcome):", dict(after))
nonpy = Counter()
for x in S:
    for m in re.finditer(r"\] \S+ (?:edit_file|write_file) \(([^)]+)\)", x["log"]):
        f = m.group(1).split(",")[0].strip()
        if not f.endswith(".py"):
            nonpy[f.rsplit(".", 1)[-1] if "." in f else f] += 1
print("  edit/write targets that are NOT .py (undo would miss):", dict(nonpy.most_common(8)))

print("\n=== 4. TRUNCATION (claim: max_output 5000 + thinking 4096 -> truncated <|tool_call>)")
for pat, lab in ((r"tool call finished closing", "truncated tool call nudge"),
                 (r"reached the token limit while thinking", "max-tokens-in-thought nudge"),
                 (r"continuation_nudge|ended turn without calling submit_patch", "any continuation nudge")):
    k = [len(re.findall(pat, x["log"])) for x in S]
    print(f"  {lab:32s}: {sum(k)} events in {sum(1 for v in k if v)} runs")
chars = sorted(int(c) for x in S for c in re.findall(r"\((\d+) chars\)", x["log"]))
if chars:
    q = lambda p: chars[min(len(chars) - 1, int(p * len(chars)))]
    print(f"  turn text chars: median {q(.5)}, p99 {q(.99)}, max {chars[-1]}; turns > ~4000 tok (16k chars): "
          f"{sum(c > 16000 for c in chars)}/{len(chars)}")

print("\n=== 5. GRAPH TOOLS (claim: dead but advertised; get_code_subgraph = freeze surface)")
for t in ("get_code_subgraph", "get_code_neighbors", "search_similar_code", "write_file"):
    k = [len(re.findall(r"\] \S+ %s" % t, x["log"])) for x in runs]
    print(f"  {t:20s} calls: {sum(k)} in {sum(1 for v in k if v)} runs")

print("\n=== 6. WHERE THE 39-TASK LOSSES ARE (what a fix could recover)")
fails = [x for x in S if x["b"] != "solved"]
for b in ("failed", "overflow", "timeout", "call_limit"):
    xs = [x for x in fails if x["b"] == b]
    if xs:
        wp = sum(1 for x in xs if x["r"].get("agent_patch_size"))
        print(f"  {b:10s} {len(xs):3d} runs | with a patch {wp} | never edited {sum(1 for x in xs if x['ok'] == 0)}")
rate = {t: sum(y["b"] == "solved" for y in xs) / len(xs) for t, xs in per.items()}
band = Counter("always" if r == 1 else "never" if r == 0 else "flaky" for r in rate.values())
print(f"  task bands over {len(per)} tasks: {dict(band)}; expected solves/pass from flaky tasks "
      f"{sum(r for r in rate.values() if 0 < r < 1):.1f}, from always {sum(1 for r in rate.values() if r == 1)}")
R90 = [x for x in runs if x["kind"] == "runtime90"]
print(f"\n  runtime90: {len(R90)} runs, solved {sum(x['b']=='solved' for x in R90)}; outcomes {dict(Counter(x['b'] for x in R90))}")
