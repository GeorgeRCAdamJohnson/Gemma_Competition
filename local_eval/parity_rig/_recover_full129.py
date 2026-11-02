"""Recover a full-pool verdict from per-task artifacts when the harness's
task_results.jsonl was overwritten per chunk.

Verdict proxy: the harness runs only the FAIL_TO_PASS + PASS_TO_PASS node ids and
fails a task if any test fails, errors, or is skipped. So a test_outputs log with
>=1 passed and 0 failed/error/skipped == resolved.

Validated against the 9 tasks whose true labels survived in task_results.jsonl.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]          # .../Gemma
RUN = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "kaggle_pkg" / "out_v7"
OUT = RUN / "results" / "test_outputs"

COUNTS = ("passed", "failed", "error", "errors", "skipped", "xfailed", "xpassed")


def parse(path: Path) -> dict:
    """Extract the pytest terminal summary (last one wins)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    body = text.split("STDOUT:", 1)[-1]
    best: dict[str, int] = {}
    for line in re.findall(r"^=*\s*(.+?)\s*=*$", body, re.M):
        hits = {c: int(n) for n, c in re.findall(r"(\d+)\s+(%s)" % "|".join(COUNTS), line)}
        if hits:
            best = hits
    return best


def resolved(counts: dict[str, int]) -> bool:
    passed = counts.get("passed", 0)
    bad = sum(counts.get(k, 0) for k in ("failed", "error", "errors", "skipped"))
    return passed > 0 and bad == 0


def main() -> None:
    # ---- validate the proxy on the labels that survived ----
    truth_path = RUN / "results" / "task_results.jsonl"
    truth = {}
    if truth_path.exists():
        for line in truth_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            truth[r["instance_id"]] = bool(r["resolved"])
    agree = tot = 0
    for tid, want in truth.items():
        p = OUT / f"{tid}.log"
        if not p.exists():
            continue
        got = resolved(parse(p))
        tot += 1
        agree += int(got == want)
        if got != want:
            print(f"  MISMATCH {tid}: truth={want} proxy={got} {parse(p)}")
    print(f"\nproxy validation on surviving labels: {agree}/{tot} agree")

    # ---- full pool ----
    tasks = [json.loads(l) for l in (BASE / "comp_files" / "tasks.jsonl")
             .read_text(encoding="utf-8").splitlines()]
    rows = []
    for t in tasks:
        tid = t["instance_id"]
        p = OUT / f"{tid}.log"
        c = parse(p) if p.exists() else {}
        rows.append(dict(instance_id=tid, repo=t["repo"],
                         verified=p.exists(), counts=c, resolved=p.exists() and resolved(c)))

    solved = [r for r in rows if r["resolved"]]
    print(f"\n=== ca5-31B FULL POOL (recovered): {len(solved)}/{len(rows)} = "
          f"{len(solved)/len(rows):.3f} ===")
    print(f"    no verification artifact (never submitted): {sum(1 for r in rows if not r['verified'])}")

    by_repo: dict[str, list[int]] = {}
    for r in rows:
        d = by_repo.setdefault(r["repo"], [0, 0])
        d[0] += int(r["resolved"])
        d[1] += 1
    print("\nper-repo:")
    for repo, (s, n) in sorted(by_repo.items(), key=lambda kv: -kv[1][1]):
        print(f"  {repo:28s} {s:3d}/{n:<3d}")

    # ---- references ----
    refs = {}
    for name, sub in (("ca5(E4B)", "ca5"), ("ca5_v2(E4B)", "ca5_v2")):
        f = BASE / "local_eval" / "parity_rig" / "m1_full129" / sub / "task_results.jsonl"
        if f.exists():
            refs[name] = {json.loads(l)["instance_id"]
                          for l in f.read_text(encoding="utf-8").splitlines()
                          if json.loads(l).get("resolved")}
    union = set().union(*refs.values()) if refs else set()
    mine = {r["instance_id"] for r in solved}
    print(f"\nrefs: " + ", ".join(f"{k} {len(v)}/129" for k, v in refs.items()))
    print(f"NEWLY solved vs E4B union 15: {len(mine - union)} -> {sorted(mine - union)}")
    print(f"LOST vs E4B union: {len(union - mine)} -> {sorted(union - mine)}")
    print("\nsolved list:", sorted(mine))

    (RUN / "recovered_full129.json").write_text(
        json.dumps(dict(rows=rows, solved=sorted(mine)), indent=1), encoding="utf-8")
    print(f"\nwrote {RUN / 'recovered_full129.json'}")


if __name__ == "__main__":
    main()
