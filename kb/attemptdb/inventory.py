"""Inventory of raw material for the deep intel DB: file kinds, counts and bytes across the repo (read-only), plus
candidate vLLM / server / notebook logs and training artifacts. usage: python kb/attemptdb/inventory.py"""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = re.compile(r"[\\/](\.git|node_modules|venv|\.venv|site-packages|__pycache__|upstream)[\\/]")
kind = defaultdict(lambda: [0, 0, []])


def classify(p):
    n, s = p.name.lower(), p.as_posix().lower()
    if n.startswith("trace_") and n.endswith(".json"):
        return "trace (ATIF)"
    if "/test_outputs/" in s:
        return "hidden-test output"
    if "/patches/" in s:
        return "agent patch"
    if "/logs/" in s and n.endswith(".log"):
        return "agent display log"
    if "vllm" in n or "server" in n and n.endswith((".log", ".txt")):
        return "vLLM/server log"
    if n.endswith((".log", ".txt")) and re.search(r"stdout|stderr|kernel|notebook|output|run|_ab|batch", n):
        return "run/kernel log"
    if n.endswith(".ipynb"):
        return "notebook"
    if n in ("registration.json", "kernel-metadata.json", "submission_receipt.json", "result_report.json"):
        return n
    if n in ("lora_progress.json", "progress.json", "variance_ab.json", "task_results.jsonl", "summary.json"):
        return n
    if n.endswith((".safetensors", ".bin")) or n == "adapter_config.json":
        return "adapter/weights"
    if re.search(r"train|trainer|loss|curriculum", n) and n.endswith((".json", ".jsonl", ".csv", ".log")):
        return "training artifact"
    if n.endswith((".tar", ".tar.gz", ".tgz", ".zip")):
        return "archive"
    return None


for p in ROOT.rglob("*"):
    if not p.is_file() or SKIP.search(str(p)):
        continue
    k = classify(p.relative_to(ROOT))
    if k:
        st = kind[k]
        st[0] += 1
        st[1] += p.stat().st_size
        if len(st[2]) < 3:
            st[2].append(p.relative_to(ROOT).as_posix())
for k, (n, b, ex) in sorted(kind.items(), key=lambda kv: -kv[1][1]):
    print(f"{k:24s} {n:7d} files {b / 1e6:9.1f} MB   e.g. {ex[0]}")
# where do vLLM lines appear? (engine/server log markers inside any .log/.txt <= 50 MB)
MARK = re.compile(rb"(Avg prompt throughput|GPU KV cache usage|INFO \d\d-\d\d \S+ \[engine|Maximum concurrency for|"
                  rb"KV cache size|prefix cache hit rate|vllm\.entrypoints)")
hits = defaultdict(int)
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix in (".log", ".txt", ".out") and not SKIP.search(str(p)) and p.stat().st_size < 50e6:
        try:
            if MARK.search(p.read_bytes()):
                hits[p.relative_to(ROOT).parts[0] + "/" + (p.relative_to(ROOT).parts[1] if len(p.relative_to(ROOT).parts) > 2 else "")] += 1
        except OSError:
            pass
print("\nfiles containing vLLM engine/server lines, by top dirs:")
for d, n in sorted(hits.items(), key=lambda kv: -kv[1])[:25]:
    print(f"  {n:5d}  {d}")
