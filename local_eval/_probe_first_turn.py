"""Throwaway probe: ONE agent turn (system prompt + problem + tools) on the local llama-server,
varying thinking on/off and sampling. Records whether the turn ends in a tool call, and what the
reasoning text looks like (length, repetition). No agent loop, nothing to verify."""
import json, sys, time, urllib.request
sys.path.insert(0, ".")
import run_local as R


def dup_ratio(text, n=6):
    w = text.split()
    if len(w) < n + 1:
        return 0.0
    grams = [" ".join(w[i:i + n]) for i in range(len(w) - n + 1)]
    return round(1.0 - len(set(grams)) / len(grams), 3)


def one_turn(task, think, temp, top_p, top_k, max_tokens):
    R.set_repo(task["repo"].split("/")[-1])
    R.reset_repo(task["base_commit"])
    msgs = [
        {"role": "system", "content": R.SYSTEM_PROMPT},
        {"role": "user", "content": f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."},
    ]
    payload = {"model": "local", "messages": msgs, "tools": R.TOOLS, "temperature": temp,
               "max_tokens": max_tokens, "stream": False}
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None:
        payload["top_k"] = top_k
    if not think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(R.OLLAMA, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=None) as r:
        resp = json.loads(r.read())
    dt = time.time() - t0
    ch = resp["choices"][0]
    m = ch["message"]
    rc = m.get("reasoning_content") or ""
    ct = m.get("content") or ""
    tcs = m.get("tool_calls") or []
    return {
        "task": task["instance_id"], "think": think, "temp": temp, "top_p": top_p, "top_k": top_k,
        "finish": ch.get("finish_reason"), "secs": round(dt, 1),
        "completion_tokens": (resp.get("usage") or {}).get("completion_tokens"),
        "msg_keys": sorted(m.keys()),
        "reasoning_chars": len(rc), "content_chars": len(ct), "n_tool_calls": len(tcs),
        "tool_names": [t["function"]["name"] for t in tcs],
        "reasoning_dup6": dup_ratio(rc), "content_dup6": dup_ratio(ct),
        "reasoning_head": rc[:500], "reasoning_tail": rc[-500:],
        "content_head": ct[:300],
    }


def main():
    tasks = [R.load_task(t) for t in sys.argv[1].split(",")]
    max_tokens = int(sys.argv[2])
    configs = [
        (True, 0.2, None, None),
        (True, 1.0, 0.95, 64),
        (False, 0.2, None, None),
        (False, 1.0, 0.95, 64),
    ]
    out = open("_probe_first_turn.jsonl", "a", encoding="utf-8")
    for t in tasks:
        for think, temp, tp, tk in configs:
            row = one_turn(t, think, temp, tp, tk, max_tokens)
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"{row['task']} think={int(think)} temp={temp} finish={row['finish']} {row['secs']}s "
                  f"tok={row['completion_tokens']} reason={row['reasoning_chars']}ch(dup6={row['reasoning_dup6']}) "
                  f"content={row['content_chars']}ch calls={row['tool_names']}", flush=True)


if __name__ == "__main__":
    main()
