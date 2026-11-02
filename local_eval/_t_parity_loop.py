"""Throwaway: drive run_agent with a scripted fake model to verify budget_warning / get_status / submit_patch shapes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_local as R

R.set_tools_mode("kaggle")
R.REPO = R.REPOS_DIR / "rich_v"
R.NUDGE_MODE = "kaggle"
R.FIRST_MSG = "kaggle"
task = R.load_task("rich_4077")

script = []
for i in range(1, 12):
    script.append(("run_command", {"command": f"echo step{i}"}))
script.append(("write_file", {"filepath": "notes.py", "content": "x = 1\n"}))
script.append(("edit_file", {"filepath": "rich/console.py"}))              # malformed: free, no budget_warning
script.append(("get_status", {}))                                        # free, no budget_warning
for i in range(12, 20):
    script.append(("read_file", {"filepath": "rich/console.py", "start_line": 1, "end_line": 3}))
script.append(("get_status", {}))
script.append(("run_command", {"command": "exit 1"}))                    # error shape + warning
for i in range(21, 40):
    script.append(("run_command", {"command": f"echo more{i}"}))

state = {"i": 0, "last_msgs": None}


def fake_chat(messages, model):
    state["last_msgs"] = messages
    i = state["i"]
    state["i"] += 1
    name, args = script[min(i, len(script) - 1)]
    msg = {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}
    return {"choices": [{"message": msg, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            "timings": {"prompt_n": 10, "cache_n": 90, "prompt_ms": 5.0, "predicted_n": 10, "predicted_ms": 100.0,
                        "predicted_per_second": 100.0}}


R.chat = fake_chat
diff, calls, dur, submitted = R.run_agent(task, "fake", 28, system_prompt="sys", max_time_s=0, use_compaction=False)
print("calls", calls, "submitted", submitted, "diff sections", [l for l in diff.splitlines() if l.startswith("diff --git")])
print("LAST_RUN", {k: v for k, v in R.LAST_RUN.items() if k in ("end_reason", "turns", "tool_counts", "calls")})
tool_msgs = [m for m in state["last_msgs"] if m.get("role") == "tool"]
print("n tool msgs:", len(tool_msgs))
warned = [i for i, m in enumerate(tool_msgs) if "budget_warning" in m["content"]]
print("msgs with budget_warning (idx):", warned)
for idx in (11, 12, 13, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38):
    if idx < len(tool_msgs):
        c = tool_msgs[idx]["content"]
        print(idx, (c if len(c) < 330 else c[:200] + " ... " + c[-170:]))
R.reset_repo(task["base_commit"])
