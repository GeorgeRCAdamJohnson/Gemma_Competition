# Merge the latest Kaggle submissions into Outputs/_submissions.json (adds new refs, updates status/score of known ones).
import json
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

P = Path("Outputs/_submissions.json")
api = KaggleApi()
api.authenticate()
rows = json.loads(P.read_text(encoding="utf-8"))
by = {r["ref"]: r for r in rows}
for s in api.competition_submissions("gemma-4-developer-agent")[:10]:
    r = {"ref": int(s.ref), "date": str(s.date), "desc": s.description or "", "status": str(s.status),
         "score": str(s.public_score or ""), "err": s.error_description or "", "url": str(getattr(s, "url", "") or "")}
    if r["ref"] in by:
        by[r["ref"]].update({k: r[k] for k in ("status", "score", "err")})
    else:
        rows.append(r)
        print("added", r["ref"], r["date"][:16], r["score"], r["desc"][:60])
P.write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("total", len(rows))
