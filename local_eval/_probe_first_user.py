import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
p = ROOT / "submit_v6w" / "out_v6w" / "results" / "traces" / "trace_rich_4079.json"
d = json.load(open(p, encoding="utf-8"))
u = d["steps"][1]["message"]
i = u.find("## Task Budget")
j = u.find("```")
print(u[i:j + 40])
print("....[tree omitted]....")
k = u.rfind("```")
print(u[k - 80:])
out = pathlib.Path(__file__).resolve().parent / "runs" / "kaggle_first_user_4079.txt"
out.write_text(u, encoding="utf-8")
print("saved", out, len(u))
