"""Scan Kaggle ATIF traces (submit_*/**/results/traces/trace_*.json) for null / loop / serialization signals.  CPU only.
python atif_scan.py            # per-trace table + per-version summary
python atif_scan.py --only v6w # filter by path substring
"""
import argparse, collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def max_line_rep(s):
    lines = [l.strip() for l in (s or "").splitlines() if l.strip()]
    if not lines:
        return 0
    return collections.Counter(lines).most_common(1)[0][1]


def label(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        # submit_v6z_on_v6w/armA/out/... -> v6z_on_v6w/armA ; submit_v6w/out_v6w/... -> v6w
        if len(rel) > 2 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return rel[0] + ("/" + rel[1] if rel[1] != "results" else "")


def scan(p):
    d = json.load(open(p, encoding="utf-8"))
    steps = d.get("steps", [])
    agent = [s for s in steps if s.get("source") == "agent"]
    tools = collections.Counter()
    bad_keys = 0
    first_edit = None
    submit = False
    submit_ok = None
    max_rep = 0
    big = 0
    max_msg = 0
    nudge_like = 0
    for i, s in enumerate(agent):
        msg = s.get("message") or ""
        max_msg = max(max_msg, len(msg))
        if len(msg) > 6000:
            big += 1
        max_rep = max(max_rep, max_line_rep(msg) if len(msg) > 800 else 0)
        for tc in s.get("tool_calls") or []:
            n = tc.get("function_name")
            tools[n] += 1
            args = tc.get("arguments") or {}
            if isinstance(args, dict) and any('"' in k for k in args):
                bad_keys += 1
            if n == "edit_file" and first_edit is None:
                first_edit = i + 1
            if n == "submit_patch":
                submit = True
                obs = (s.get("observation") or {}).get("content") or ""
                submit_ok = ("ok" in obs[:80].lower()) if obs else None
    final = next((s for s in reversed(steps) if (s.get("extra") or {}).get("event_type") == "final"), None)
    fm = d.get("final_metrics") or {}
    return {
        "label": label(p), "task": p.stem.replace("trace_", ""), "steps": len(agent), "tools": dict(tools),
        "edits": tools.get("edit_file", 0), "first_edit": first_edit, "submit": submit,
        "final": bool(final), "final_head": (final.get("message") or "")[:100].replace("\n", " ") if final else "",
        "bad_keys": bad_keys, "max_rep": max_rep, "big_msgs": big, "max_msg": max_msg,
        "ctok": fm.get("total_completion_tokens"), "elapsed": round(((final or {}).get("extra") or {}).get("elapsed_s", 0) or 0),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--rows", action="store_true")
    a = ap.parse_args()
    rows = []
    for p in sorted(ROOT.glob("**/results/traces/trace_*.json")):
        if "local_eval" in p.parts or (a.only and a.only not in str(p)):
            continue
        try:
            rows.append(scan(p))
        except Exception as e:
            print("skip", p, e)
    if a.rows:
        print(f"{'version':26}{'task':11}{'steps':>6}{'edits':>6}{'1stEd':>6}{'subm':>5}{'final':>6}{'badK':>5}{'rep':>4}{'big':>4}{'maxmsg':>7}{'ctok':>7}{'sec':>5}")
        for r in rows:
            print(f"{r['label'][:25]:26}{r['task']:11}{r['steps']:>6}{r['edits']:>6}{str(r['first_edit']):>6}{str(r['submit'])[:1]:>5}{str(r['final'])[:1]:>6}"
                  f"{r['bad_keys']:>5}{r['max_rep']:>4}{r['big_msgs']:>4}{r['max_msg']:>7}{str(r['ctok']):>7}{r['elapsed']:>5}")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["label"]].append(r)
    print(f"\n{'version':26}{'n':>3}{'submit':>7}{'edit>0':>7}{'no-edit':>8}{'badKeyTr':>9}{'loop(rep>=5)':>13}{'big>6k':>7}")
    for k, v in by.items():
        n = len(v)
        print(f"{k[:25]:26}{n:>3}{sum(r['submit'] for r in v):>7}{sum(r['edits'] > 0 for r in v):>7}{sum(r['edits'] == 0 for r in v):>8}"
              f"{sum(r['bad_keys'] > 0 for r in v):>9}{sum(r['max_rep'] >= 5 for r in v):>13}{sum(r['big_msgs'] > 0 for r in v):>7}")
    n = len(rows)
    print(f"\nALL {n} traces: submit {sum(r['submit'] for r in rows)} | edited {sum(r['edits'] > 0 for r in rows)} | never edited {sum(r['edits'] == 0 for r in rows)} | "
          f"bad-key traces {sum(r['bad_keys'] > 0 for r in rows)} | loop(rep>=5) {sum(r['max_rep'] >= 5 for r in rows)} | msgs>6000 chars {sum(r['big_msgs'] > 0 for r in rows)}")


if __name__ == "__main__":
    main()
