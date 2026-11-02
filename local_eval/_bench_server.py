import json, sys, time, threading, urllib.request

URL = "http://127.0.0.1:8081/completion"


def one(prompt, n_predict, out, key):
    body = {"prompt": prompt, "n_predict": n_predict, "temperature": 0.7, "top_k": 64,
            "cache_prompt": False, "stream": False, "ignore_eos": True}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    out[key] = (time.time() - t0, d.get("timings", {}))


def run(n_streams, prompt, n_predict):
    out = {}
    th = [threading.Thread(target=one, args=(prompt, n_predict, out, i)) for i in range(n_streams)]
    t0 = time.time()
    for t in th:
        t.start()
    for t in th:
        t.join()
    wall = time.time() - t0
    for i in sorted(out):
        el, tm = out[i]
        print(f"  stream {i}: wall {el:5.1f}s  prompt_n={tm.get('prompt_n')} prompt_tok/s={tm.get('prompt_per_second', 0):7.1f}"
              f"  predicted_n={tm.get('predicted_n')} decode_tok/s={tm.get('predicted_per_second', 0):6.1f}")
    print(f"  total wall {wall:.1f}s")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "short"
    n_pred = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    base = "The quick brown fox jumps over the lazy dog. " * (1 if mode == "short" else 400)
    for n in (1, 2, 3):
        print(f"[{mode}] {n} concurrent stream(s), n_predict={n_pred}, prompt chars={len(base)}")
        run(n, base, n_pred)
