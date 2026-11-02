"""DEEP forensic decomposer for rich_4077 across all official-12B reps.
Reconstructs every tool call: intent -> call -> result, then classifies WHERE the budget went
and WHY each edit failed. No surface counting."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
ARM = "off12"
TASK = "rich_4077"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

GOLD = None


def load_gold():
    """gold patch for rich_4077 from comp_files/tasks.jsonl"""
    p = RIG.parent.parent / "comp_files" / "tasks.jsonl"
    if not p.exists():
        return None
    for line in open(p, encoding="utf-8"):
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("instance_id") == TASK:
            return d.get("patch") or d.get("gold_patch")
    return None


def get_path(args):
    for k in ("path", "filepath", "file_path", "filename"):
        if args.get(k):
            return str(args[k])
    return "?keys=" + ",".join(sorted(args.keys()))


def classify_args(fn, args):
    if fn == "run_command":
        return (args.get("command") or "")[:110]
    if fn == "read_file":
        return f"{get_path(args)} L{args.get('start_line')}-{args.get('end_line')}"
    if fn == "edit_file":
        o = (args.get("old_string") or "")
        n = (args.get("new_string") or "")
        return f"{get_path(args)} | old={len(o)}b new={len(n)}b same={o == n}"
    if fn == "search_code":
        return str(args.get("query"))[:80]
    if fn == "submit_patch":
        return f"patch={len(json.dumps(args))}b"
    return str(args)[:80]


def obs_status(obs):
    """(status, short_message) from a tool observation"""
    if not obs:
        return ("none", "")
    c = obs.get("content") if isinstance(obs, dict) else obs
    if isinstance(c, str):
        try:
            j = json.loads(c)
            st = str(j.get("status", "?"))
            msg = j.get("stdout") or j.get("message") or j.get("stderr") or j.get("error") or ""
            return (st, str(msg)[:120].replace("\n", " "))
        except Exception:
            return ("raw", str(c)[:120].replace("\n", " "))
    return ("?", str(c)[:120])


def analyze(path):
    try:
        raw = ANSI.sub("", path.read_text(encoding="utf-8"))
        j = json.loads(raw)
    except Exception as e:
        return None
    steps = j.get("steps", [])
    timeline = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        msg = (s.get("message") or "").strip()
        for tc in (s.get("tool_calls") or []):
            fn = tc.get("function_name") or ""
            args = tc.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            st, note = obs_status(s.get("observation"))
            timeline.append({
                "step": s.get("step_id"),
                "intent": msg.replace("\n", " ")[:150],
                "fn": fn,
                "detail": classify_args(fn, args),
                "status": st,
                "note": note,
                "args": args,
                "elapsed": (tc.get("extra") or {}).get("elapsed_s"),
            })
    return {"timeline": timeline, "metrics": j.get("final_metrics", {})}


def summarize(name, an):
    tl = an["timeline"]
    counts = Counter(t["fn"] for t in tl)
    edits = [t for t in tl if t["fn"] == "edit_file"]
    noop = [t for t in edits if "same=True" in t["detail"]]
    edit_fail = [t for t in edits if t["status"] not in ("ok",)]
    reads = [t for t in tl if t["fn"] == "read_file"]
    cmds = [t for t in tl if t["fn"] == "run_command"]
    verify = [t for t in cmds if re.search(r"pytest|python -m pytest|unittest", t["detail"])]
    grepish = [t for t in cmds if re.search(r"grep|rg |sed -n|cat ", t["detail"])]
    files_edited = Counter()
    for t in edits:
        files_edited[get_path(t["args"])] += 1
    print(f"\n{'='*100}\n{name}  steps={len(tl)}  tokens={an['metrics'].get('total_tokens')}")
    print(f"  calls: {dict(counts)}")
    print(f"  explore: read={len(reads)} grepish={len(grepish)} | verify(pytest)={len(verify)}")
    print(f"  edits={len(edits)}  NO-OP(old==new)={len(noop)}  edit-status!=ok={len(edit_fail)}")
    print(f"  files edited: {dict(files_edited)}")
    return {"timeline": tl, "edits": edits, "noop": noop, "edit_fail": edit_fail,
            "reads": reads, "verify": verify, "grepish": grepish, "counts": dict(counts)}


def dump_timeline(tl, limit=None):
    for i, t in enumerate(tl, 1):
        if limit and i > limit:
            break
        flag = ""
        if t["fn"] == "edit_file" and "same=True" in t["detail"]:
            flag = "  <<< NO-OP"
        elif t["fn"] == "edit_file" and t["status"] != "ok":
            flag = f"  <<< EDIT-{t['status'].upper()}"
        print(f"  {i:2d}. [{t['fn']}] {t['detail']}{flag}")
        print(f"      -> {t['status']}: {t['note']}")


def main():
    reps = sorted((RIG / "m1_batch_multi" / ARM).glob("r*"),
                  key=lambda p: int(p.name[1:]))
    results = {}
    for d in reps:
        tr = d / "traces" / f"trace_{TASK}.json"
        res = d / "task_results.jsonl"
        if not tr.exists():
            continue
        resolved = None
        if res.exists():
            for line in open(res, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    if r.get("instance_id") == TASK:
                        resolved = bool(r.get("resolved"))
        an = analyze(tr)
        if not an:
            continue
        s = summarize(f"{d.name} resolved={resolved}", an)
        results[d.name] = {"resolved": resolved, **s}

    # aggregate
    print(f"\n{'='*100}\nAGGREGATE ({len(results)} reps)")
    ok = [v for v in results.values() if v["resolved"]]
    bad = [v for v in results.values() if not v["resolved"]]
    for label, grp in (("RESOLVED", ok), ("FAILED", bad)):
        if not grp:
            continue
        def avg(key):
            vals = [len(v[key]) if isinstance(v[key], (list, dict)) else v[key] for v in grp]
            return sum(vals) / len(vals)
        print(f"\n{label} n={len(grp)}")
        cc = Counter()
        for v in grp:
            for k, n in v["counts"].items():
                cc[k] += n
        tot = sum(cc.values())
        print(f"  call mix ({tot} calls): " + ", ".join(f"{k}={v}({100*v/tot:.0f}%)" for k, v in cc.most_common()))
        print(f"  reads={avg('reads'):.1f} grep={avg('grepish'):.1f} verify={avg('verify'):.1f} "
              f"edits={avg('edits'):.1f} noop={avg('noop'):.1f} editfail={avg('edit_fail'):.1f}")

    # detailed timeline of one success + two failures
    if ok:
        name = [k for k, v in results.items() if v["resolved"]][0]
        print(f"\n{'='*100}\nTIMELINE: {name} (SUCCESS)")
        dump_timeline(results[name]["timeline"])
    for name in [k for k, v in results.items() if not v["resolved"]][:2]:
        print(f"\n{'='*100}\nTIMELINE: {name} (FAIL)")
        dump_timeline(results[name]["timeline"])

    # intent-vs-reality: what did the model SAY it was doing on failed edits?
    print(f"\n{'='*100}\nFAILED EDIT CONTEXTS (all reps)")
    seen = 0
    for name, v in results.items():
        for t in v["edit_fail"]:
            print(f"  [{name}] {t['detail']}")
            print(f"      intent: {t['intent'][:130]}")
            print(f"      result: {t['status']}: {t['note'][:110]}")
            seen += 1
            if seen > 18:
                break
        if seen > 18:
            break


if __name__ == "__main__":
    main()
