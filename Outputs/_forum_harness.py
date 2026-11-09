"""Harness-mechanics messages from the forum dump, grouped by theme. Prints topic id, votes and a window around
each hit so claims can be checked against the source. python Outputs/_forum_harness.py > Outputs/_forum_harness.txt"""
import json
import re
from collections import defaultdict

T = json.load(open("discussions/20261108/topics.json", encoding="utf-8"))
THEMES = {
    "task_prompt": r"problem_description|\{hints|hints_text|task prompt|Workspace Layout|global_instruction|user[- ]role prompt",
    "free_tools": r"get_status|submit_patch.{0,40}free|count_tool_call|does not count toward",
    "compaction": r"compaction|LlmEventSummarizer|token_threshold|event_retention",
    "context": r"ContextWindow|max_output_tokens|context window|32[,.]?768|overflow",
    "gen_config": r"stop_sequences|presence_penalty|frequency_penalty|seed\b|top_k|response_mime_type",
    "agent_fields": r"include_contents|output_key|before_model|after_model|callback|disallow_transfer",
    "budget_warn": r"80%|budget warning|calls remaining|time_seconds_remaining|continuation nudge|nudge",
    "tools_registry": r"tool registry|ToolRegistry|undeclared tool|hallucinated tool|unknown tool|exit_loop",
    "tests": r"test_patch|reset.{0,20}test|enable_sandbox_testing|PASS_TO_PASS|FAIL_TO_PASS|verification",
    "diff_capture": r"git diff|fallback.{0,30}diff|patch.{0,20}empty|empty patch",
}


def walk(msgs):
    for m in msgs:
        yield m
        yield from walk(m.get("replies") or [])


hits = defaultdict(list)
for t in T:
    for m in walk(t.get("messages") or []):
        txt = re.sub(r"\s+", " ", m.get("text") or "")
        for th, pat in THEMES.items():
            mm = re.search(pat, txt, re.I)
            if mm:
                a, b = max(0, mm.start() - 220), min(len(txt), mm.end() + 320)
                hits[th].append((m.get("votes", 0), t["id"], t["title"][:60], txt[a:b]))
for th in THEMES:
    rows = sorted(hits[th], key=lambda h: -h[0])
    print(f"\n######## {th}: {len(rows)} messages")
    seen = set()
    for v, tid, title, w in rows:
        if (tid, w[:60]) in seen:
            continue
        seen.add((tid, w[:60]))
        print(f"[{tid}] ({v}v) {title}\n   ...{w}...")
        if len(seen) >= 12:
            break
