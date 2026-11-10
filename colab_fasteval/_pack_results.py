# Runs ON the GPU VM: bundle the smoke artifacts for download (results incl. logs/traces, summary, run logs).
import tarfile
from pathlib import Path

out = Path("/content/smoke_results.tar.gz")
with tarfile.open(out, "w:gz") as t:
    for p in ("/content/work/results", "/content/work/smoke_summary.json", "/content/work/eval_stderr.txt",
              "/content/work/eval_stdout.txt", "/content/smoke.log", "/content/smoke_attempt_prev.log",
              "/content/prep.log"):
        if Path(p).exists():
            t.add(p, arcname=Path(p).name)
print(out, out.stat().st_size, "bytes")
