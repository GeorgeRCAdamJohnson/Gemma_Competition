"""How long are 31B model turns (logged text chars, ~4 chars/token)? If almost no turn needs > ~3,000 tokens,
max_output_tokens 5000 -> 3000 frees ~2k tokens of prompt room (vLLM reserves max_output from the 32,768 window)."""
import re
import tarfile
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
chars = []
with tarfile.open(Path("Outputs/ca5_31b_presubmit_85/results.tar.gz")) as tf:
    for m in tf.getmembers():
        if m.name.endswith(".log") and "/logs/" in m.name:
            t = A.sub("", tf.extractfile(m).read().decode("utf-8", "replace"))
            chars += [int(x) for x in re.findall(r"\((\d+) chars\)", t)]
chars.sort()
n = len(chars)
q = lambda p: chars[min(n - 1, int(p * n))]
print(f"{n} model turns | chars median {q(.5)}, p90 {q(.9)}, p99 {q(.99)}, max {chars[-1]}")
for tok in (2000, 3000, 4000):
    k = sum(c > tok * 4 for c in chars)
    print(f"  turns > ~{tok} tokens ({tok*4} chars): {k} ({100*k/n:.2f}%)")
