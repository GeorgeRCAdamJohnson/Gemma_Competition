"""
Batch runner for rapid prompt/config iteration against the local llama.cpp Gemma judge.
Runs each PROMPT VARIANT across a fixed set of tasks, prints resolved N/total per variant.

Usage:
  python batch.py --variant baseline --tasks rich_small
  python batch.py --variant anti_noop
  python batch.py --all           # run every variant on the task set
"""
import argparse, json, time, sys
import run_local as R

# ---- task sets (small-patch rich tasks: fast, the slice our method targets) ----
TASK_SETS = {
    # chosen: small single-file rich fixes (patch < ~600 chars) so a weak 12b has a chance
    "rich_small": ["rich_4077", "rich_3278", "rich_2943", "rich_3470", "rich_3471"],
    "rich_one": ["rich_4077"],
}

# ---- prompt variants (ONE idea each; keep the winner) ----
BASE_TOOLS_LINE = ("Tools: search_code(query), read_file(path,start_line,end_line), "
    "edit_file(path,old_string,new_string), run_command(command), submit_patch(). "
    "ONE tool call per turn. Do NOT modify test files. old_string must be an EXACT snippet copied "
    "verbatim from read_file content; new_string is the corrected code and must DIFFER from old_string. "
    "Keep reasoning to 1-2 sentences then emit a tool call.")

VARIANTS = {
# the current/working prompt (control)
"baseline": """You are an expert autonomous software engineer. HARD budget ~15 tool calls. BE DECISIVE AND FAST.
LOCATE then EDIT. Spend AT MOST 3-4 tool calls locating, then IMMEDIATELY call edit_file. Do NOT write reproduction scripts.
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings.
Workflow: 1) search_code + read_file to locate (<=3-4 calls). 2) edit_file minimal fix. 3) submit_patch ONCE then STOP.
""" + BASE_TOOLS_LINE,

# V-A: attack the NO-OP edit failure directly
"anti_noop": """You are an expert autonomous software engineer. HARD budget ~15 tool calls. BE DECISIVE.
LOCATE then EDIT. <=3-4 locate calls, then edit_file. Do NOT write reproduction scripts.

YOUR EDIT MUST CHANGE PROGRAM LOGIC, NOT JUST REFORMAT. A fix where new_string merely re-indents or
re-types the same code is WRONG and wastes a turn. The new_string must contain DIFFERENT behavior:
a new condition, a changed return, a new validator, a forwarded attribute, a corrected operator.
Before you call edit_file, state in one sentence WHAT BEHAVIOR CHANGES.

Most bugs are a DEVIATION from a pattern the code already follows elsewhere. Find the working sibling
(a similar function/field that behaves correctly) and make the broken one behave the SAME way.
Workflow: 1) locate (<=3-4). 2) edit_file with a REAL logic change. 3) submit_patch ONCE then STOP.
""" + BASE_TOOLS_LINE,

# V-B: explicit sibling-conformance with "show me the sibling" step
"sibling": """You are an expert autonomous software engineer. HARD budget ~15 tool calls.
Method (follow exactly):
1) Find the buggy symbol with search_code, read it with read_file.
2) Find a WORKING SIBLING: another function/field/class in the SAME file that already does the correct
   thing the buggy one should do. read_file it. (e.g. if `event` lacks validation, the `id` field that
   HAS validation is the sibling.)
3) edit_file so the buggy code CONFORMS to the sibling's pattern — copy the sibling's mechanism
   (same decorator, same guard, same forwarding) onto the broken code. The change must alter behavior.
4) submit_patch ONCE then STOP.
Do NOT write reproduction scripts. Keep reasoning to 1-2 sentences per turn.
""" + BASE_TOOLS_LINE,

# V-C: BOUNDED self-check — observe the defect once, then fix (budget-disciplined detection)
# DROPPED from the default lineup (user call): invites the repro rabbit-hole, doesn't close the
# gap to a correct fix. Kept here for reference only; not run by --all.
"selfcheck": """You are an expert autonomous software engineer. HARD budget ~15 tool calls.
Method:
1) Locate the buggy symbol (search_code + read_file, <=3 calls).
2) OBSERVE THE DEFECT: run EXACTLY ONE quick behavior check with run_command using a single
   `python3 -c "..."` one-liner that prints what the buggy code currently does (e.g. construct the
   object and print the wrong result). This shows you the ACTUAL wrong behavior. You get ONE such
   check only — do NOT write .py files, do NOT run pytest, do NOT loop. One command, read the output.
3) From what you OBSERVED, make the minimal edit_file that changes the behavior to correct.
4) submit_patch ONCE then STOP.
Keep reasoning to 1-2 sentences per turn. The edit must change program logic, not just reformat.
""" + BASE_TOOLS_LINE,

# V-D: LOCALIZE-TO-DEFINITION — mirrors v4's system.md. The failing test names a class/symbol;
# find the file that DEFINES it and edit the method THERE, not where it is referenced.
"localize": """You are an expert autonomous software engineer. HARD budget ~15 tool calls. Be decisive.

LOCALIZE TO THE DEFINITION, NOT THE REFERENCE. The problem/test names a class, function, or attribute.
Your fix belongs in the file that DEFINES that class or function, not a file that merely uses it. If the
test constructs an object of some class and calls a method on it, the fix is a change to THAT class in
its defining file. Trace the named symbol to its definition FIRST, then edit there.

Method:
1) From the problem/test, identify the named class/symbol. Use search_code to find where it is DEFINED
   (e.g. `class FileProxy`), read that file. <=3-4 locate calls. Confirm you are in the defining module,
   not a caller.
2) Make the buggy code conform to its correct sibling (a parallel method/field on the same class that
   already behaves correctly). If a forwarding/validation method is MISSING, add it, matching the sibling.
3) edit_file with a REAL logic change (old_string verbatim, new_string differs). 
4) submit_patch ONCE then STOP. Do NOT write reproduction scripts.
Keep reasoning to 1-2 sentences per turn.
""" + BASE_TOOLS_LINE,
}

# variants run by --all (selfcheck intentionally excluded per user decision)
ALL_VARIANTS = ["baseline", "sibling", "localize"]


def run_one(task, model, max_tool_calls, prompt):
    try:
        R.set_repo(task["repo"].split("/")[-1])
        diff, calls, dur, submitted = R.run_agent(task, model, max_tool_calls, system_prompt=prompt)
        if not diff.strip():
            return {"resolved": False, "reason": "no_patch", "calls": calls, "dur": round(dur), "chars": 0}
        passed, log = R.verify(task, diff)
        return {"resolved": passed, "reason": "pass" if passed else "test_fail",
                "calls": calls, "dur": round(dur), "chars": len(diff)}
    except Exception as e:
        return {"resolved": False, "reason": f"err:{type(e).__name__}", "calls": 0, "dur": 0, "chars": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tasks", default="rich_small")
    ap.add_argument("--model", default="local")
    ap.add_argument("--max-tool-calls", type=int, default=15)
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()
    R.TEMPERATURE = args.temp
    R.QUIET = True

    task_ids = TASK_SETS[args.tasks]
    tasks = [R.load_task(t) for t in task_ids]
    variants = ALL_VARIANTS if args.all else [args.variant]

    import io
    outf = io.open("_batch_summary.txt", "w", encoding="utf-8")
    def log(s):
        outf.write(s + "\n"); outf.flush()
    log(f"temp={args.temp} max_tool_calls={args.max_tool_calls} tasks={task_ids}")
    results = {}
    for v in variants:
        prompt = VARIANTS[v]
        log(f"\n===== VARIANT: {v} =====")
        resolved = 0; tot_dur = 0
        for t in tasks:
            r = run_one(t, args.model, args.max_tool_calls, prompt)
            flag = "RESOLVED" if r["resolved"] else r["reason"]
            line = f"  {t['instance_id']:12s} {flag:12s} calls={r['calls']:2d} dur={r['dur']:3d}s chars={r['chars']}"
            log(line)
            resolved += int(r["resolved"]); tot_dur += r["dur"]
        mean_dur = tot_dur / max(len(tasks), 1)
        results[v] = (resolved, mean_dur)
        log(f"  --> {v}: RESOLVED {resolved}/{len(tasks)}  mean {mean_dur:.0f}s/task")
    log("\n===== SUMMARY (resolves, then mean time) =====")
    for v, (n, md) in sorted(results.items(), key=lambda kv: (-kv[1][0], kv[1][1])):
        log(f"  {v:12s} {n}/{len(tasks)}  mean {md:.0f}s/task")
    outf.close()


if __name__ == "__main__":
    main()
