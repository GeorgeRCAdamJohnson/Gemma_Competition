"""Build RESULTS_TABLE.md for a collected Kaggle experiment (any mode that writes lora_progress.json).

Runs automatically at the end of `run_experiment launch/resume` collection; can also be run by hand:
    python -m kaggle_pkg.results_table "Outputs\\e4b-swing-task-repeats-r100"
If the intel DB (kb/attempts.sqlite) exists, each task also shows its pooled E4B rate from all earlier attempts and
whether that rate falls outside this run's 95% interval. The DB is read before this run is added to it.
"""
import json
import sqlite3
import sys
from pathlib import Path

from kaggle_pkg.tool_lora_runner import results_table

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "attempts.sqlite"


def pooled_rates(tasks, exclude_exp):
    if not DB.is_file():
        return None
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(tasks))
        rows = db.execute(
            f"""SELECT task, COUNT(*), AVG(resolved) FROM attempts_unique
                WHERE model NOT LIKE '%31b%' AND resolved IS NOT NULL AND task IN ({marks}) AND exp NOT LIKE ?
                GROUP BY task""", (*tasks, f"%{exclude_exp}%")).fetchall()
    finally:
        db.close()
    return {task: (n, rate) for task, n, rate in rows}


def build(output):
    output = Path(output)
    progress = sorted((output / "results").rglob("lora_progress.json"))
    if len(progress) != 1:
        raise RuntimeError(f"Expected one lora_progress.json under {output / 'results'}, found {len(progress)}")
    records = json.loads(progress[0].read_text(encoding="utf-8"))["tasks"]
    receipt = output / "receipt.json"
    slug = json.loads(receipt.read_text(encoding="utf-8"))["slug"] if receipt.is_file() else output.name
    pooled = pooled_rates(sorted({r["id"] for r in records}), slug.split("/")[-1])
    table = results_table(records, pooled=pooled)
    text = (f"# Results: `{slug}`\n\nSource: `{progress[0].relative_to(output)}`. Solves use the verified definition "
            "(completed, real grade, exit 0, no errors, audited fixer route). 95% CI = Wilson."
            + (" DB pooled = all earlier E4B attempts on the task, every configuration (not a like-for-like baseline)."
               if pooled else "") + "\n\n" + table + "\n")
    (output / "RESULTS_TABLE.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(build(sys.argv[1]))
