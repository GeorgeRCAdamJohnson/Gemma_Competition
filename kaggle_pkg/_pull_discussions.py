"""Dump every discussion topic + all its messages (with nested replies) for the competition, via the official
Kaggle API (kagglesdk competitions.list_competition_topics / list_topic_messages). No scraping.

Writes discussions/<YYYYmmdd>/topics.json (index) and discussions/<YYYYmmdd>/ALL.md (one readable file, newest
activity first). Re-runnable; paces requests and backs off on 429.
usage: python kaggle_pkg/_pull_discussions.py [competition-slug]
"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

import requests
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import (ApiListCompetitionTopicsRequest,
                                                                   ApiListTopicMessagesRequest)

COMP = sys.argv[1] if len(sys.argv) > 1 else "gemma-4-developer-agent"
OUT = Path(__file__).resolve().parents[1] / "discussions" / dt.date.today().strftime("%Y%m%d")
OUT.mkdir(parents=True, exist_ok=True)
api = KaggleApi()
api.authenticate()


def call(fn, req, what):
    for attempt in range(8):
        try:
            with api.build_kaggle_client() as k:
                return fn(k)(req)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else None
            if code == 429:
                w = 20 * (attempt + 1); print(f"  429 on {what}, sleeping {w}s", flush=True); time.sleep(w); continue
            print(f"  HTTP {code} on {what}: {(e.response.text or '')[:200] if e.response is not None else e}", flush=True)
            return None
    return None


def to_dict(m, depth=0):
    return {"id": m.id, "author": m.author_name, "date": str(m.post_date), "votes": m.votes,
            "deleted": m.is_deleted, "text": m.raw_markdown or m.content or "",
            "replies": [to_dict(r, depth + 1) for r in (m.replies or [])]}


topics, page = [], 1
while True:
    req = ApiListCompetitionTopicsRequest()
    req.competition_name = COMP
    req.page = page
    resp = call(lambda k: k.competitions.competition_api_client.list_competition_topics, req, f"topics page {page}")
    got = list(resp.topics or []) if resp else []
    if not got:
        break
    for t in got:
        topics.append({"id": t.id, "title": t.title, "url": t.topic_url, "author": t.author_name,
                       "comments": t.comment_count, "votes": t.votes, "posted": str(t.post_date),
                       "last_comment": str(t.last_comment_post_date), "sticky": t.is_sticky})
    print(f"topics page {page}: {len(got)} (total so far {len(topics)} / reported {resp.total_count})", flush=True)
    if resp.total_count and len(topics) >= resp.total_count:
        break
    page += 1
    time.sleep(1.5)
(OUT / "topics.json").write_text(json.dumps(topics, indent=1), encoding="utf-8")

topics.sort(key=lambda t: t["last_comment"] or t["posted"], reverse=True)
md = [f"# {COMP} discussions - pulled {dt.datetime.now():%Y-%m-%d %H:%M} ({len(topics)} topics)\n"]
for i, t in enumerate(topics, 1):
    req = ApiListTopicMessagesRequest()
    req.competition_name = COMP
    req.topic_id = t["id"]
    req.page_size = 500
    resp = call(lambda k: k.competitions.competition_api_client.list_topic_messages, req, f"topic {t['id']}")
    msgs = [to_dict(m) for m in (resp.messages or [])] if resp else []
    t["messages"] = msgs
    md.append(f"\n---\n\n## {t['title']}\n{t['url']} | by {t['author']} | posted {t['posted'][:16]} | "
              f"last comment {t['last_comment'][:16]} | {t['comments']} comments | {t['votes']} votes\n")

    def emit(m, depth):
        if m["deleted"]:
            return
        pad = "> " * depth
        body = "\n".join(pad + line for line in m["text"].strip().splitlines())
        md.append(f"\n{pad}**{m['author']}** ({m['date'][:16]}, {m['votes']} votes)\n{body}\n")
        for r in m["replies"]:
            emit(r, depth + 1)
    for m in msgs:
        emit(m, 0)
    print(f"[{i}/{len(topics)}] {t['title'][:70]} - {len(msgs)} top-level messages", flush=True)
    time.sleep(1.0)
(OUT / "topics.json").write_text(json.dumps(topics, indent=1, default=str), encoding="utf-8")
(OUT / "ALL.md").write_text("\n".join(md), encoding="utf-8")
print(f"DONE -> {OUT / 'ALL.md'} ({sum(len(t.get('messages', [])) for t in topics)} top-level messages)")
