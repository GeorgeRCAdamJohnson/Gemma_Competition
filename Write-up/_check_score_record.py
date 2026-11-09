"""Sanity checks for gemma-agent-score-record.html: balanced tags, valid UTF-8, score chart points ordered by date,
and the corrected passages present. python Write-up/_check_score_record.py"""
import re
from html.parser import HTMLParser
from pathlib import Path

t = (Path(__file__).parent / "gemma-agent-score-record.html").read_bytes().decode("utf-8")
VOID = {"meta", "input", "br", "img", "line", "circle", "polyline", "hr", "link"}


class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.st = []; self.err = []

    def handle_starttag(self, tag, a):
        if tag not in VOID:
            self.st.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.st and self.st[-1] == tag:
            self.st.pop()
        else:
            self.err.append((tag, self.getpos()))


p = P(); p.feed(t)
print("unclosed:", p.st, "| mismatches:", p.err[:5])
svg = re.search(r'<svg viewBox="0 0 760 248".*?</svg>', t, re.S).group(0)
xs = [float(v) for v in re.findall(r'<circle cx="([0-9.]+)"', svg)]
print("points", len(xs), "| x", min(xs), "->", max(xs), "| ordered", xs == sorted(xs),
      "| date ticks", svg.count("<text x="))
for k in ("no score", "true by construction", "24 of 7,424", "Points are placed by submission time"):
    print(f"  {k!r}: {k in t}")
