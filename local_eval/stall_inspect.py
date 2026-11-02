"""Characterise a stalled (finish=length) message from a *.stall.<task>.json dump.  CPU only.
python stall_inspect.py runs\\<tag>.trace.jsonl.stall.<task>.json
"""
import json, sys, re, collections, zlib

d = json.load(open(sys.argv[1], encoding="utf-8"))
m = d["stalled_message"]
print("task", d["task"], "finish", d["finish"], "keys", list(m.keys()))
for field in ("reasoning_content", "reasoning", "content"):
    s = m.get(field)
    if not s:
        continue
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    c = collections.Counter(lines)
    top = c.most_common(3)
    comp = len(zlib.compress(s.encode("utf-8"))) / max(1, len(s.encode("utf-8")))
    print(f"\n[{field}] chars={len(s)} lines={len(lines)} unique_lines={len(c)} zlib_ratio={comp:.3f}")
    for line, n in top:
        print(f"   x{n}: {line[:110]}")
    print("   HEAD:", s[:400].replace("\n", "\\n"))
    print("   TAIL:", s[-400:].replace("\n", "\\n"))
    print("   has <|tool_call>:", "<|tool_call>" in s, "| has tool_call|>:", "<tool_call|>" in s,
          "| 'diff --git' count:", s.count("diff --git"), "| fenced blocks:", s.count("```") // 2)
print("\nmessages_before:", len(d["messages_before"]), "last roles:", [x.get("role") for x in d["messages_before"][-4:]])
