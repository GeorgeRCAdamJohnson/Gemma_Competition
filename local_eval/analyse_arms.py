"""Analyse the e4b_arms_1024 sweep against the pre-registration.

PRIMARY (pre-registered): per-run edit_file failure rate, arm vs A3, run-level
permutation test, two-sided, alpha 0.05, 20,000 shuffles.

Run-level, not per-call: errors cluster inside looping runs, which is the mistake
that produced the retracted D-arm p-values.

GUARDS: corruption rate must not rise; landed edits must not decline; fresh-anchor
success must not decline. Resolve rate is reported but is NOT the decision metric,
and every resolve number is PROVISIONAL until rescore_pinned.py re-scores it
(gate_run's shared-env verifier has silent false positives).

Usage:
    python analyse_arms.py                 # all arms
    python analyse_arms.py --arm D2        # one arm vs A3
"""
import argparse
import collections
import glob
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
SWEEP = "e4b_arms_1024"
ARMS = ["A3", "D2", "A19"]
TASKS = ["rich_2725", "rich_2943"]


def parse_args(raw):
    """args_full/args_head are JSON-encoded strings; return the dict or None."""
    if not raw:
        return None
    try:
        a = json.loads(raw)
    except Exception:
        return None
    return a if isinstance(a, dict) else None


def is_err(d):
    st = str(d.get("status") or "").lower()
    err = d.get("error")
    return (st == "error") or (err not in (None, "", "None"))


def err_class(d):
    e = str(d.get("error") or "")
    if "mandatory input parameters" in e:
        return "corruption"
    if "old_string" in e or "not found" in e or "no match" in e.lower():
        return "anchor"
    if e.strip() == "":
        return "empty"
    if "timeout" in e.lower() or "timed out" in e.lower():
        return "timeout"
    return "other"


def load_run(path):
    """One (arm, rep, task) run -> metrics."""
    r = dict(edit_calls=0, edit_err=0, corruption=0, anchor=0, empty=0, other_err=0,
             landed=0, fresh_ok=0, fresh_n=0, retry=0, retry_ok=0, retry_n=0,
             turns=0, secs=0.0, chat_err=0, comp_err=0, nudge=0, submitted=0,
             infra_death=False, first_call_err=False)
    seen = set()
    first_call_seen = False
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        k = d.get("kind")
        if k == "turn":
            r["turns"] += 1
            r["secs"] += d.get("secs") or 0
        elif k == "chat_error":
            r["chat_err"] += 1
            call = d.get("call")
            if call in (0, 1) and (d.get("error") in (None, "", "None")):
                r["infra_death"] = True
        elif k == "compaction_error":
            r["comp_err"] += 1
        elif k == "nudge":
            r["nudge"] += 1
        elif k == "tool":
            t = d.get("tool")
            if not first_call_seen:
                first_call_seen = True
                if is_err(d):
                    r["first_call_err"] = True
            if t == "edit_file":
                r["edit_calls"] += 1
                a = parse_args(d.get("args_full")) or parse_args(d.get("args_head")) or {}
                old = a.get("old_string")
                if is_err(d):
                    r["edit_err"] += 1
                    c = err_class(d)
                    r[c if c in ("corruption", "anchor", "empty") else "other_err"] += 1
                    if old is not None:
                        if old in seen:
                            r["retry"] += 1
                            r["retry_n"] += 1
                        else:
                            r["fresh_n"] += 1
                else:
                    r["landed"] += 1
                    if old is not None:
                        if old in seen:
                            r["retry_n"] += 1
                            r["retry_ok"] += 1
                        else:
                            r["fresh_n"] += 1
                            r["fresh_ok"] += 1
                            seen.add(old)
            elif t == "submit_patch":
                r["submitted"] += 1
    return r


def collect():
    out = collections.defaultdict(list)
    for arm in ARMS:
        for task in TASKS:
            pat = os.path.join(RUNS, "%s_%s_r*_%s.trace.jsonl" % (SWEEP, arm, task))
            for p in sorted(glob.glob(pat)):
                base = os.path.basename(p)
                # <sweep>_<ARM>_r<N>_<task>.trace.jsonl
                try:
                    rep = int(base.split("_r")[1].split("_")[0])
                except Exception:
                    continue
                m = load_run(p)
                m["arm"] = arm
                m["rep"] = rep
                m["task"] = task
                out[arm].append(m)
    return out


def perm_test(a, b, n_shuf=20000, seed=12345):
    """Two-sided run-level permutation test on the difference of means."""
    if len(a) < 2 or len(b) < 2:
        return None, None
    rng = random.Random(seed)
    obs = statistics.mean(b) - statistics.mean(a)
    pool = list(a) + list(b)
    na = len(a)
    hits = 0
    for _ in range(n_shuf):
        rng.shuffle(pool)
        d = statistics.mean(pool[na:]) - statistics.mean(pool[:na])
        if abs(d) >= abs(obs) - 1e-12:
            hits += 1
    return obs, (hits + 1) / (n_shuf + 1)


def rate(num, den):
    return (num / den) if den else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default=None)
    ap.add_argument("--min-reps", type=int, default=1)
    args = ap.parse_args()

    data = collect()
    arms = [args.arm] if args.arm else ARMS
    ctrl = data.get("A3", [])

    print("=" * 78)
    print("SWEEP %s   (pre-registered primary: per-run edit_file failure rate)" % SWEEP)
    print("=" * 78)

    if not ctrl:
        print("NO A3 CONTROL RUNS FOUND. Nothing can be compared.")
        return 1

    infra = [r for r in ctrl if r["infra_death"]]
    print("\nA3 control: %d runs (%d infra deaths excluded from the primary)"
          % (len(ctrl), len(infra)))
    ctrl_valid = [r for r in ctrl if not r["infra_death"]]

    def block(name, rows):
        if not rows:
            print("  %-6s no runs" % name)
            return
        ef = rate(sum(r["edit_err"] for r in rows), sum(r["edit_calls"] for r in rows))
        corr = rate(sum(r["corruption"] for r in rows), sum(r["edit_calls"] for r in rows))
        anch = rate(sum(r["anchor"] for r in rows), sum(r["edit_calls"] for r in rows))
        fresh = rate(sum(r["fresh_ok"] for r in rows), sum(r["fresh_n"] for r in rows))
        print("  %-6s n=%3d | edit_file fail %5.1f%% | corruption %5.2f%% | anchor %5.1f%% | "
              "landed %5.2f | fresh-anchor ok %5.1f%% | wall %6.0fs | infra %d"
              % (name, len(rows), 100 * (ef or 0), 100 * (corr or 0), 100 * (anch or 0),
                 statistics.mean(r["landed"] for r in rows), 100 * (fresh or 0),
                 statistics.mean(r["secs"] for r in rows),
                 sum(1 for r in rows if r["infra_death"])))

    print("\n--- descriptive ---")
    block("A3", ctrl_valid)
    for a in arms:
        if a == "A3":
            continue
        rows = [r for r in data.get(a, []) if not r["infra_death"]]
        block(a, rows)

    print("\n--- PRIMARY: per-run edit_file failure rate, run-level permutation vs A3 ---")
    ctrl_vals = [rate(r["edit_err"], r["edit_calls"]) for r in ctrl_valid]
    ctrl_vals = [v for v in ctrl_vals if v is not None]
    for a in arms:
        if a == "A3":
            continue
        rows = [r for r in data.get(a, []) if not r["infra_death"]]
        vals = [rate(r["edit_err"], r["edit_calls"]) for r in rows]
        vals = [v for v in vals if v is not None]
        if len(vals) < 2 or len(ctrl_vals) < 2:
            print("  %-6s vs A3: too few runs (arm %d, A3 %d)" % (a, len(vals), len(ctrl_vals)))
            continue
        obs, p = perm_test(ctrl_vals, vals)
        direction = "LOWER (better)" if obs < 0 else ("HIGHER (worse)" if obs > 0 else "same")
        print("  %-6s vs A3: A3 %.3f -> %s %.3f   delta %+.3f   permutation p = %.4f   %s"
              % (a, statistics.mean(ctrl_vals), a, statistics.mean(vals), obs, p, direction))
        if p is not None and p < 0.05:
            print("         SIGNIFICANT at alpha 0.05 -- check the guards below before adopting")

    print("\n--- GUARDS (all must hold) ---")
    for a in arms:
        if a == "A3":
            continue
        rows = [r for r in data.get(a, []) if not r["infra_death"]]
        if not rows:
            continue
        c_corr = rate(sum(r["corruption"] for r in ctrl_valid), sum(r["edit_calls"] for r in ctrl_valid)) or 0
        a_corr = rate(sum(r["corruption"] for r in rows), sum(r["edit_calls"] for r in rows)) or 0
        c_land = statistics.mean(r["landed"] for r in ctrl_valid)
        a_land = statistics.mean(r["landed"] for r in rows)
        c_fresh = rate(sum(r["fresh_ok"] for r in ctrl_valid), sum(r["fresh_n"] for r in ctrl_valid)) or 0
        a_fresh = rate(sum(r["fresh_ok"] for r in rows), sum(r["fresh_n"] for r in rows)) or 0
        g1 = "OK" if a_corr <= c_corr + 1e-9 else "FAIL"
        g2 = "OK" if a_land >= c_land - 1e-9 else "FAIL"
        g3 = "OK" if a_fresh >= c_fresh - 1e-9 else "FAIL"
        print("  %-6s corruption %+.4f [%s] | landed %+.2f [%s] | fresh-anchor %+.3f [%s]"
              % (a, a_corr - c_corr, g1, a_land - c_land, g2, a_fresh - c_fresh, g3))

    print("\n--- resolve rate (PROVISIONAL: gate_run has silent false positives; "
          "re-score with rescore_pinned.py) ---")
    for a in arms:
        rows = data.get(a, [])
        if not rows:
            continue
        print("  %-6s runs=%d  (resolve numbers come from results.jsonl, not traces)"
              % (a, len(rows)))

    print("\n--- per-task breakdown ---")
    for a in arms:
        for t in TASKS:
            rows = [r for r in data.get(a, []) if r["task"] == t and not r["infra_death"]]
            if not rows:
                continue
            ef = rate(sum(r["edit_err"] for r in rows), sum(r["edit_calls"] for r in rows))
            print("  %-6s %-12s n=%2d  edit_file fail %5.1f%%  landed %5.2f  wall %6.0fs"
                  % (a, t, len(rows), 100 * (ef or 0),
                     statistics.mean(r["landed"] for r in rows),
                     statistics.mean(r["secs"] for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
