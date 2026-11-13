"""Rebuild the Overview score chart in gemma-agent-score-record.html from Outputs/_submissions.json, with points placed
by REAL submission time (the hand-made version spaced them evenly by order). Main track (31B) scored rows only.
Re-run after new submissions: python Write-up/_rebuild_score_svg.py"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "Write-up" / "gemma-agent-score-record.html"
subs = json.load(open(ROOT / "Outputs" / "_submissions.json", encoding="utf-8"))
pts = []
for s in subs:
    # E4B rows: kernel url names e4b, or the description STARTS with E4B (raw-file urls). A 31B description may merely
    # mention E4B (58263186 "...; E4B locate test not ready"), so "e4b anywhere in desc" wrongly dropped it.
    desc, url = (s.get("desc") or "").lower(), (s.get("url") or "").lower()
    if s.get("score") in (None, "") or "e4b" in url or desc.startswith("e4b"):
        continue
    pts.append((datetime.fromisoformat(s["date"][:19]), float(s["score"])))
pts.sort()
X0, X1, Y0 = 36.0, 728.0, 216.0           # same frame as the original chart
t0 = pts[0][0].replace(hour=0, minute=0, second=0)
t1 = (pts[-1][0] + timedelta(days=1)).replace(hour=0, minute=0, second=0)
span = (t1 - t0).total_seconds()
x = lambda d: X0 + (X1 - X0) * (d - t0).total_seconds() / span
y = lambda v: Y0 - 588.0 * v               # original scale: 0.10 -> 157.2, 0.25 -> 68.9
P = [(x(d), y(v)) for d, v in pts]
poly = " ".join(f"{a:.1f},{b:.1f}" for a, b in P)
circles = "".join(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="2.5"/>' for a, b in P)
ticks, d = [], t0
while d <= t1:
    if d.weekday() == 0 or d == t0:        # Mondays + first day
        ticks.append(f'<text x="{x(d):.0f}" y="236">{d:%m-%d}</text><line x1="{x(d):.1f}" y1="216" x2="{x(d):.1f}" y2="220" stroke="#a8a29e"/>')
    d += timedelta(days=1)
svg = f'''<svg viewBox="0 0 760 248" role="img" aria-label="Displayed public score by date, main track, {pts[0][0]:%B %d} to {pts[-1][0]:%B %d} %Y">
      <line x1="36" y1="16" x2="36" y2="216" stroke="#e7e5e4"/>
      <line x1="36" y1="216" x2="736" y2="216" stroke="#e7e5e4"/>
      <line x1="36" y1="68.9" x2="736" y2="68.9" stroke="#9a3412" stroke-dasharray="4 3"/>
      <line x1="36" y1="45.4" x2="736" y2="45.4" stroke="#166534" stroke-dasharray="4 3"/>
      <text class="axis" x="740" y="72">0.25</text>
      <text class="axis" x="740" y="48">0.29</text>
      <text class="axis" x="4" y="220">0</text>
      <text class="axis" x="4" y="161">0.10</text>
      <text class="axis" x="4" y="102">0.20</text>
      <polyline fill="none" stroke="#1d4ed8" stroke-width="2" points="{poly}"/>
      <g fill="#1d4ed8">{circles}</g>
      <g class="axis">{"".join(ticks)}</g>
    </svg>'''.replace("%Y", f"{pts[-1][0]:%Y}")
html = HTML.read_text(encoding="utf-8")
new, n = re.subn(r'<svg viewBox="0 0 760 248".*?</svg>', lambda _: svg, html, count=1, flags=re.S)
assert n == 1, "score chart <svg> not found"
HTML.write_text(new, encoding="utf-8", newline="")
print(f"rebuilt chart: {len(pts)} main-track points, {pts[0][0]:%m-%d} .. {pts[-1][0]:%m-%d}, {len(ticks)} date ticks (Mondays)")
