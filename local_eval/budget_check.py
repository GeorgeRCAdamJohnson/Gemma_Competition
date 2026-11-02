"""Was the per-turn thinking budget actually enforced?  For each ON trace, list turns by reasoning size.  CPU only.
python budget_check.py k_on1024 k_on1024_orf
"""
import json, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
for tag in sys.argv[1:]:
    rows = [json.loads(l) for l in open(HERE / "runs" / f"{tag}.trace.jsonl", encoding="utf-8")]
    turns = [e for e in rows if e.get("kind") == "turn"]
    print(f"\n== {tag}: {len(turns)} turns")
    big = sorted(turns, key=lambda e: -e["reasoning_chars"])[:8]
    print(f"{'task':10}{'turn':>5}{'finish':>11}{'ctok':>6}{'rs_chars':>9}{'content':>8}  chars/ctok")
    for e in big:
        print(f"{e['task']:10}{e['turn']:>5}{e['finish']:>11}{e['ctok']:>6}{e['reasoning_chars']:>9}{e['content_chars']:>8}  {e['reasoning_chars'] / max(1, e['ctok']):.2f}")
    over = [e for e in turns if e["reasoning_chars"] > 4200]
    print(f"turns with reasoning > 4200 chars (~1300+ tokens at ~3.2 chars/token): {len(over)}/{len(turns)}")
