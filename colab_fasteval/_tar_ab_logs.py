# Runs ON a CPU VM with Drive mounted: bundle the A/B task logs + task_results for the batches NOT yet pulled
# (batch 2 and the vote run), one tar per batch, in the background. Writes /content/<tag>.tar.gz and <tag>.done.
import subprocess
from pathlib import Path

R = "/content/drive/MyDrive/gemma_fasteval/ab_runs"
script = f"""
cd {R}
ls -la
for tag in e4b_ab2_20261111 e4b_ab4_vote_20261111 e4b_ab2b_20261111; do
  if [ -d "$tag" ]; then
    find "$tag" \\( -name '*.log' -path '*/logs/*' -o -name task_results.jsonl -o -name progress.json \\) -print0 \\
      | tar --null -czf /content/$tag.tar.gz -T - && echo "$tag $(ls -l /content/$tag.tar.gz | awk '{{print $5}}')" && touch /content/$tag.done
  else
    echo "$tag missing"
  fi
done
echo ALL > /content/tar2.done
"""
Path("/content/tar2.sh").write_text(script)
subprocess.Popen("nohup bash /content/tar2.sh > /content/tar2.log 2>&1 &", shell=True)
print("started")
