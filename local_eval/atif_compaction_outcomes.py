"""Real-run compaction vs outcome.  CPU only.

The real ATIF steps carry metrics.prompt_tokens.  A fall in prompt_tokens right after the prompt crossed ~14.3k is
the harness compacting the history (EventsCompactionConfig token_threshold=14336, event_retention_size=5).
For every real rich run: when did the first compaction happen (agent-step index / tool calls used), was an
edit_file call already made, and how did the run end (resolved / wrong patch / NULL, from kaggle_outcomes.json)?
Usage: python atif_compaction_outcomes.py
"""
import json, glob, re, statistics as st, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = json.load(open(ROOT / "local_eval" / "runs" / "kaggle_outcomes.json", encoding="utf-8"))
by_key = {}
for r in OUT:
    by_key.setdefault((r["version"], r["task"]), r)


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if len(rel) > 3 and rel[2] == "out":
        return f"{rel[0][7:]}/{rel[1]}"
    return rel[0][7:]


EDITS = {"edit_file", "write_file"}
rows = []
for p in glob.glob(str(ROOT / "submit_*" / "**" / "trace_rich_*.json"), recursive=True):
    pp = Path(p)
    try:
        j = json.load(open(pp, encoding="utf-8"))
    except Exception:
        continue
    task = re.search(r"trace_(rich_\d+)", p).group(1)
    ver = version_of(pp)
    steps = [s for s in (j.get("steps") or []) if s.get("source") == "agent"]
    seq = [s for s in steps if (s.get("metrics") or {}).get("prompt_tokens")]
    if len(seq) < 3:
        continue
    P = [s["metrics"]["prompt_tokens"] for s in seq]
    comp_idx = [k for k in range(1, len(P)) if P[k] < P[k - 1] and P[k - 1] >= 13500]
    # tool calls (excluding get_status) used before each agent step
    calls_before, n = [], 0
    first_edit_idx = None
    first_edit_call = None
    for k, s in enumerate(seq):
        calls_before.append(n)
        for tc in (s.get("tool_calls") or []):
            if tc.get("function_name") == "get_status":
                continue
            n += 1
            if tc.get("function_name") in EDITS and first_edit_idx is None:
                first_edit_idx, first_edit_call = k, n
    out = by_key.get((ver, task))
    rows.append(dict(ver=ver, task=task, n_steps=len(seq), calls=n, comp_idx=comp_idx,
                     first_comp_call=(calls_before[comp_idx[0]] if comp_idx else None),
                     first_edit_idx=first_edit_idx, first_edit_call=first_edit_call,
                     maxP=max(P), outcome=(out or {}).get("tag"), resolved=(out or {}).get("resolved")))

print("traces:", len(rows), " joined with outcome:", sum(1 for r in rows if r["outcome"]))
j_rows = [r for r in rows if r["outcome"]]


def summarize(name, rs):
    if not rs:
        print(f"  {name:48s} n=0")
        return
    res = sum(1 for r in rs if r["resolved"])
    nul = sum(1 for r in rs if str(r["outcome"]).startswith("NULL"))
    wr = sum(1 for r in rs if r["outcome"] == "wrong-patch")
    print(f"  {name:48s} n={len(rs):3d}  resolved={res:3d} ({100*res/len(rs):4.0f}%)  wrong-patch={wr:3d}  NULL={nul:3d} ({100*nul/len(rs):4.0f}%)")


print("\nhow many compactions per run (all traces):", collections.Counter(len(r["comp_idx"]) for r in rows))
print("\nOUTCOME by compaction status (joined runs):")
summarize("no compaction", [r for r in j_rows if not r["comp_idx"]])
summarize("compacted, first edit BEFORE compaction", [r for r in j_rows if r["comp_idx"] and r["first_edit_idx"] is not None and r["first_edit_idx"] < r["comp_idx"][0]])
summarize("compacted, first edit AFTER compaction", [r for r in j_rows if r["comp_idx"] and r["first_edit_idx"] is not None and r["first_edit_idx"] >= r["comp_idx"][0]])
summarize("compacted, NO edit_file at all", [r for r in j_rows if r["comp_idx"] and r["first_edit_idx"] is None])
summarize("no compaction, edit made", [r for r in j_rows if not r["comp_idx"] and r["first_edit_idx"] is not None])
summarize("no compaction, NO edit_file", [r for r in j_rows if not r["comp_idx"] and r["first_edit_idx"] is None])

fc = [r["first_comp_call"] for r in rows if r["first_comp_call"] is not None]
fe = [r["first_edit_call"] for r in rows if r["first_edit_call"] is not None]
print(f"\nfirst compaction happens after tool call #: median={st.median(fc):.0f} p25={sorted(fc)[len(fc)//4]} p75={sorted(fc)[3*len(fc)//4]} (n={len(fc)})")
print(f"first edit_file is tool call #:            median={st.median(fe):.0f} p25={sorted(fe)[len(fe)//4]} p75={sorted(fe)[3*len(fe)//4]} (n={len(fe)})")
both = [r for r in rows if r["first_comp_call"] is not None and r["first_edit_call"] is not None]
before = sum(1 for r in both if r["first_edit_call"] <= r["first_comp_call"])
print(f"runs with both compaction and an edit: {len(both)}; edit came before the first compaction in {before}")
# time-to-compaction vs the budget: how many calls are LEFT after the first compaction
left = [r["calls"] - r["first_comp_call"] for r in rows if r["first_comp_call"] is not None]
print(f"tool calls remaining after the first compaction: median={st.median(left):.0f} mean={st.mean(left):.1f}")
