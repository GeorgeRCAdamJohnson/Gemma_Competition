"""Check kb/attempts.sqlite against numbers already recorded in GEMMA_EXPERIMENT_LOG.md / HANDOFF.md, and check the
dedupe for false merges. Exit 1 on any failed check.
usage: python kb/attemptdb/verify.py"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
db = sqlite3.connect(ROOT / "kb" / "attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: got {got} want {want}")


print("1. recorded results reproduce")
# HANDOFF: p5 paired eval 178 p5 vs 189 base verified solves in 624 pairs
r = dict(q("SELECT arm, SUM(verified) FROM attempts_unique WHERE exp='kaggle_tool_lora_p5_repeat39' GROUP BY arm"))
n = dict(q("SELECT arm, COUNT(*) FROM attempts_unique WHERE exp='kaggle_tool_lora_p5_repeat39' GROUP BY arm"))
check("p5 adapter verified", r.get("adapter"), 178)
check("p5 base verified", r.get("base"), 189)
check("p5 attempts per arm", (n.get("adapter"), n.get("base")), (624, 624))
# Colab batch 2 progress.json pass totals == DB per (arm, round), whichever source survived dedupe
P = json.loads((ROOT / "Outputs/ab_logs/e4b_ab2_20261111/progress.json").read_text())["passes"]
want = {(p["arm"], p["round"]): p["solved"] for p in P}
got = {}
for p in P:
    ids = [x["id"] for x in p["rows"]]
    # an attempt of that pass may live under any exp after dedupe: count via the summary rows' surviving copies
    rows = q("""SELECT COALESCE(u.resolved, 0) FROM attempts s JOIN attempts u
                ON u.id = COALESCE(s.dup_of, s.id)
                WHERE s.source='summary' AND s.source_path='Outputs/ab_logs/e4b_ab2_20261111/progress.json'
                AND s.arm=? AND s.round=?""", p["arm"], p["round"])
    got[(p["arm"], p["round"])] = sum(x[0] for x in rows)
check("batch 2: every pass total", sum(got[k] == want[k] for k in want), len(want))
# Repair-decisions rounds 6-10: 10, 11, 13, 11, 14 verified (HANDOFF)
rd = q("""SELECT round, SUM(verified) FROM attempts_unique WHERE exp='kaggle_e4b_repair_decisions_seed39_r6_r10'
          GROUP BY round ORDER BY round""")
check("repair-decisions r6-r10 verified", [x[1] for x in rd], [10, 11, 13, 11, 14])

print("2. dedupe sanity")
# a single pass file never holds the same attempt twice -> duplicates inside one (source_path, arm, round) = collision
coll = q("""SELECT COUNT(*) FROM attempts a JOIN attempts k ON a.dup_of = k.id
            WHERE a.source_path = k.source_path AND COALESCE(a.arm,'') = COALESCE(k.arm,'')
            AND COALESCE(a.round,-1) = COALESCE(k.round,-1) AND COALESCE(a.node,-1) = COALESCE(k.node,-1)""")[0][0]
check("same-pass false merges", coll, 0)
cross = q("""SELECT COUNT(*) FROM attempts a JOIN attempts k ON a.dup_of = k.id
             WHERE a.source = 'task_results' AND k.source = 'task_results' AND a.exp = k.exp
             AND (COALESCE(a.round,-1) <> COALESCE(k.round,-1) OR COALESCE(a.arm,'') <> COALESCE(k.arm,''))""")[0][0]
print(f"  info  task_results merged across different round/arm in the same exp: {cross} (should be ~0)")

check("repair-decisions r1-r5 verified (HANDOFF 60)",
      q("SELECT SUM(verified) FROM attempts_unique WHERE exp='kaggle_e4b_repair_decisions_seed39_r1_r5_v2'")[0][0], 60)
xexp = q("""SELECT COUNT(*) FROM attempts a JOIN attempts k ON a.dup_of = k.id
            WHERE a.exp <> k.exp AND COALESCE(a.arm,'') <> COALESCE(k.arm,'')""")[0][0]
check("cross-experiment merges between different arms", xexp, 0)
check("seed39 round-1 run: unique attempts", q("SELECT COUNT(*) FROM attempts_unique WHERE exp='kaggle_e4b_evidence_seed39'")[0][0], 39)
check("seed39 round-1 verified (HANDOFF 13/39)",
      q("SELECT SUM(verified) FROM attempts_unique WHERE exp='kaggle_e4b_evidence_seed39'")[0][0], 13)

print("2a. Colab Drive copy (Outputs/drive_ab_runs), if present")
drive = ROOT / "Outputs" / "drive_ab_runs"
for pj in sorted(drive.glob("*/progress.json")) if drive.is_dir() else []:
    exp = f"drive_{pj.parent.name}"
    P = json.loads(pj.read_text(encoding="utf-8-sig")).get("passes", [])
    ok = tot = 0
    for p in P:
        # attempts from this tag's task_results for (arm, round); a pass may be incomplete on Drive -> compare only
        # passes whose task_results are fully present
        rows = q("""SELECT COUNT(*), SUM(resolved) FROM attempts WHERE exp = ? AND source = 'task_results'
                    AND arm = ? AND round = ?""", exp, p["arm"], p["round"])[0]
        if rows[0] == p["n"]:
            tot += 1
            ok += (rows[1] or 0) == p["solved"]
    traced = q("""SELECT COUNT(*), SUM(trace_path IS NOT NULL) FROM attempts WHERE exp = ? AND source = 'task_results'""", exp)[0]
    check(f"{exp}: pass totals == progress.json ({tot} complete passes of {len(P)})", ok, tot)
    print(f"  info  {exp}: {traced[1]}/{traced[0]} task_results attempts have a trace")

print("2b. agent bundles")
# pack 1 = colab_fasteval/arms/C_pack1, sha12 84f904c63afd (recorded in every A/B prereg)
check("pack 1 bundle sha12", q("SELECT sha12 FROM bundles WHERE path='colab_fasteval/arms/C_pack1'"), [("84f904c63afd",)])
check("batch-6 L_loc sha12", q("SELECT sha12 FROM bundles WHERE path='colab_fasteval/arms6/L_loc'"), [("a60585682580",)])
reg = q("SELECT COUNT(DISTINCT exp || role) FROM registered_files")[0][0]
matched = q("SELECT COUNT(DISTINCT exp || role) FROM exp_bundles")[0][0]
print(f"  info  registered experiment roles matched to an on-disk bundle by file hash: {matched}/{reg}")

print("2c. deep layers")
# trace-decoded tool calls vs swegemma's own tool_calls count (swegemma excludes get_status, which is free)
# swegemma's tool_calls excludes get_status (free) and submit_patch (established from the diff distribution)
agree = q("""SELECT COUNT(*), SUM(f.n_calls - f.n_get_status - f.n_submit = a.tool_calls)
             FROM attempt_features f JOIN attempts a ON a.id = f.attempt_id
             WHERE f.basis = 'trace' AND a.tool_calls IS NOT NULL AND a.source <> 'trace_only'""")[0]
print(f"  info  trace calls (excl. get_status, submit_patch) == swegemma tool_calls: {agree[1]}/{agree[0]}")
check("trace tool-call counts agree with swegemma (>= 95%)", (agree[1] or 0) >= 0.95 * agree[0], True)
ov = q("""SELECT COUNT(*), SUM(l.lane_overflows_in_window > 0) FROM attempts_unique a
          JOIN attempt_server_load l ON l.attempt_id = a.id WHERE a.error_class = 'overflow'""")[0]
print(f"  info  overflow attempts with a vLLM overflow on their lane in their window: {ov[1]}/{ov[0]}")
check("overflow attempts confirmed by vLLM log (>= 90%)", (ov[1] or 0) >= 0.9 * (ov[0] or 1), True)
# limit = the experiment's own served context (vLLM log) minus the 5000-token output reserve
over = q("""SELECT COUNT(*) FROM traces t JOIN attempts a ON a.id = t.attempt_id
            JOIN (SELECT exp, MAX(max_model_len) AS ml FROM vllm_servers GROUP BY exp) s ON s.exp = a.exp
            WHERE t.max_prompt_tokens > s.ml - 5000""")[0][0]
check("no trace prompt above its server's context minus 5000", over, 0)
print("  info  prompts > 27768 by exp (larger-context runs):",
      q("""SELECT a.exp, MAX(t.max_prompt_tokens) FROM traces t JOIN attempts a ON a.id = t.attempt_id
           WHERE t.max_prompt_tokens > 27768 GROUP BY a.exp"""))

bad = q("""SELECT COUNT(*) FROM tool_calls WHERE obs_status = 'error'
           AND (obs_content LIKE '{"status": "success"%' OR obs_content LIKE '{"status": "ok"%')""")[0][0]
check("no successful tool result counted as an error", bad, 0)
print("  info  normalised tool status:", q("SELECT obs_status, COUNT(*) FROM tool_calls GROUP BY 1 ORDER BY 2 DESC"))

print("3. coverage")
for row in q("""SELECT source, COUNT(*), SUM(dup_of IS NULL), SUM(trace_path IS NOT NULL), SUM(test_output_path IS NOT NULL),
                SUM(verified IS NOT NULL), SUM(arm IS NULL) FROM attempts GROUP BY source"""):
    print(f"  {row[0]:13s} rows {row[1]:6d} unique {row[2]:6d} trace {row[3]:6d} test_out {row[4]:6d} "
          f"verified-known {row[5]:6d} arm-unknown {row[6]:6d}")
print("  models:", q("SELECT model, model_basis, COUNT(*) FROM attempts_unique GROUP BY 1,2 ORDER BY 3 DESC"))
print("FAILED CHECKS:", fails)
sys.exit(1 if fails else 0)
