import json, sys, io
sys.path.insert(0, r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval")
import run_local as R

R.TRACE_FILE = None


def rounds(n, par_at=None):
    msgs = [{"role": "system", "content": "SYS"}, {"role": "user", "content": "TASK: fix isatty"}]
    for k in range(1, n + 1):
        ncalls = 2 if par_at == k else 1
        calls = [{"id": f"c{k}_{j}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
                 for j in range(ncalls)]
        msgs.append({"role": "assistant", "content": f"text{k}", "reasoning_content": f"think{k}", "tool_calls": calls})
        for c in calls:
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": "{\"status\":\"ok\"}"})
    return msgs


class FakeResp:
    def __init__(self, text): self.text = text
    def read(self): return json.dumps({"choices": [{"message": {"content": self.text}}], "usage": {"prompt_tokens": 123}}).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


seen = {}
def fake_urlopen(req, timeout=None):
    seen["payload"] = json.loads(req.data)
    return FakeResp(seen.get("reply", "SUMMARY-1"))
R.urllib.request.urlopen = fake_urlopen
stats = {"turns": 12}

# 1. split index and tail shape on a clean alternation
m = rounds(12)
ev = R._adk_events(m[1:])
assert len(ev) == 25, len(ev)
assert R._safe_split(ev, 5) == 19, R._safe_split(ev, 5)

# 2. parallel calls merge into one response event
m2 = rounds(12, par_at=11)
ev2 = R._adk_events(m2[1:])
assert len(ev2) == 25, len(ev2)
assert len(ev2[21]["msgs"]) == 2 or any(len(e["msgs"]) == 2 for e in ev2)

# 3. too few events -> no compaction and no server call
seen.clear()
assert R.adk_compact(rounds(2), None, "m", "t", stats, 15000) is None and "payload" not in seen

# 4. first compaction: prompt format and rebuilt history
out = R.adk_compact(m, None, "m", "t", stats, 15000)
assert out is not None
new, summ = out
assert summ == "SUMMARY-1"
assert new[0]["content"] == "SYS" and new[1] == {"role": "user", "content": "For context:\n[model] said: SUMMARY-1"}
assert new[2]["role"] == "assistant" and new[2]["content"] == "text10", new[2]
assert len(new) == 2 + 6 + 0 or len(new) == 2 + 6, len(new)
p = seen["payload"]
assert p["messages"] == [{"role": "user", "content": p["messages"][0]["content"]}]
prompt = p["messages"][0]["content"]
assert prompt.startswith("The following is a conversation history")
assert "\\n\\nuser: TASK: fix isatty" in prompt
assert "\\nsibling_conform_agent: think1\\nsibling_conform_agent: text1\\n" in prompt
assert "text10" not in prompt and "tool" not in prompt.split("\\n\\n", 1)[1].replace("fix isatty", "")
assert "tools" not in p and p["chat_template_kwargs"] == {"enable_thinking": False}
assert prompt.count("\n") == 0 or "\\n" in prompt

# 5. second compaction on a longer history: seed line comes first and the old summary message is not re-summarised
more = list(new)
for k in range(13, 22):
    more.append({"role": "assistant", "content": f"text{k}", "reasoning_content": f"think{k}",
                 "tool_calls": [{"id": f"c{k}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]})
    more.append({"role": "tool", "tool_call_id": f"c{k}", "content": "{}"})
seen["reply"] = "SUMMARY-2"
out2 = R.adk_compact(more, "SUMMARY-1", "m", "t", stats, 15000)
assert out2 is not None and out2[1] == "SUMMARY-2"
prompt2 = seen["payload"]["messages"][0]["content"]
body2 = prompt2.split("\\n\\n", 1)[1] if "\\n\\n" in prompt2 else prompt2
assert prompt2.split("{conversation_history}")[0] and "model: SUMMARY-1" in prompt2
assert prompt2.index("model: SUMMARY-1") < prompt2.index("sibling_conform_agent: think10")
assert "For context" not in prompt2
assert out2[0][1]["content"] == "For context:\n[model] said: SUMMARY-2"
assert out2[0][2]["role"] == "assistant"

# 6. empty summary -> no compaction
seen["reply"] = "   "
assert R.adk_compact(m, None, "m", "t", stats, 15000) is None
print("ALL OK; tail after first compaction:", [x["role"] for x in new])
