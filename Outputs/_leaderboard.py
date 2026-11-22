"""Summarise a downloaded Kaggle public leaderboard zip: teams, score distribution, rank bands, our position.
Scores are truncated k/58 (public board = 58 tasks). usage: python Outputs/_leaderboard.py <zip> [team substring]"""
import csv
import io
import sys
import zipfile
from collections import Counter

path = sys.argv[1]
ours = sys.argv[2].lower() if len(sys.argv) > 2 else "comfyops"
with zipfile.ZipFile(path) as z:
    name = next(n for n in z.namelist() if n.endswith(".csv"))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8")))
print("file", name, "| columns", list(rows[0]))
score_key = next(k for k in rows[0] if "score" in k.lower())
team_key = next(k for k in rows[0] if "team" in k.lower() and "name" in k.lower())
scores = [float(r[score_key]) for r in rows if r[score_key]]
print(f"teams {len(rows)}, scored {len(scores)}")
by = Counter(round(s, 2) for s in scores)
rank = 0
print("score  teams  ranks          tasks/58")
for s in sorted(by, reverse=True):
    first = rank + 1
    rank += by[s]
    print(f"{s:5.2f}  {by[s]:5d}  {first:4d}-{rank:<6d}   {int(round(s * 58 + 0.49))}")
for i, r in enumerate(rows, 1):
    if ours in r[team_key].lower():
        print("OURS:", i, r[team_key], r[score_key])
