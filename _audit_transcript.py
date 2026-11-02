"""Audit the exported transcript: how many assumptions/mistakes trace to log-retrieval failure?"""
import re
from pathlib import Path

T = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\SESSION_TRANSCRIPT_2026-11-01.md')
t = T.read_text(encoding='utf-8')

PATS = {
    'I was wrong': r"(?i)\bI was wrong\b",
    'retract*': r"(?i)\bretract",
    'you\'re right': r"(?i)you(?:'|\u2019)?re right|you are right",
    'my error/bug': r"(?i)\bmy (?:error|mistake|bug)\b",
    'I should have': r"(?i)\bI should have\b",
    'already tested/known': r"(?i)already (?:tested|in the log|recorded|established|known|exists)",
    'overclaim': r"(?i)overclaim",
    'that is false': r"(?i)\b(?:that is|that's) false\b|\bfalse claim",
    'correction/corrected': r"(?i)\bcorrection\b|\bcorrected\b",
    'null verdict': r"(?i)\bnull\b",
    'you corrected me': r"(?i)you corrected me|corrected me",
    'I overclaimed': r"(?i)I overclaimed",
}
print('=== marker counts across the 853-turn transcript ===')
for k, p in PATS.items():
    print('  %-26s %d' % (k, len(re.findall(p, t))))

# user messages that are themselves corrections
USER = re.compile(r'\n## USER  \[(.*?)\]\n\n(.*?)(?=\n### ASSISTANT|\n## USER|\Z)', re.S)
users = USER.findall(t)
print('\n=== user turns:', len(users), '===')
CORR = re.compile(r"(?i)\b(?:no|nope|wrong|already|didn't|did not|you just|not true|incorrect|"
                  r"that's not|we (?:already|tested)|I told you|check the (?:log|chema))")
corr = [(ts, body.strip()[:220]) for ts, body in users if CORR.search(body[:400])]
print('user turns that read as a correction:', len(corr))
for ts, s in corr[:60]:
    print('  [%s] %s' % (ts[:19], s.replace('\n', ' ')[:170]))
