"""Re-verify saved gate results (and/or validate the gold patch) with a pytest-capable interpreter.

python reverify_gate.py --tags q_off,q_on1024,q_on1024_t1            # re-verify each saved diff
python reverify_gate.py --gold --tasks-file gate8.txt                # gold patch must PASS, empty patch must FAIL

Why: the gate verify() used sys.executable, and the interpreter that launched the gate (.train_env) has no pytest, so
every patch the model produced was scored resolved=False ("No module named pytest" in verify_tail). The diff is saved
in each results row, so the score can be recomputed afterwards without re-running the model.
Verification runs in its own checkout (--repo-dir, default repos\\rich_v), never in a checkout a live run is using.
"""
import argparse, json
from pathlib import Path

import run_local as R

HERE = Path(__file__).resolve().parent
TASKS = HERE.parent / "comp_files" / "tasks.jsonl"


def load_tasks():
    out = {}
    for line in open(TASKS, encoding="utf-8"):
        t = json.loads(line)
        out[t["instance_id"]] = t
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="")
    ap.add_argument("--gold", action="store_true")
    ap.add_argument("--tasks-file", default=None)
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--repo-dir", default=str(HERE / "repos" / "rich_v"))
    a = ap.parse_args()
    tasks = load_tasks()
    R.set_repo("rich")
    R.REPO = Path(a.repo_dir).resolve()
    print("pytest interpreter:", R.pytest_python(), " repo:", R.REPO, flush=True)

    if a.gold:
        ids = []
        if a.tasks:
            ids += [x for x in a.tasks.replace(",", " ").split()]
        if a.tasks_file:
            ids += Path(a.tasks_file).read_text().replace(",", " ").split()
        for tid in ids:
            t = tasks[tid]
            g_ok, g_log = R.verify(t, t["patch"])
            e_ok, e_log = R.verify(t, "")
            print(f"{tid:11} gold={'PASS' if g_ok else 'FAIL'}  empty-patch={'PASS(!)' if e_ok else 'fail(ok)'}", flush=True)
            if not g_ok:
                print("   gold log tail:", g_log[-400:].replace("\n", " | "), flush=True)
        R.reset_repo(tasks[ids[-1]]["base_commit"]) if ids else None
        return

    for tag in [x for x in a.tags.split(",") if x]:
        src = HERE / "runs" / f"{tag}.results.jsonl"
        dst = HERE / "runs" / f"{tag}.reverified.jsonl"
        rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
        done = {}
        if dst.exists():
            for l in open(dst, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    done[(r["task"], r.get("diff") or "")] = r
        out = []
        for r in rows:
            key = (r["task"], r.get("diff") or "")
            if key in done:
                out.append(done[key])
                continue
            diff = r.get("diff") or ""
            if diff.strip():
                ok, log = R.verify(tasks[r["task"]], diff)
            else:
                ok, log = False, "no patch"
            r2 = dict(r)
            r2["resolved_orig"] = r.get("resolved")
            r2["resolved"] = bool(ok)
            r2["verify_tail"] = log[-600:]
            out.append(r2)
        with open(dst, "w", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r) + "\n")
        print(f"== {tag}: {sum(1 for r in out if r['resolved'])}/{len(out)} resolved after re-verify", flush=True)
        for r in out:
            print(f"   {r['task']:11} resolved={r['resolved']!s:5} (orig {r.get('resolved_orig')!s:5}) end={r['end_reason']:10} "
                  f"calls={r['calls']:>3} first_edit={r.get('first_edit_call')} patch={r.get('patch_chars')}", flush=True)


if __name__ == "__main__":
    main()
