"""Find forum messages that tie an architecture choice (sub-agents / skills / LoRA / loop agents) to a BOARD score,
since board numbers are the only evidence of transfer to the hidden repos. Prints compact snippets per category."""
import json
import re
from collections import defaultdict

T = json.load(open("discussions/20261108/topics.json", encoding="utf-8"))
CATS = {
    "lora": r"\blora\b|adapter",
    "skills": r"\bskills?\b|run_skill_script|SKILL\.md",
    "subagent": r"sub[-_ ]?agent|agent_tool|AgentTool|router|SequentialAgent|LoopAgent|ParallelAgent|multi[- ]agent",
}
SCORE = re.compile(r"(?<![\d.])0\.(?:0[0-9]|1[0-9]|2[0-9])(?!\d)")
BOARD = re.compile(r"\b(LB|leaderboard|public score|scored|board|submission|submitted)\b", re.I)


def walk(msgs, tid, title):
    for m in msgs:
        yield tid, title, m
        yield from walk(m.get("replies") or [], tid, title)


hits = defaultdict(list)
for t in T:
    for tid, title, m in walk(t.get("messages") or [], t["id"], t["title"]):
        txt = m.get("text") or ""
        if not SCORE.search(txt) or not BOARD.search(txt):
            continue
        for cat, pat in CATS.items():
            for mm in re.finditer(pat, txt, re.I):
                # sentence-ish window around the keyword that also contains a score
                a, b = max(0, mm.start() - 260), min(len(txt), mm.end() + 260)
                win = re.sub(r"\s+", " ", txt[a:b])
                if SCORE.search(win):
                    hits[cat].append((tid, title[:60], m.get("votes", 0), win))
                    break
for cat in CATS:
    seen = set()
    rows = [h for h in hits[cat] if not (h[0], h[3][:80]) in seen and not seen.add((h[0], h[3][:80]))]
    print(f"\n######## {cat.upper()}: {len(rows)} messages with a board score near the keyword")
    for tid, title, v, win in rows[:40]:
        print(f"[{tid}] ({v}v) {title}\n    ...{win}...")
