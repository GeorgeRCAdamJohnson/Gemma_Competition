"""Discovery 2: what do WINNING attempts do differently, holding task, experiment and arm fixed?
Strata = (exp, arm, task) with >= 3 solved and >= 3 failed traced E4B attempts. For each behaviour feature: mean
(solved - failed) within each stratum, then across strata: mean difference, standardized (pooled-sd) effect, and how
many strata point each way with a two-sided sign test. Bonferroni threshold for ~30 features: p < 0.0017.
Correlational: a feature can be a symptom of being on the right track rather than a cause."""
import json
import math
import sqlite3
import statistics as st
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
FEATS = ["n_calls", "n_read_file", "n_run_command", "n_grep", "n_sed", "n_cat", "n_find_ls", "n_pytest", "n_script_write",
         "n_edit_ok", "n_edit_fail", "n_failed_calls", "n_repeat_calls", "n_edited_files", "distinct_files_read",
         "calls_before_first_edit", "s_before_first_edit", "first_edit_gold", "edited_any_gold", "n_gold_touches",
         "saw_gold_before_first_edit", "n_iterations", "gate_rejected", "max_prompt_tokens", "thinking_chars", "wall_s",
         "n_get_status", "n_skill"]
cols = ", ".join(f"f.{c}" for c in FEATS)
rows = q(f"""SELECT a.exp, a.arm, a.task, a.resolved, a.patch_chars, f.tool_sequence, t.trace_id, {cols}
             FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
             WHERE f.basis = 'trace' AND a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL AND a.arm IS NOT NULL""")
# derived features
extra = {}
for tid, in q("SELECT DISTINCT t.trace_id FROM traces t"):
    pass
early = defaultdict(dict)
for tid, idx, tool, ck, tg, author in q("""SELECT trace_id, idx, tool, cmd_kind, touches_gold, author FROM tool_calls
                                           WHERE idx < 4 ORDER BY trace_id, idx"""):
    e = early[tid]
    e["gold_in_first4"] = max(e.get("gold_in_first4", 0), tg or 0)
    e.setdefault("first_tool", f"{tool}:{ck}" if ck else tool)
post = defaultdict(lambda: {"verify_after_edit": 0})
first_edit = dict(q("SELECT trace_id, first_edit_idx FROM attempt_features WHERE first_edit_idx IS NOT NULL"))
for tid, idx, ck, author in q("""SELECT trace_id, idx, cmd_kind, author FROM tool_calls WHERE cmd_kind IN ('pytest','python')
                                 AND author IN ('fixer','sibling_conform_agent','swe_agent')"""):
    if tid in first_edit and idx > first_edit[tid]:
        post[tid]["verify_after_edit"] = 1
strata = defaultdict(lambda: {0: [], 1: []})
for r in rows:
    exp, arm, task, res, patch, seq, tid = r[:7]
    vals = dict(zip(FEATS, r[7:]))
    vals["patch_chars"] = patch
    vals["gold_in_first4"] = early[tid].get("gold_in_first4", 0)
    vals["verify_after_edit"] = post[tid]["verify_after_edit"]
    strata[(exp, arm, task)][int(res)].append(vals)
usable = {k: v for k, v in strata.items() if len(v[1]) >= 3 and len(v[0]) >= 3}
print(f"strata (exp, arm, task) with >= 3 solved and >= 3 failed: {len(usable)} "
      f"({sum(len(v[0]) + len(v[1]) for v in usable.values())} attempts, {len({k[2] for k in usable})} tasks)\n")


def sign_p(pos, neg):
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


out = []
for feat in FEATS + ["patch_chars", "gold_in_first4", "verify_after_edit"]:
    diffs, effs = [], []
    for v in usable.values():
        s = [x[feat] for x in v[1] if x[feat] is not None]
        f = [x[feat] for x in v[0] if x[feat] is not None]
        if len(s) < 2 or len(f) < 2:
            continue
        d = st.mean(s) - st.mean(f)
        sd = math.sqrt((st.pvariance(s) + st.pvariance(f)) / 2) or None
        diffs.append(d)
        if sd:
            effs.append(d / sd)
    if not diffs:
        continue
    pos, neg = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    out.append((feat, len(diffs), st.mean(diffs), st.mean(effs) if effs else float("nan"), pos, neg, sign_p(pos, neg)))
print(f"{'feature':28s} strata  mean(solved-failed)  std effect  solved>failed  solved<failed  sign p")
for f, n, d, e, p_, n_, pv in sorted(out, key=lambda x: x[6]):
    flag = "  ***" if pv < 0.0017 else "  *" if pv < 0.05 else ""
    print(f"  {f:26s} {n:5d}   {d:+12.2f}        {e:+6.2f}      {p_:5d}         {n_:5d}      {pv:.2g}{flag}")
json.dump([dict(feature=f, strata=n, mean_diff=d, effect=e, pos=p_, neg=n_, p=pv) for f, n, d, e, p_, n_, pv in out],
          open("Outputs/_disc_within_task.json", "w"), indent=1)
