"""Scorer-parity check: re-score a Kaggle run's final patches with the local pinned replay engine.

Kaggle outputs do not store the final patch, so it is rebuilt by replaying every successful
edit_file/write_file diff from the trace onto a clean checkout at the task's base commit. The
rebuilt patch is trusted only if its length equals Kaggle's recorded patch_chars; otherwise the
task is reported UNRECONSTRUCTED (e.g. run_command edits) and not scored.

python score_kaggle_patches.py --run ..\\submit_remap_e4b\\out_v1 --tag kaggle_e4b_remap_v1
Writes runs\\<tag>.kscore.jsonl.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEMMA = HERE.parent
KB = GEMMA / "kb"
TASKS_JSONL = GEMMA / "comp_files" / "tasks.jsonl"
GOLDGATE = KB / "replays" / "goldgate_all.json"

sys.path.insert(0, str(KB))
from kblib import replay as rp, gold  # noqa: E402


def git(cwd, *args, inp=None):
    return subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def edit_diffs(trace_path):
    tr = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    out, shell_calls = [], 0
    for s in tr.get("steps", []):
        for c in s.get("tool_calls") or []:
            if c.get("function_name") == "run_command":
                shell_calls += 1
        cont = (s.get("observation") or {}).get("content")
        if not isinstance(cont, str) or '"diff"' not in cont:
            continue
        try:
            d = json.loads(cont)
        except ValueError:
            continue
        if d.get("status") == "ok" and d.get("diff") and d.get("filepath"):
            if d.get("is_truncated"):
                return None, shell_calls
            out.append((d["filepath"], d["diff"]))
    return out, shell_calls


def rebuild(clone, base_commit, diffs):
    git(clone, "checkout", "-q", "-f", base_commit)
    git(clone, "clean", "-qfdx")
    for fp, diff in diffs:
        body = diff if diff.endswith("\n") else diff + "\n"
        patch = f"diff --git a/{fp} b/{fp}\n{body}"
        r = git(clone, "apply", "--recount", "--whitespace=nowarn", "-", inp=patch)
        if r.returncode != 0:
            return None, f"apply failed for {fp}: {r.stderr.strip()[:200]}"
    return git(clone, "diff").stdout, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="Kaggle output dir with run_rows.jsonl and results/traces")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--repo-dir", default=str(HERE / "repos" / "rich"))
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    run = Path(args.run)
    rows = [json.loads(l) for l in (run / "run_rows.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    goldgate = json.loads(GOLDGATE.read_text(encoding="utf-8"))
    raw = {json.loads(l)["instance_id"]: json.loads(l)
           for l in TASKS_JSONL.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()}
    rp.load_raw_tasks(TASKS_JSONL)
    tasks_gold = gold.build_tasks_gold(TASKS_JSONL)

    tmp = Path(tempfile.mkdtemp(prefix="kscore_"))
    clone = tmp / "repo"
    out_rows = []
    try:
        r = git(tmp, "clone", "-q", "--no-local", str(Path(args.repo_dir).resolve()), str(clone))
        if r.returncode != 0:
            sys.exit(f"clone failed: {r.stderr}")
        with rp.ReplayEngine(tasks_gold) as eng:
            for row in rows:
                tid = row["id"]
                rec = raw[tid]
                validity = goldgate.get(tid, {}).get("gold_first", "UNKNOWN")
                out = {"task": tid, "gold_validity": validity, "kaggle_resolved": row.get("resolved"),
                       "kaggle_patch_chars": row.get("patch_chars")}
                diffs, shell = edit_diffs(run / "results" / "traces" / f"trace_{tid}.json")
                patch, err = (None, "truncated diff in trace") if diffs is None else rebuild(clone, rec["base_commit"], diffs)
                out["shell_calls"] = shell
                if patch is None or len(patch) != row.get("patch_chars"):
                    out.update(local_result="UNRECONSTRUCTED", rebuilt_chars=None if patch is None else len(patch),
                               reason=err or "rebuilt length != Kaggle patch_chars")
                elif not patch.strip():
                    out.update(local_result="EMPTY_PATCH", local_resolved=False, rebuilt_chars=0)
                else:
                    gold_pass = None
                    if validity == "VALID-GOLD-RELATIVE":
                        gold_pass = eng.gold_first(rec["repo"], tid, rec["base_commit"],
                                                   timeout_s=args.timeout).get("gold_pass_tests", [])
                    res = eng.run_candidate(rec["repo"], tid, rec["base_commit"], kind="patch",
                                            patch_text=patch, timeout_s=args.timeout, gold_pass_tests=gold_pass)
                    if res.get("result") in ("INFRA", "APPLY_FAIL"):
                        out.update(local_result=res["result"], local_resolved=None, reason=res.get("reason"))
                    else:
                        ok = res.get("gold_relative") if validity == "VALID-GOLD-RELATIVE" else res.get("harness_like")
                        out.update(local_result="PASS" if ok else "FAIL", local_resolved=bool(ok),
                                   rebuilt_chars=len(patch), passed=res.get("passed"), failed=res.get("failed"))
                scorable = validity in ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE")
                out["agrees"] = (out.get("local_resolved") == row.get("resolved")) if scorable and "local_resolved" in out and out["local_resolved"] is not None else None
                out_rows.append(out)
                print(f"{tid:<10} valid={validity:<20} kaggle={str(row.get('resolved')):<5} "
                      f"local={out['local_result']:<16} agrees={out['agrees']}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    (HERE / "runs" / f"{args.tag}.kscore.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in out_rows), encoding="utf-8")
    judged = [r for r in out_rows if r["agrees"] is not None]
    print(f"\n[{args.tag}] scorer agreement {sum(r['agrees'] for r in judged)}/{len(judged)} "
          f"judged tasks ({len(out_rows) - len(judged)} not judged)")


if __name__ == "__main__":
    main()
