"""CPU-only smoke test for the Kaggle-parity changes in run_local.py (no GPU / no model needed)."""
import json, sys
from pathlib import Path

import run_local as R

HERE = Path(__file__).resolve().parent
R.set_tools_mode("kaggle")
R.QUIET = True

task = R.load_task("rich_4079")
R.set_repo("rich")
R.REPO = (HERE / "repos" / "rich_v").resolve()
R.reset_repo(task["base_commit"])

# 1. first user message vs the real sample
sample = (HERE / "runs" / "kaggle_first_user_4079.txt").read_text(encoding="utf-8")
mine = R.kaggle_first_message(task)
print("sample len", len(sample), "mine len", len(mine), "identical:", sample == mine)
if sample != mine:
    n = min(len(sample), len(mine))
    i = next((k for k in range(n) if sample[k] != mine[k]), n)
    print("first diff at", i)
    print("SAMPLE:", repr(sample[max(0, i - 120): i + 200]))
    print("MINE  :", repr(mine[max(0, i - 120): i + 200]))
    # also try modulo trailing whitespace / CRLF
    print("equal after strip:", sample.strip() == mine.strip(), "| equal after CRLF norm:",
          sample.replace("\r\n", "\n") == mine.replace("\r\n", "\n"))

# 2. tool surface sanity
names = [t["function"]["name"] for t in R.ACTIVE_TOOLS]
print("tools:", names)
print("missing-required edit_file(filepath only):", R._missing_required("edit_file", {"filepath": "x"}))
print("unknown tool:", R._missing_required("search_code", {"query": "x"}))
print("adk msg:", json.dumps(R._adk_missing_msg("edit_file", ["old_string"])))

# 3. read_file / run_command / edit_file behaviours
r = R.tool_read_file(filepath="rich/cells.py", start_line=1, end_line=5)
print("read_file keys:", sorted(r.keys()), "| first line:", str(r.get("content"))[:80].replace("\n", "\\n"))
c = R.tool_run_command(command="sed -n '1,3p' rich/cells.py && echo done && ls | head -3")
print("run_command:", json.dumps(c)[:300])

src = R.tool_read_file(filepath="rich/cells.py", start_line=1, end_line=40)
print("edit exact:", json.dumps(R.tool_edit_file(filepath="rich/cells.py", old_string="from __future__ import annotations",
                                                  new_string="from __future__ import annotations  # smoke"))[:260])
print("edit unescaped:", json.dumps(R.tool_edit_file(filepath="rich/cells.py",
      old_string='from __future__ import annotations  # smoke\\n', new_string='from __future__ import annotations\\n'))[:260])
print("edit notfound:", json.dumps(R.tool_edit_file(filepath="rich/cells.py", old_string="THIS_DOES_NOT_EXIST", new_string="x"))[:260])
print("write_file:", json.dumps(R.tool_write_file(filepath="tmp_smoke/sub/a.txt", content="hi")))
R.reset_repo(task["base_commit"])
print("status after reset:", R.git(["status", "--porcelain"]).stdout.strip() or "clean")
