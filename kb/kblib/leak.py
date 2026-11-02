"""Scorer-gaming leak check (design §1, §15/§18.3).

leakcheck scans a config or prompt (scope config) or a tooling file (scope
tooling) for gold-patch text and problem-statement fingerprints. --scope tooling
allows bare task ids (query recipes) but still flags gold lines.
"""
from __future__ import annotations

import json
import re


def _load_gold(tasks_jsonl_path):
    gold_lines = set()
    titles = set()
    task_ids = set()
    for ln in tasks_jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        rec = json.loads(ln)
        task_ids.add(rec["instance_id"])
        prob = (rec.get("problem_statement", "") or "").splitlines()
        if prob:
            titles.add(prob[0].strip())
        for part in (rec.get("patch", ""),):
            for pl in part.split("\n"):
                if pl.startswith("+") and not pl.startswith("+++"):
                    body = pl[1:].strip()
                    if len(body) >= 20:
                        gold_lines.add(body)
    return gold_lines, titles, task_ids


def check(text, tasks_jsonl_path, scope="config"):
    gold_lines, titles, task_ids = _load_gold(tasks_jsonl_path)
    hits = []
    norm = text
    for gl in gold_lines:
        if gl in norm:
            hits.append({"type": "gold_line", "text": gl[:80]})
    for t in titles:
        if t and len(t) >= 12 and t in norm:
            hits.append({"type": "problem_title", "text": t[:80]})
    if scope != "tooling":
        for tid in task_ids:
            if re.search(r"\b" + re.escape(tid) + r"\b", norm):
                hits.append({"type": "task_id", "text": tid})
    return hits
