"""Census on every ca5-family 31B trace we hold (presubmit_85, timeout_ab, bc_check).

Q1 (Grok / forum topic: "44/44 overflowed sessions submitted empty diffs"): when a 31B ca5 run hits a
    context-window overflow, is the patch empty? Did the model have an edit on disk before the overflow?
Q2: how often do edit_file calls fail ("old_string not found" etc.) on 31B ca5, and does the failing
    run recover (later successful edit) or die?

Outcome buckets follow the earlier convention: resolved -> solved; 'ContextWindow' in error ->
overflow; 'session timeout' -> timeout; 'turns budget' / 'LLM turns' -> call_limit; else failed.
"""
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
TARS = [
    "Outputs/ca5_31b_presubmit_85/results.tar.gz",
    "Outputs/ca5_31b_timeout_ab/results.tar.gz",
    "Outputs/ca5_31b_bc_check/results.tar.gz",
]


def bucket(r):
    e = str(r.get("error") or "")
    if r.get("resolved"):
        return "solved"
    if "ContextWindow" in e or "context length" in e.lower():
        return "overflow"
    if "session timeout" in e:
        return "timeout"
    if "turns budget" in e or "LLM turns" in e:
        return "call_limit"
    if e:
        return "other_err"
    return "failed"


runs = []
for tp in TARS:
    with tarfile.open(tp) as tf:
        names = {m.name: m for m in tf.getmembers()}
        for n, m in names.items():
            if not n.endswith("task_results.jsonl"):
                continue
            arm_dir = n.rsplit("/", 1)[0]
            for line in tf.extractfile(m).read().decode("utf-8", "replace").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                lp = f"{arm_dir}/logs/{r['instance_id']}.log"
                log = ""
                if lp in names:
                    log = ANSI.sub("", tf.extractfile(names[lp]).read().decode("utf-8", "replace"))
                runs.append(dict(src=tp.split("/")[1], arm=arm_dir, r=r, b=bucket(r), log=log))

print(f"{len(runs)} runs from {len(TARS)} archives")
print("outcomes:", dict(Counter(x["b"] for x in runs)))

CALL = re.compile(r"\] \S+ (edit_file|write_file) \(")


def edits(log):
    """[(tool, ok, kind)] for each edit_file/write_file call, judged by the immediate result line."""
    out = []
    lines = log.splitlines()
    for i, ln in enumerate(lines):
        m = CALL.search(ln)
        if not m:
            continue
        res = lines[i + 1] if i + 1 < len(lines) else ""
        if "\u2713" in res and "'status': 'ok'" in res:
            out.append((m.group(1), True, "ok"))
        elif "\u274c" in res or "error" in res:
            k = re.search(r"error_type': '(\w+)'", res)
            kind = k.group(1) if k else ("arg_error" if "Invoking" in res else "error")
            if "old_string not found" in res:
                kind += ":not_found"
            elif "occurrences" in res or "multiple" in res.lower():
                kind += ":multi"
            out.append((m.group(1), False, kind))
        else:
            out.append((m.group(1), None, "no_result_line"))  # run cut off right after the call
    return out


for x in runs:
    x["ed"] = edits(x["log"])
    x["ok_edits"] = sum(1 for _, ok, _ in x["ed"] if ok)

# ---------- Q0 does any bucket lose an on-disk edit?
print("\n=== Q0: runs with >=1 SUCCESSFUL edit/write but EMPTY final patch (lost work) ===")
for b in ("solved", "failed", "timeout", "call_limit", "overflow", "other_err"):
    xs = [x for x in runs if x["b"] == b]
    if not xs:
        continue
    had = [x for x in xs if x["ok_edits"]]
    lost = [x for x in had if x["r"]["agent_patch_size"] == 0]
    print(f"  {b:10s} n={len(xs):3d}  with ok edit={len(had):3d}  ok edit but empty patch={len(lost):3d}")
    for x in lost[:6]:
        print(f"      {x['src'][:20]:20s} {x['arm'][-24:]:24s} {x['r']['instance_id']:15s} "
              f"ok_edits={x['ok_edits']} dur={x['r']['duration_seconds']}")

# ---------- Q1 overflow -> patch?
print("\n=== Q1: overflow runs ===")
ov = [x for x in runs if x["b"] == "overflow"]
for x in ov:
    r, log = x["r"], x["log"]
    n_edit = x["ok_edits"]
    n_sub = len(re.findall(r"\] \S+ submit_patch", log))
    print(f"  {x['src'][:22]:22s} {r['instance_id']:16s} patch={r['agent_patch_size']:6d}B "
          f"test_exit={r['test_exit_code']:3d} edits~{n_edit:2d} submits~{n_sub} "
          f"err={str(r['error'])[:70]!r}")
k_nonempty = sum(x["r"]["agent_patch_size"] > 0 for x in ov)
k_tested = sum(x["r"]["test_exit_code"] not in (-1, None) for x in ov)
print(f"  overflow runs: {len(ov)}; non-empty patch: {k_nonempty}; reached pytest: {k_tested}")

# patch sizes by bucket (does any bucket systematically lose patches?)
print("\n  empty-patch rate by bucket:")
for b in ("solved", "failed", "timeout", "call_limit", "overflow", "other_err"):
    xs = [x for x in runs if x["b"] == b]
    if xs:
        e = sum(x["r"]["agent_patch_size"] == 0 for x in xs)
        print(f"    {b:10s} n={len(xs):3d} empty={e:3d} ({100*e/len(xs):.0f}%)")

# ---------- Q2 edit_file failures
print("\n=== Q2: edit_file outcomes ===")
fail_kinds = Counter()
calls = Counter()
for x in runs:
    for tool, ok, kind in x["ed"]:
        calls[(tool, ok)] += 1
        if ok is False:
            fail_kinds[f"{tool}:{kind}"] += 1
for tool in ("edit_file", "write_file"):
    n = sum(v for (t, _), v in calls.items() if t == tool)
    f = calls[(tool, False)]
    print(f"  {tool}: {n} calls, {f} failed ({100*f/max(1,n):.1f}%), {calls[(tool, None)]} cut off")
print("  failure kinds:", fail_kinds.most_common(8))
wf = [x for x in runs if any(ok is False for _, ok, _ in x["ed"])]
print(f"  runs with >=1 failed edit: {len(wf)} / {len(runs)} -> outcomes {dict(Counter(x['b'] for x in wf))}")
nf = [x for x in runs if x["ed"] and not any(ok is False for _, ok, _ in x["ed"])]
print(f"  runs with edits, none failed: {len(nf)} -> outcomes {dict(Counter(x['b'] for x in nf))}")
dead = [x for x in runs if x["ed"] and x["ok_edits"] == 0]
print(f"  runs that tried to edit but NEVER succeeded: {len(dead)} -> outcomes {dict(Counter(x['b'] for x in dead))}")
for x in dead:
    print(f"      {x['src'][:20]:20s} {x['r']['instance_id']:15s} {x['b']:9s} "
          f"attempts={len(x['ed'])} kinds={Counter(k for _, _, k in x['ed'])}")
# solve rate conditional on edit failures (is a failed edit a marker of a lost task?)
for label, xs in (("with failed edit", wf), ("clean edits", nf)):
    s = sum(x["b"] == "solved" for x in xs)
    print(f"  solve rate {label:17s}: {s}/{len(xs)} ({100*s/max(1,len(xs)):.0f}%)")
