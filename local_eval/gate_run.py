"""Gate driver for the local llama-server harness (run_local.py).

Runs run_agent + verify over a task list with NO wall-clock cap by default, and records one result row
per task plus a per-turn trace, so a run can be audited afterwards.

  python gate_run.py --tag think_on_t02 --tasks-file gate12.txt --thinking on --temp 0.2
  python gate_run.py --tag think_off    --tasks rich_3944,rich_3296 --thinking off

Outputs (relative to this folder):
  runs\\<tag>.results.jsonl   one row per task (resolved, end_reason, calls, edit stats, ...)
  runs\\<tag>.trace.jsonl     one row per model turn / tool call / task end
"""
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path

import run_local as R

HERE = Path(__file__).resolve().parent


def oracle_hint(task, level):
    """Diagnostic only: leaks the gold location so we can measure the agent loop with localization solved."""
    gold = task["patch"]
    files = re.findall(r"^\+\+\+ b/(\S+)", gold, re.M)
    text = "\n\n[Oracle hint for a diagnostic run] The fix belongs in: " + ", ".join(files) + "."
    if level == "scope":
        scopes = [s.strip() for s in re.findall(r"^@@ .*?@@\s*(.+)$", gold, re.M) if s.strip()]
        if scopes:
            text += " Enclosing code: " + "; ".join(dict.fromkeys(scopes)) + "."
    return text


def read_tasks(args):
    ids = []
    if args.tasks:
        ids += [t for t in re.split(r"[,\s]+", args.tasks) if t]
    if args.tasks_file:
        ids += [t for t in re.split(r"[,\s]+", Path(args.tasks_file).read_text(encoding="utf-8")) if t]
    return ids


def make_isolated_worktree(tag):
    """Create a detached git worktree for this run so concurrent runs cannot corrupt
    each other's working tree. Returns the path, or None if it could not be made.

    A worktree shares the object store (no disk cost) but has its own working tree,
    HEAD and index, so `git reset --hard` inside it cannot touch another run.
    """
    src = HERE / "repos" / "rich"
    if not (src / ".git").exists():
        return None
    wt = HERE / "repos" / f"_wt_{tag}"
    if wt.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                       cwd=src, capture_output=True)
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)
    r = subprocess.run(["git", "worktree", "add", "--detach", str(wt), "HEAD"],
                       cwd=src, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not wt.exists():
        print(f"[gate_run] worktree add failed: {(r.stderr or '')[:200]}")
        return None
    return wt


def remove_isolated_worktree(tag):
    src = HERE / "repos" / "rich"
    wt = HERE / "repos" / f"_wt_{tag}"
    if not wt.exists():
        return
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                   cwd=src, capture_output=True)
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=src, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--tasks", default=None, help="comma-separated task ids")
    ap.add_argument("--tasks-file", default=None, help="file of whitespace/comma separated task ids")
    ap.add_argument("--thinking", choices=["on", "off"], default="on")
    ap.add_argument("--temp", type=float, default=0.2)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--max-tool-calls", type=int, default=28)
    ap.add_argument("--max-time", type=float, default=0.0, help="per-task wall cap in seconds; 0 = no cap")
    ap.add_argument("--prompt-file", default=None, help="system prompt file; {problem_description} is interpolated")
    ap.add_argument("--no-compaction", action="store_true")
    ap.add_argument("--model", default="local")
    ap.add_argument("--skip-done", action="store_true", help="skip tasks already present in the results file")
    ap.add_argument("--max-no-tool", type=int, default=4,
                    help="legacy nudge mode only: no-tool turns tolerated before the run ends")
    ap.add_argument("--nudge", choices=["legacy", "kaggle"], default="legacy",
                    help="kaggle = HARNESS_README 5.3 continuation nudges (3 consecutive, per-condition text); legacy = local strikes")
    ap.add_argument("--think-budget", type=int, default=None,
                    help="cap reasoning tokens per turn (llama-server thinking_budget_tokens); Kaggle v6w uses 1024")
    ap.add_argument("--repo-dir", default=None,
                    help="use this checkout instead of repos\\<repo>; lets two agent loops run at once without sharing a working tree")
    ap.add_argument("--isolate", action="store_true",
                    help="give THIS run its own git worktree of repos\\<repo>. Without it, two concurrent "
                         "gate_run processes share one working tree: each one's reset_repo() wipes the "
                         "other's edits, and git diff then reports a phantom 80-136 file 'patch'. "
                         "Verified: 91 patches across 25 tags were corrupted this way.")
    ap.add_argument("--oracle", choices=["none", "file", "scope"], default="none",
                    help="diagnostic: tell the agent the gold file (file) or the gold file + enclosing function/class (scope)")
    ap.add_argument("--tools", choices=["legacy", "kaggle"], default="legacy",
                    help="kaggle = the scorer's tool surface (filepath, write_file, get_code_subgraph(nodes), no search_code), "
                         "uncut tool results, free malformed calls")
    ap.add_argument("--edit-engine", choices=["real", "strict"], default=None,
                    help="real = the scorer's apply_replacement (exact/flexible/regex/unescaped); strict = old exact-only matcher")
    ap.add_argument("--kaggle-prompt", action="store_true",
                    help="first user message = the scorer's template (problem + budget + instructions + workspace tree)")
    ap.add_argument("--no-bash", action="store_true", help="run_command through cmd.exe instead of Git bash")
    ap.add_argument("--result-cap", type=int, default=None, help="override the tool-result character cap")
    args = ap.parse_args()

    R.QUIET = True
    R.set_tools_mode(args.tools)
    if args.edit_engine:
        R.EDIT_ENGINE = args.edit_engine
    if args.kaggle_prompt:
        R.FIRST_MSG = "kaggle"
    if args.no_bash:
        R.USE_BASH = False
    if args.result_cap:
        R.RESULT_CAP = args.result_cap
    R.THINKING = args.thinking == "on"
    R.TEMPERATURE = args.temp
    R.TOP_P, R.TOP_K = args.top_p, args.top_k
    R.MAX_TOKENS = args.max_tokens
    R.MAX_NO_TOOL = args.max_no_tool
    R.NUDGE_MODE = args.nudge
    R.THINK_BUDGET = args.think_budget
    if args.oracle != "none":
        R.HINT_FN = lambda task: oracle_hint(task, args.oracle)

    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    res_path = runs / f"{args.tag}.results.jsonl"
    run_patches_dir = runs / f"{args.tag}.patches"
    run_patches_dir.mkdir(exist_ok=True)
    R.TRACE_FILE = str(runs / f"{args.tag}.trace.jsonl")

    prompt_tpl = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else None
    done = set()
    if args.skip_done and res_path.exists():
        done = {json.loads(l)["task"] for l in res_path.read_text(encoding="utf-8").splitlines() if l.strip()}

    ids = [t for t in read_tasks(args) if t not in done]
    cfg = {k: v for k, v in vars(args).items()}
    print(f"[gate_run] tag={args.tag} tasks={len(ids)} cfg={json.dumps(cfg)}", flush=True)

    # ---- PER-RUN REPO ISOLATION ----
    # Two concurrent gate_run processes sharing repos\<repo> corrupt each other: each
    # reset_repo() wipes the other's working tree, so git diff reports a phantom
    # 80-136 file patch of deletions the model never made. 91 patches across 25 tags
    # were corrupted this way (verified: byte-identical patches in unrelated tags,
    # and sidecar writes 2-9s apart). A worktree gives each run its own tree + index
    # while sharing the object store, so it costs no disk.
    isolate_dir = None
    if args.isolate and not args.repo_dir:
        isolate_dir = make_isolated_worktree(args.tag)
        if isolate_dir:
            args.repo_dir = str(isolate_dir)
            print(f"[gate_run] isolated worktree: {isolate_dir}", flush=True)
        else:
            print("[gate_run] WARNING: could not create a worktree -- falling back to the "
                  "shared repo. Do NOT run this concurrently with another gate_run.", flush=True)

    resolved = 0
    try:
        for i, tid in enumerate(ids, 1):
            task = R.load_task(tid)
            R.set_repo(task["repo"].split("/")[-1])
            if args.repo_dir:
                R.REPO = Path(args.repo_dir).resolve()
        sysprompt = None
        if prompt_tpl is not None:
            sysprompt = prompt_tpl.replace("{problem_description}", task["problem_statement"])
        row = {"task": tid, "tag": args.tag, "thinking": args.thinking, "temp": args.temp}
        t0 = time.time()
        try:
            diff, calls, dur, submitted = R.run_agent(
                task, args.model, args.max_tool_calls, system_prompt=sysprompt,
                max_time_s=args.max_time, use_compaction=not args.no_compaction)
            row.update(R.LAST_RUN)
            row["patch_chars"] = len(diff)
            row["diff"] = diff[:8000]
            # Full patch to a sidecar: rescore_pinned.py needs the COMPLETE diff, and an 8000-char
            # cap makes any larger patch unscorable in the pinned pass (silent denominator loss).
            try:
                (run_patches_dir / f"{task['instance_id']}.patch").write_text(diff, encoding="utf-8")
            except OSError:
                pass
            if diff.strip():
                passed, log = R.verify(task, diff)
                row["resolved"] = bool(passed)
                row["verify_tail"] = log[-400:]
            else:
                row["resolved"] = False
        except Exception as e:
            row.update(resolved=False, end_reason=f"driver_exception:{type(e).__name__}", error=str(e)[:300])
        row["wall_s"] = round(time.time() - t0)
        resolved += 1 if row.get("resolved") else 0
        with open(res_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(ids)}] {tid} resolved={row.get('resolved')} end={row.get('end_reason')} "
              f"calls={row.get('calls')} turns={row.get('turns')} first_edit={row.get('first_edit_call')} "
              f"edit_ok/err={row.get('edit_ok')}/{row.get('edit_err')} patch={row.get('patch_chars')} "
              f"nudges={row.get('nudges')} len_turns={row.get('length_turns')} "
              f"wall={row['wall_s']}s", flush=True)
    finally:
        if isolate_dir:
            remove_isolated_worktree(args.tag)
            print(f"[gate_run] removed worktree {isolate_dir.name}", flush=True)
    print(f"[gate_run] DONE tag={args.tag} resolved={resolved}/{len(ids)}", flush=True)


if __name__ == "__main__":
    main()
