"""Replay a saved stalled conversation state under different sampling / thinking settings.
One request per sample, capped at --max-tokens; scores repetition and whether a tool call appeared.
GPU: one stream.
  python replay_stall.py --stall runs\\X.trace.jsonl.stall.rich_3944.json --label t02 --temp 0.2 --n 3
"""
import argparse, collections, json, pathlib, sys, time, urllib.request, zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_local as R  # noqa: E402


def rep_stats(s):
    if not s:
        return 0, 1.0, 0
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    top = collections.Counter(lines).most_common(1)
    max_rep = top[0][1] if top else 0
    ratio = len(zlib.compress(s.encode("utf-8"))) / max(1, len(s.encode("utf-8")))
    return max_rep, ratio, len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stall", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--temp", type=float, default=0.2)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--min-p", type=float, default=None)
    ap.add_argument("--freq-pen", type=float, default=None)
    ap.add_argument("--pres-pen", type=float, default=None)
    ap.add_argument("--rep-pen", type=float, default=None, help="llama.cpp repeat_penalty (not exposed by Kaggle sampling.yaml)")
    ap.add_argument("--thinking", choices=["on", "off"], default="on")
    ap.add_argument("--think-budget", type=int, default=None)
    ap.add_argument("--strip-thoughts", action="store_true", help="drop reasoning_content from earlier assistant messages")
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    d = json.load(open(args.stall, encoding="utf-8"))
    base = d["messages_before"]
    if args.strip_thoughts:
        base = [{k: v for k, v in m.items() if k != "reasoning_content"} if m.get("role") == "assistant" else m for m in base]

    out_path = pathlib.Path(args.out) if args.out else HERE / "runs" / "replay_stall.jsonl"
    for i in range(args.n):
        payload = {"model": "local", "messages": base, "tools": R.TOOLS, "temperature": args.temp,
                   "max_tokens": args.max_tokens, "stream": False, "seed": args.seed_base + i}
        for k, v in (("top_p", args.top_p), ("top_k", args.top_k), ("min_p", args.min_p), ("frequency_penalty", args.freq_pen),
                     ("presence_penalty", args.pres_pen), ("repeat_penalty", args.rep_pen)):
            if v is not None:
                payload[k] = v
        if args.thinking == "off":
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        elif args.think_budget:
            payload["thinking_budget_tokens"] = args.think_budget
        t0 = time.time()
        req = urllib.request.Request(R.OLLAMA, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as resp:
            j = json.loads(resp.read())
        ch = j["choices"][0]
        m = ch["message"]
        content = m.get("content") or ""
        reasoning = m.get("reasoning_content") or ""
        tcs = [tc["function"]["name"] for tc in (m.get("tool_calls") or [])]
        c_rep, c_ratio, _ = rep_stats(content)
        r_rep, r_ratio, _ = rep_stats(reasoning)
        ctok = j.get("usage", {}).get("completion_tokens")
        loop = (c_rep >= 5 and len(content) > 1500) or (r_rep >= 5 and len(reasoning) > 1500)
        row = {"label": args.label, "stall": pathlib.Path(args.stall).name, "sample": i, "finish": ch.get("finish_reason"),
               "ctok": ctok, "tools": tcs, "reasoning_chars": len(reasoning), "content_chars": len(content),
               "content_max_line_rep": c_rep, "content_zlib": round(c_ratio, 3),
               "reasoning_max_line_rep": r_rep, "reasoning_zlib": round(r_ratio, 3), "loop": loop,
               "secs": round(time.time() - t0, 1), "cfg": {k: v for k, v in payload.items() if k not in ("messages", "tools")},
               "content_head": content[:300], "reasoning_head": reasoning[:300], "reasoning_tail": reasoning[-300:],
               "content_tail": content[-300:],
               "tool_args": [tc["function"].get("arguments", "")[:300] for tc in (m.get("tool_calls") or [])]}
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{args.label} s{i}] finish={row['finish']} ctok={ctok} tools={tcs} reasoning={len(reasoning)}c(rep {r_rep}) "
              f"content={len(content)}c(rep {c_rep}, z {c_ratio:.2f}) loop={loop} {row['secs']}s", flush=True)


if __name__ == "__main__":
    main()
