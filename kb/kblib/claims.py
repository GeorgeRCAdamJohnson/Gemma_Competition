"""Log claim extraction, auto-checks, supersession and curated merge
(design §12.1-§12.7 + REVISION 5 R5.7; version cl-4).

Pipeline (explicit regex patterns only, no NLP):
1. segment(): `##`/`###` heading blocks -> level-2 / level-3 units (dates,
   versions, tasks, levers, kind, correction_unit).
2. claim units (§12.3): READ-THIS-FIRST items, recognised table rows (types
   A/B/C incl. TOTAL rows), lexicon paragraphs (<=12-line chunks), heading
   blocks, and rule-5 fact-lines.
3. facts (§12.4): F1 (bar/unit/keyed classifier), F1v, F2, F2b, F3/F3t, F4, F5
   (keyword / `<v> @ 0.NN` / `= 0.NN (k/58)` / `0.NN public`; `ref NNNNNNNN`
   binds to that exact submission), F6, F9, F10 (live-best / NEW PERSONAL BEST /
   BOARD BEST).
4. checks: F5 against the LB source rows; F10 against the curated baseline;
   resolve/config facts against the bound run(s), per track (ambiguous binding
   -> UNVERIFIED, never forced).
5. supersession (§12.7 + R5.7): cited lines, `[RETRACTED ...]` /
   `[CLAIM ... WRONG ...]` heading tags, `CORRECTION/RETRACTION ... ABOVE`;
   chains (unit ids oldest -> newest) and superseded_by on every claim.
6. curated merge (read-only; curated claims are listed with their evidence).

Deterministic: every list is sorted or in log order; no wall clock.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re

CL_VERSION = "cl-4"

# ------------------------------------------------------------------ lexicon (§12.1)

CORRECTION_RX = re.compile(
    r"(?i:\b(?:retract\w*|correct(?:ed|ion|ions)|supersed\w*|falsif\w*|invalidat\w*"
    r"|overturn\w*|not reproducible|revised (?:stance|verdict))\b)"
    r"|(?<![.\w])CRITICAL\b")
VERDICT_RX = re.compile(
    r"\b(?:VERDICT|Verdict|RESULT|CONFIRMED|ROOT CAUSE|DECISIVE|CLOSED|EXHAUSTED|REGRESSION"
    r"|NULL|FAIL(?:ED)?|PASS(?:ED)?|INVALID|STANDING|NEGATIVE|POSITIVE|(?:NOT )?PROMOTED"
    r"|DEAD END|DEAD|FORENSICS|SOLVED)\b")
TASK_RX = re.compile(r"\b(?:rich|fastapi|requests|httpx)_\d+\b")
DATE_RX = re.compile(r"20\d\d-\d\d-\d\d")
_RETRACT_TAG = re.compile(r"\[\s*(?:RETRACTED\b|CLAIM\b[^\]]*\bWRONG\b)[^\]]*\]?", re.I)
_ABOVE = re.compile(r"(?i)^.{0,80}?\b(?:correct\w*|retract\w*)\b.{0,120}?\babove\b")
_CITE = re.compile(r"(?<![A-Za-z0-9])(?:L(\d{2,5})(?![\d])|line ~?(\d{2,5})\b|§~(\d{2,5})\b)")

# ------------------------------------------------------------- version tokens (§12.2)

_MODEL_TRACK = {"31b": "main", "e4b": "small-model", "e2b": "small-model", "12b": "dev-proxy"}
_MODEL_RX = re.compile(r"(?i)(?<![A-Za-z0-9])(31B|12B|E4B|E2B)(?![A-Za-z0-9])")
_TOKEN_RXS = (
    ("v", re.compile(
        r"(?<![A-Za-z0-9_])v\d+(?:[a-z]+\d*)?"
        r"(?:[-_](?:v\d+[a-z]*|(?i:lora)(?:[-_ ]v\d+)?|(?i:rich|cpu)|on[-_]v\d+\w*)"
        r"|[ ](?i:lora(?:[-_ ]v\d+)?|rich|cpu)(?![A-Za-z0-9_]))?(?![A-Za-z0-9])")),
    ("ca", re.compile(r"(?i)(?<![A-Za-z0-9_])ca\d+(?:[-_][A-Za-z0-9]+)?(?![A-Za-z0-9])")),
    ("named", re.compile(r"(?i)(?<![A-Za-z0-9_])(?:off12|b12|branch[_ -]final)(?![A-Za-z0-9])")),
    ("A", re.compile(r"(?<![A-Za-z0-9_])A\d{1,2}(?![A-Za-z0-9])(?!-\d)")),
    ("D", re.compile(r"(?<![A-Za-z0-9_])D\d(?![A-Za-z0-9])(?!-\d)")),
    ("E", re.compile(r"(?<![A-Za-z0-9_])E\d(?![A-Za-z0-9])(?!-\d)")),
    ("P", re.compile(r"(?<![A-Za-z0-9_])P\d(?![A-Za-z0-9])(?!-\d)")),
    ("model", _MODEL_RX),
)
_MODEL_AFTER = re.compile(r"^\s?@?\s?-?(31B|12B|E4B|E2B)(?![A-Za-z0-9])", re.I)
_MODEL_BEFORE = re.compile(r"(31B|12B|E4B|E2B)[\s-]$", re.I)

# Builtin alias table (§12.2; curated run_labels.json `aliases` extend it).
BUILTIN_ALIASES = {
    "arm a": "v6z_on_v6w-arma",
    "arm b": "v6z_on_v6w-armb",
    "arm c": "v6z_on_v6w-armc",
    "branch final": "branch_final",
    "compact5": "v6z_on_v6w-compact5",
    "maxout16k": "v6z_on_v6w-maxout16k",
    "lora025": "v6z_on_v6w-lora025",
    "ser a": "v6z_on_v6w-sera",
    "ser b": "v6z_on_v6w-serb",
}


def canon(s):
    return re.sub(r"[ _-]+", "-", (s or "").strip().lower())


class Tokenizer:
    """Two passes (§12.2): aliases on the raw text (longest first), then the
    version regexes on what pass 1 left. Model tokens are qualifiers."""

    def __init__(self, run_labels=(), curated_aliases=None):
        amap = {}
        for k, v in BUILTIN_ALIASES.items():
            amap[canon(k)] = canon(v)
        for k, v in (curated_aliases or {}).items():
            amap[canon(k)] = canon(v)
        for lab in sorted(set(l for l in run_labels if l)):
            if self._distinctive(lab):
                amap.setdefault(canon(lab), canon(lab))
        self.alias_map = amap
        keys = sorted(amap, key=lambda k: (-len(k), k))
        alts = []
        for k in keys:
            parts = [re.escape(p) for p in k.split("-") if p]
            alts.append(r"[ _-]?".join(parts))
        self.alias_rx = (re.compile(r"(?i)(?<![A-Za-z0-9_])(?:" + "|".join(alts)
                                    + r")(?![A-Za-z0-9])") if alts else None)

    @staticmethod
    def _distinctive(label):
        if label.startswith("-") or len(label) < 4 or not re.search(r"[\d_-]", label):
            return False
        toks = _regex_tokens(label)
        if len(toks) == 1 and toks[0]["canon"] == canon(label) \
                and toks[0]["end"] - toks[0]["start"] == len(label):
            return False
        return True

    def tokens(self, text):
        out = []
        masked = text
        if self.alias_rx is not None:
            for m in self.alias_rx.finditer(text):
                key = canon(m.group(0))
                lab = self.alias_map.get(key)
                if lab is None:
                    # separators were optional: match by compact form
                    comp = re.sub(r"[ _-]", "", key)
                    for k, v in self.alias_map.items():
                        if re.sub(r"-", "", k) == comp:
                            lab = v
                            break
                if lab is None:
                    continue
                out.append({"start": m.start(), "end": m.end(), "canon": lab,
                            "kind": "alias", "model": None})
                masked = masked[:m.start()] + " " * (m.end() - m.start()) + masked[m.end():]
        out += _regex_tokens(masked)
        out.sort(key=lambda t: (t["start"], t["end"]))
        for t in out:
            if t["kind"] == "model" or t["model"]:
                continue
            ma = _MODEL_AFTER.match(text[t["end"]:t["end"] + 7])
            mb = _MODEL_BEFORE.search(text[max(0, t["start"] - 5):t["start"]])
            if ma:
                t["model"] = ma.group(1).lower()
            elif mb:
                t["model"] = mb.group(1).lower()
        return out


def _regex_tokens(text):
    out = []
    masked = text
    for kind, rx in _TOKEN_RXS:
        for m in rx.finditer(masked):
            raw = m.group(0)
            model = None
            c = canon(raw)
            if kind == "ca":
                base, _, suf = c.partition("-")
                if suf in _MODEL_TRACK:
                    c, model = base, suf
            elif kind == "model":
                model = c
            elif kind == "named":
                c = c.replace("branch-final", "branch-final")
            out.append({"start": m.start(), "end": m.end(), "canon": c, "kind": kind,
                        "model": model})
        masked = rx.sub(lambda m: " " * len(m.group(0)), masked)
    return out


def _vers(tokens):
    """Non-model version canons in order (deduplicated)."""
    seen, out = set(), []
    for t in tokens:
        if t["kind"] == "model":
            continue
        if t["canon"] not in seen:
            seen.add(t["canon"])
            out.append(t["canon"])
    return out


def _models(tokens):
    return sorted({t["model"] for t in tokens if t.get("model")})


# --------------------------------------------------------------- segmentation (§12.1)

def _level(ln):
    if ln.startswith("### "):
        return 3
    if ln.startswith("## "):
        return 2
    return 0


def _norm(s):
    return " ".join((s or "").split()).lower()


def _norm_heading(s):
    s = re.sub(r"Updated 20\d\d-\d\d-\d\d\.?", "", s or "")
    s = DATE_RX.sub("", s)
    s = re.sub(r"[^\x20-\x7e]", "", s)
    return _norm(s).rstrip(" .:;,-")


def _fences(lines):
    out, inside = [], False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            out.append(True)
            inside = not inside
            continue
        out.append(inside)
    return out


def segment(log_text, tokenizer=None, lever_fn=None):
    """Units in log order: dicts with id, level, start, end, heading,
    heading_block, heading_lines, parent, entry_heading, date..., versions,
    tasks, levers, kind, correction_unit, own_lines [(a, b)]."""
    tok = tokenizer or Tokenizer()
    lines = [ln.rstrip("\r") for ln in log_text.split("\n")]   # the log mixes CRLF lines
    n = len(lines)
    fence = _fences(lines)
    blocks = []
    i = 0
    while i < n:
        lv = 0 if fence[i] else _level(lines[i])
        if lv:
            j = i
            while j + 1 < n and not fence[j + 1] and _level(lines[j + 1]) == lv:
                j += 1
            blocks.append((lv, i + 1, j + 1))
            i = j + 1
        else:
            i += 1
    units = []
    cur2 = None
    for bi, (lv, a, b) in enumerate(blocks):
        hb = " ".join(lines[k - 1][lv + 1:].strip() for k in range(a, b + 1))
        nxt_any = blocks[bi + 1][1] - 1 if bi + 1 < len(blocks) else n
        nxt2 = n
        for lv2, a2, _ in blocks[bi + 1:]:
            if lv2 == 2:
                nxt2 = a2 - 1
                break
        end = nxt2 if lv == 2 else min(nxt2, nxt_any)
        u = {"level": lv, "start": a, "heading_end": b, "end": end,
             "heading": lines[a - 1][lv + 1:].strip(), "heading_block": hb,
             "heading_lines": b - a + 1}
        if lv == 2:
            cur2 = u
            u["parent"] = None
            u["entry_heading"] = hb
        else:
            if cur2 is None:
                continue
            u["parent"] = cur2
            u["entry_heading"] = cur2["heading_block"] + " \u203a " + hb
        units.append(u)
    # own line ranges: lines not inside a deeper unit
    for idx, u in enumerate(units):
        own_end = u["end"]
        if u["level"] == 2:
            for v in units[idx + 1:]:
                if v["level"] == 2:
                    break
                own_end = v["start"] - 1
                break
        u["own"] = (u["heading_end"] + 1, own_end)
    # ids (collision suffixes in log order)
    seen = {}
    for u in units:
        base = "U-" + hashlib.sha1(_norm(u["heading_block"]).encode("utf-8")).hexdigest()[:10]
        k = seen.get(base, 0) + 1
        seen[base] = k
        u["id"] = base if k == 1 else f"{base}-{k}"
    # per-unit attributes
    prev_date = None
    dates = []
    for u in units:
        body_first = [lines[k - 1] for k in range(u["heading_end"] + 1,
                                                    min(u["end"], u["heading_end"] + 5) + 1)]
        m = DATE_RX.search(u["heading_block"]) or DATE_RX.search("\n".join(body_first))
        dates.append(m.group(0) if m else None)
    for idx, u in enumerate(units):
        d = dates[idx]
        u["date_raw"] = d
        u["date_suspect"] = False
        if d is not None:
            later = [x for x in dates[idx + 1: idx + 21] if x]
            if d < "2026-09-01" or (later and d > max(later) and prev_date
                                    and d > _add_days(prev_date, 7)):
                u["date_suspect"] = True
                d = prev_date
        else:
            d = prev_date
        u["date"] = d
        if not u["date_suspect"] and u["date_raw"]:
            prev_date = u["date_raw"]
        body = "\n".join(lines[k - 1] for k in range(u["start"], u["end"] + 1)
                         if not fence[k - 1])
        toks = tok.tokens(u["heading_block"]) + tok.tokens(body)
        u["head_tokens"] = tok.tokens(u["heading_block"])
        u["versions"] = sorted(set(_vers(toks)))
        u["first_version"] = (_vers(u["head_tokens"]) or _vers(tok.tokens(body)) or [None])[0]
        u["models"] = _models(toks)
        u["tasks"] = sorted(set(TASK_RX.findall(u["heading_block"] + "\n" + body)))
        u["levers"] = lever_fn(u["heading_block"] + "\n" + body) if lever_fn else []
        hb = u["heading_block"]
        if u["level"] == 2:
            if "READ THIS FIRST" in hb:
                kind = "read-this-first"
            elif "CONSOLIDATED VERSION HISTORY" in hb:
                kind = "version-history"
            elif VERDICT_RX.search(hb) or CORRECTION_RX.search(hb):
                kind = "verdict"
            else:
                kind = "other"
        else:
            if VERDICT_RX.search(hb) or CORRECTION_RX.search(hb):
                kind = "verdict"
            else:
                kind = u["parent"]["kind"] if u["parent"]["kind"] == "verdict" else "other"
        u["kind"] = kind
        first_para = []
        for k in range(u["heading_end"] + 1, u["end"] + 1):
            ln = lines[k - 1]
            if not ln.strip():
                if first_para:
                    break
                continue
            first_para.append(ln)
            if len(first_para) >= 12:
                break
        u["correction_unit"] = bool(CORRECTION_RX.search(hb)
                                    or CORRECTION_RX.search(" ".join(first_para)))
        u["self_retracted"] = bool(_RETRACT_TAG.search(hb))
    return units, lines, fence


def _add_days(d, n):
    import datetime
    try:
        x = datetime.date.fromisoformat(d) + datetime.timedelta(days=n)
        return x.isoformat()
    except ValueError:
        return d


# ------------------------------------------------------------------- facts (§12.4)

_CHAIN = re.compile(r"(?<!\d)(?<!\d\.)\d+(?:/\d+)+(?!\d|\.\d)")
_BAR_BEFORE = re.compile(
    r"(?i)(?:>=|<=|>|<|\u2265|\u2264|at least|\bbar\b|\btarget\b|\bneed\w*|\bexpect\w*|\bideally"
    r"|\bshould\b|\bwould\b|\bmust\b)")
_UNIT_AFTER = re.compile(
    r"(?i)^\W{0,3}?(?:calls?\b|c\b|patch(?:es)?\b|banked\b|edits?\b|chars?\b|ch\b|tests?\b"
    r"|files?\b|hunks?\b|turns?\b|lines?\b|min\b)")
_RESOLVE_KW = re.compile(r"(?i)^(?:resolv\w*|scored?|dev)$")
_TASK_GROUP = re.compile(
    r"\(\s*((?:rich|fastapi|requests|httpx)_\d+(?:\s*(?:\+|,|&|\band\b)?\s*"
    r"(?:rich|fastapi|requests|httpx)_\d+)*)\s*\)")
_F2_PAREN = re.compile(r"\(([^()]*)\)")
_F2_TF = re.compile(r"\b((?:rich|fastapi|requests|httpx)_\d+)\s+(T|F|True|False)\b")
_F2_EQ = re.compile(r"\b((?:rich|fastapi|requests|httpx)_\d+)\b[^\n]{0,40}?\bresolved\s*=\s*(True|False)\b")
_F3_KV = re.compile(r"\b(calls|chars|dur)\s*=\s*(\d+(?:\.\d+)?)")
_F5_KW = re.compile(
    r"(?i:\bLB\b|leaderboard|\bpublic(?: score)?\b|\bscor(?:e|ed|es)\b)[^\d\n]{0,30}?"
    r"(~?)(0\.\d{2,3})(-ish)?(?![\d])(?!\s*budget)(?!-?recipe)")
_F5_POST = re.compile(r"(~?)(0\.\d{2,3})(-ish)?\s*(?:public\b|LB\b|on the (?:LB|board)\b|leaderboard\b)")
_F5_K58 = re.compile(r"=\s*(~?)(0\.\d{2,3})\s*\((\d+)/58\)")
_F5_AT = re.compile(r"^\s*@\s*(~?)(0\.\d{2,3})(-ish)?(?![\d])")
_REF = re.compile(r"(?i)\b(?:ref|submission)\s*#?\s*(\d{8})\b")
_F10 = re.compile(
    r"(?i)(?:live[- ]best\s*(?:=|:|is)\s*|new live[- ]best|is now the live[- ]best|no longer sacred"
    r"|new personal best|board best)")
_F4 = (
    ("thinking_budget", re.compile(r"(?i)\bthinking(?:[_ ]budget)?\s*[=:]?\s*(\d{3,5})\b")),
    ("max_tool_calls", re.compile(r"(?i)\bmax_tool_calls\s*[=:]?\s*(\d+)\b")),
    ("temperature", re.compile(r"(?i)\btemp(?:erature)?\s*[=:]?\s*([01](?:\.\d+)?)\b")),
    ("top_k", re.compile(r"(?i)\btop_k\s*[=:]?\s*(\d+)\b")),
    ("max_output_tokens", re.compile(r"(?i)\bmax_out\w*\s*[=:]?\s*(\d{3,6})\b")),
)
_QUAD = re.compile(r"(?<![\d/.])(\d{1,3})/(\d{1,3})/(\d{1,4})/(\d{2,4})(?![\d/])")
_QUAD_KEYS = ("max_tool_calls", "max_time_minutes", "max_turns", "timeout_seconds")
_F6 = re.compile(r"(?i)\b(n_edit|edit_fail|first_edit_at)\s*=\s*(\d+)|\b(never edited|0 edits)\b"
                 r"|\bnot ONE\b[^.]{0,40}\bedit")
_F9 = re.compile(r"(?i)\b(?:distinct fixes|resolves) EVER\s*=\s*(\d+)")
_SENT = re.compile(r"(?<=[.;!?])\s+")
_QUOTE = re.compile(r"\"[^\"\n]{4,300}\"|\u201c[^\u201d\n]{4,300}\u201d")
# Expectation / bar context: a score or resolve stated as a target, projection
# or pre-registered bar is recorded as `bar`, never checked as an outcome.
_BAR_CTX = re.compile(
    r"(?i)(?:>=|<=|>|<|\u2265|\u2264|\bat least\b|\bshould\b|\bwould\b|\bcould\b|\bexpect\w*"
    r"|\btarget\w*\b|\bneed\w*|\bbar\b|\bprojected?\b|\bestimat\w*|\bmust\b|\bflips? to\b"
    r"|\bpre-?regist\w*|\bif\b|\bto beat\b|\bbeat\b)")
CHECK_FIELDS = ("F1", "F1v", "F2", "F2b", "F3", "F3t", "F4", "F5", "F6", "F9", "F10")
FACTLINE_FIELDS = ("F1", "F1v", "F2", "F2b", "F3", "F5", "F10")


def _clean(text):
    return text.replace("**", "").replace("`", "")


def _sent_spans(text):
    spans, a = [], 0
    for m in _SENT.finditer(text):
        spans.append((a, m.start()))
        a = m.end()
    spans.append((a, len(text)))
    return spans


def _sent_of(spans, pos):
    for a, b in spans:
        if a <= pos <= b:
            return a, b
    return spans[-1]


def _nearest_before(tokens, pos, lo):
    best = None
    for t in tokens:
        if t["kind"] == "model":
            continue
        if lo <= t["start"] and t["end"] <= pos:
            best = t
    return best


def _nearest_any(tokens, pos, lo, hi):
    best, bd = None, None
    for t in tokens:
        if t["kind"] == "model" or t["start"] < lo or t["end"] > hi:
            continue
        d = pos - t["end"] if t["end"] <= pos else t["start"] - pos
        if bd is None or d < bd:
            best, bd = t, d
    return best


def _f1_class(text, s, e):
    """bar / unit / keyed / unkeyed for an N/M at text[s:e] (D3-2)."""
    before = text[max(0, s - 12):s].replace("*", "")
    if _BAR_BEFORE.search(before):
        return "bar"
    if _UNIT_AFTER.match(text[e:e + 12]):
        return "unit"
    words_before = re.findall(r"[A-Za-z_]+", text[max(0, s - 40):s])[-3:]
    m_after = re.match(r"\W*([A-Za-z_]+)", text[e:e + 20])
    if any(_RESOLVE_KW.match(w) for w in words_before) or \
            (m_after and _RESOLVE_KW.match(m_after.group(1))):
        return "keyed"
    if re.match(r"\s*" + _TASK_GROUP.pattern, text[e:]):
        return "keyed"
    return "unkeyed"


def _mk(field, value, line, **kw):
    f = {"field": field, "value": value, "line": line}
    for k, v in kw.items():
        if v is not None:
            f[k] = v
    return f


def line_facts(raw, line_no, tok, task_ctx=None):
    """Free-text facts on one prose line / cell. Each fact gets `version` by
    attribution rule 2 (nearest token before in the same sentence) when one
    exists; rules 3/4 are applied by the claim."""
    text = _clean(raw)
    tokens = tok.tokens(text)
    spans = _sent_spans(text)
    facts = []

    def bind(pos):
        a, _ = _sent_of(spans, pos)
        t = _nearest_before(tokens, pos, a)
        return t

    def put(field, value, pos, t, **kw):
        ver = t["canon"] if t else None
        model = t.get("model") if t else None
        facts.append(_mk(field, value, line_no, version=ver, model=model,
                         binding=("rule2-nearest-before" if t else None), pos=pos, **kw))

    # F1v: <token> = N/M
    f1v_spans = []
    for t in tokens:
        if t["kind"] == "model":
            continue
        m = re.match(r"\s*=\s*(\d+)/(\d+)\b", text[t["end"]:])
        if m:
            n_, m_ = int(m.group(1)), int(m.group(2))
            if 0 < m_ <= 200 and n_ <= m_:
                s = t["end"] + m.start(1)
                f1v_spans.append((s, t["end"] + m.end(2)))
                # `metric 2/5 (v19=0/5, ...)`: the F1v restates the preceding
                # N/M's metric; it is a resolve count only if that one is.
                pm = re.search(r"(\d+)/(\d+)\s*\(\s*$", text[max(0, t["start"] - 30):t["start"]])
                if pm:
                    ps = max(0, t["start"] - 30) + pm.start()
                    pcls = _f1_class(text, ps, ps + len(pm.group(1)) + 1 + len(pm.group(2)))
                    if pcls != "keyed":
                        facts.append(_mk("unkeyed", f"{n_}/{m_}", line_no, pos=s,
                                         note=f"F1v restating a {pcls} N/M"))
                        continue
                facts.append(_mk("F1v", f"{n_}/{m_}", line_no, version=t["canon"],
                                 model=t.get("model"), binding="rule-F1v-token", pos=s))
    # F1 with the classifier
    f1_by_end = {}
    for m in _CHAIN.finditer(text):
        if m.group(0).count("/") != 1:
            continue
        s, e = m.start(), m.end()
        if any(a <= s < b for a, b in f1v_spans):
            continue
        n_, m_ = (int(x) for x in m.group(0).split("/"))
        if m_ == 0 or m_ > 200 or n_ > m_:
            continue
        cls = _f1_class(text, s, e)
        if cls == "unit":
            continue
        if cls in ("bar", "unkeyed"):
            facts.append(_mk(cls, f"{n_}/{m_}", line_no, pos=s))
            continue
        t = bind(s)
        put("F1", f"{n_}/{m_}", s, t)
        f1_by_end[e] = facts[-1]
    # F2b: task group in parens on a line with an F1
    f1s = [f for f in facts if f["field"] in ("F1", "F1v")]
    if f1s:
        for m in _TASK_GROUP.finditer(text):
            tasks = sorted(set(TASK_RX.findall(m.group(1))))
            prev = [f for f in f1s if f["pos"] < m.start()]
            base = prev[-1] if prev else f1s[0]
            facts.append(_mk("F2b", tasks, line_no, version=base.get("version"),
                             model=base.get("model"), binding=base.get("binding"),
                             pos=m.start(), with_f1=base["value"]))
    # F2
    for m in _F2_PAREN.finditer(text):
        for mm in _F2_TF.finditer(m.group(1)):
            t = bind(m.start())
            put("F2", mm.group(2) in ("T", "True"), m.start(), t, task=mm.group(1))
    for m in _F2_EQ.finditer(text):
        if _BAR_CTX.search(text[max(0, m.start() - 30):m.end()]):
            facts.append(_mk("bar", f"{m.group(1)} resolved={m.group(2)}", line_no, pos=m.start()))
            continue
        t = bind(m.start())
        put("F2", m.group(2) == "True", m.start(), t, task=m.group(1))
    # F3 key=value with a task on the line
    tasks_on = [(m.start(), m.group(0)) for m in TASK_RX.finditer(text)]
    for m in _F3_KV.finditer(text):
        tk = [x for x in tasks_on if x[0] < m.start()] or ([(0, task_ctx)] if task_ctx else [])
        if not tk or not tk[-1][1]:
            continue
        fld = {"calls": "tool_calls", "chars": "patch_chars", "dur": "duration_s"}[m.group(1)]
        val = float(m.group(2)) if fld == "duration_s" else int(float(m.group(2)))
        put("F3", val, m.start(), bind(m.start()), task=tk[-1][1], column=fld)
    # F4 config facts
    for fld, rx in _F4:
        for m in rx.finditer(text):
            v = float(m.group(1)) if fld == "temperature" else int(m.group(1))
            put("F4", v, m.start(), bind(m.start()), column=fld)
    if re.search(r"(?i)\b(?:budget|eval)\b", text):
        for m in _QUAD.finditer(text):
            for k, v in zip(_QUAD_KEYS, m.groups()):
                put("F4", int(v), m.start(), bind(m.start()), column=k)
    # F5
    refs = [(m.start(), m.group(1)) for m in _REF.finditer(text)]
    seen5 = set()

    def put5(m_tilde, val, ish, pos, t, how, extra=None):
        if pos in seen5:
            return
        seen5.add(pos)
        a, b = _sent_of(spans, pos)
        ref = None
        if how != "idiom-@":          # `<v> @ 0.NN` names its own version
            inside = [(abs(rp - pos), r) for rp, r in refs if a <= rp <= b]
            if inside:
                ref = sorted(inside)[0][1]
        facts.append(_mk("F5", val, line_no, version=t["canon"] if t else None,
                         model=t.get("model") if t else None,
                         binding=(how if t else None), pos=pos,
                         approx=(True if (m_tilde or ish) else None), ref=ref, note=extra))

    for t in tokens:
        if t["kind"] == "model":
            continue
        m = _F5_AT.match(text[t["end"]:])
        if m:
            put5(m.group(1), m.group(2), m.group(3), t["end"] + m.start(2), t, "idiom-@")
    for m in _F5_KW.finditer(text):
        if _BAR_CTX.search(text[max(0, m.start() - 20):m.start(2)]):
            facts.append(_mk("bar", m.group(2), line_no, pos=m.start(2), note="score as bar"))
            continue
        put5(m.group(1), m.group(2), m.group(3), m.start(2), bind(m.start(2)),
             "rule2-nearest-before")
    for m in _F5_POST.finditer(text):
        if _BAR_CTX.search(text[max(0, m.start() - 20):m.start(2)]):
            facts.append(_mk("bar", m.group(2), line_no, pos=m.start(2), note="score as bar"))
            continue
        put5(m.group(1), m.group(2), m.group(3), m.start(2), bind(m.start(2)),
             "rule2-nearest-before")
    for m in _F5_K58.finditer(text):
        put5(m.group(1), m.group(2), None, m.start(2), bind(m.start(2)),
             "rule2-nearest-before", extra=f"k={m.group(3)}/58")
    # F6
    for m in _F6.finditer(text):
        if m.group(1):
            put("F6", int(m.group(2)), m.start(), bind(m.start()), column=m.group(1),
                task=([x for x in tasks_on if x[0] < m.start()] or [(0, task_ctx)])[-1][1])
        else:
            put("F6", m.group(0), m.start(), bind(m.start()), column="never-edited",
                task=([x for x in tasks_on if x[0] < m.start()] or [(0, task_ctx)])[-1][1])
    # F9
    for m in _F9.finditer(text):
        facts.append(_mk("F9", int(m.group(1)), line_no, pos=m.start()))
    # F10 (nearest token either side, same sentence)
    for m in _F10.finditer(text):
        a, b = _sent_of(spans, m.start())
        t = _nearest_any(tokens, m.start(), a, b)
        pol = "not-live-best" if "no longer sacred" in m.group(0).lower() else "live-best"
        facts.append(_mk("F10", pol, line_no, version=t["canon"] if t else None,
                         model=t.get("model") if t else None,
                         binding=("rule-F10-nearest" if t else None), pos=m.start(),
                         phrase=m.group(0).strip()))
    # text QUOTED inside a correction/retraction is the retracted statement, not
    # an assertion: flag its facts (they never check as outcomes)
    for m in _QUOTE.finditer(text):
        a, b = m.span()
        pre = text[max(0, a - 60):a]
        sa, sb = _sent_of(spans, a)
        if CORRECTION_RX.search(pre) or CORRECTION_RX.search(text[sa:a]):
            for f in facts:
                if a <= f["pos"] < b:
                    f["quoted"] = True
    lf = next((t for t in tokens if t["kind"] != "model"), None)
    if lf is not None:
        for f in facts:
            if f.get("version") is None:
                f["_line_first"] = (lf["canon"], lf.get("model"))
    facts.sort(key=lambda f: (f["pos"], f["field"]))
    return facts, tokens


# ------------------------------------------------------------------- tables (§12.4)

_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _hclean(c):
    return re.sub(r"\*\*|`", "", c).strip().lower()


_FIELD_COLS = {"resolved": "resolved", "dur": "duration_s", "dur_s": "duration_s",
               "duration": "duration_s", "calls": "tool_calls", "tool_calls": "tool_calls",
               "chars": "patch_chars", "patch_chars": "patch_chars"}


def table_type(header):
    h = [_hclean(c) for c in header]
    if not h:
        return None
    if h[0] == "date":
        return "C"
    if h[0] in ("ver", "version"):
        return "A"
    if h[0] in ("task", "id", "instance_id"):
        return "B"
    if any(x in ("score", "lb", "public") for x in h):
        return "C"
    return None


def cell_grammar(cell, line_no, version, task, column, binding):
    c = re.sub(r"(?<=\d),(?=\d{3}\b)", "", cell)
    c = re.sub(r"\*\*|`|\u00b7|\?|,", " ", c).strip()
    out = []

    def put(field, value, col):
        out.append(_mk(field, value, line_no, version=version, task=task,
                       column=col, binding=binding, cell=column))

    m = re.match(r"^(T|F|True|False)\s*/\s*(\d+)\s*(?:c|calls?)?\s*/\s*(\d+)\s*(?:ch|chars)?\b(.*)$",
                 c)
    rest = c
    if m:
        put("F2", m.group(1) in ("T", "True"), "resolved")
        put("F3", int(m.group(2)), "tool_calls")
        put("F3", int(m.group(3)), "patch_chars")
        rest = m.group(4)
    else:
        mr = re.match(r"^(T|F|True|False|TRUE|FALSE|RESOLVED?)\b", c)
        if mr:
            put("F2", mr.group(1) in ("T", "True", "TRUE", "RESOLVED", "RESOLVE"), "resolved")
        mc = re.search(r"(?<![\d.])(\d+)(?:/(\d+))?\s*(?:c|calls?)\b", c)
        if mc:
            put("F3", int(mc.group(1)), "tool_calls")
            if mc.group(2):
                put("F3t", int(mc.group(2)), "trace_calls")
        mh = re.search(r"(?<![\d.])(\d[\d]*)\s*(?:ch|chars)\b", c)
        if mh:
            put("F3", int(mh.group(1)), "patch_chars")
    md = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*s\b", rest)
    if md:
        put("F3", float(md.group(1)), "duration_s")
    return out


def _resolved_cell(cell):
    c = _hclean(cell)
    m = re.match(r"^(t|f|true|false|resolved?|yes|no)\b", c)
    if not m:
        return None
    return m.group(1) in ("t", "true", "resolved", "resolve", "yes")


def table_facts(header, rows, tok, unit_version, hints):
    """rows: [(line_no, cells)]. Returns [(line_no, row_text, facts, kind, row_tasks)]."""
    ttype = table_type(header)
    h = [_hclean(c) for c in header]
    out = []
    if ttype == "A":
        for ln, cells in rows:
            ver_toks = tok.tokens(_clean(cells[0])) if cells else []
            vs = _vers(ver_toks)
            ver = vs[0] if vs else None
            model = next((t["model"] for t in ver_toks if t.get("model")), None)
            facts = []
            for i, cell in enumerate(cells[1:], 1):
                hc = h[i] if i < len(h) else ""
                cc = _clean(cell)
                if hc in ("dev result", "result", "resolved"):
                    for m in _CHAIN.finditer(cc):
                        if m.group(0).count("/") == 1:
                            n_, m_ = (int(x) for x in m.group(0).split("/"))
                            if 0 < m_ <= 200 and n_ <= m_:
                                facts.append(_mk("F1", f"{n_}/{m_}", ln, version=ver,
                                                 model=model, binding="rule1-ver-column",
                                                 column=hc))
                            break
                elif hc in ("lb", "score"):
                    m = re.search(r"(~?)(0\.\d{2,3})(-ish)?", cc)
                    if m:
                        facts.append(_mk("F5", m.group(2), ln, version=ver, model=model,
                                         binding="rule1-ver-column", column=hc,
                                         approx=(True if (m.group(1) or m.group(3)) else None)))
                elif hc == "sample" or i == 0:
                    continue
                else:
                    fs, _ = line_facts(cell, ln, tok)
                    for f in fs:
                        if f["field"] in ("F1", "F2b"):
                            continue
                        if f.get("version") is None and f["field"] not in ("F9", "bar", "unkeyed"):
                            f["version"], f["model"] = ver, model
                            f["binding"] = "rule1-ver-column"
                        f["column"] = hc
                        facts.append(f)
            f1 = [f for f in facts if f["field"] == "F1"]
            row_text = " \u2502 ".join(cells)
            if f1:
                for m in _TASK_GROUP.finditer(_clean(row_text)):
                    facts.append(_mk("F2b", sorted(set(TASK_RX.findall(m.group(1)))), ln,
                                     version=ver, model=model, binding="rule1-ver-column",
                                     with_f1=f1[0]["value"]))
            out.append((ln, row_text, facts, "version-row", sorted(set(TASK_RX.findall(row_text)))))
        return out
    if ttype == "B":
        vcols = {}
        kinds = []
        for i, hc in enumerate(header):
            if i == 0:
                kinds.append("task")
                continue
            hcl = _hclean(hc)
            if hcl in _FIELD_COLS:
                kinds.append("field")
                continue
            vt = _vers(tok.tokens(_clean(hc)))
            if len(vt) == 1:
                kinds.append("version")
                vcols[i] = vt[0]
            else:
                kinds.append("free")
        dup = {v for v in vcols.values() if list(vcols.values()).count(v) > 1}
        for ln, cells in rows:
            first = _hclean(cells[0]) if cells else ""
            row_text = " \u2502 ".join(cells)
            facts = []
            if first in ("total", "sum"):
                for i, v in vcols.items():
                    if i < len(cells):
                        m = re.search(r"(\d+)/(\d+)", _clean(cells[i]))
                        if m and 0 < int(m.group(2)) <= 200 and int(m.group(1)) <= int(m.group(2)):
                            b = "ambiguous-duplicate-column" if v in dup else "rule1-version-column"
                            facts.append(_mk("F1", f"{m.group(1)}/{m.group(2)}", ln, version=v,
                                             binding=b, column=_clean(header[i]).strip()))
                out.append((ln, row_text, facts, "table-row", []))
                continue
            tm = TASK_RX.search(cells[0]) if cells else None
            if not tm:
                fs, _ = line_facts(row_text, ln, tok)
                out.append((ln, row_text, fs, "table-row", sorted(set(TASK_RX.findall(row_text)))))
                continue
            task = tm.group(0)
            for i, cell in enumerate(cells[1:], 1):
                if i >= len(kinds):
                    break
                k = kinds[i]
                if k == "field":
                    fld = _FIELD_COLS[_hclean(header[i])]
                    cc = _clean(cell)
                    if fld == "resolved":
                        v = _resolved_cell(cell)
                        if v is not None:
                            facts.append(_mk("F2", v, ln, version=unit_version, task=task,
                                             binding="rule4-unit", column="resolved"))
                    else:
                        m = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)", cc.replace(",", ""))
                        if m:
                            val = float(m.group(1)) if fld == "duration_s" else int(float(m.group(1)))
                            facts.append(_mk("F3", val, ln, version=unit_version, task=task,
                                             binding="rule4-unit", column=fld))
                elif k == "version":
                    v = vcols[i]
                    b = "ambiguous-duplicate-column" if v in dup else "rule1-version-column"
                    facts += cell_grammar(cell, ln, v, task, _clean(header[i]).strip(), b)
                else:
                    fs, _ = line_facts(cell, ln, tok, task_ctx=task)
                    for f in fs:
                        f["column"] = f.get("column") or _hclean(header[i])
                    facts += fs
            out.append((ln, row_text, facts, "table-row", sorted(set(TASK_RX.findall(row_text)))))
        return out
    if ttype == "C":
        cfg_i = next((i for i, x in enumerate(h) if x in ("config", "version", "description",
                                                          "submission", "change")), None)
        sc_i = [i for i, x in enumerate(h) if x in ("score", "lb", "public")]
        for ln, cells in rows:
            row_text = " \u2502 ".join(cells)
            facts = []
            ver, model = None, None
            if cfg_i is not None and cfg_i < len(cells):
                ctoks = tok.tokens(_clean(cells[cfg_i]))
                vs = _vers(ctoks)
                if len(vs) == 1:
                    ver = vs[0]
                    model = next((t["model"] for t in ctoks if t.get("model")), None)
                    for q in re.findall(r"\"([^\"]{3,80})\"", cells[cfg_i]):
                        hints.append({"text": q, "version": ver, "line": ln})
            for i in sc_i:
                if i < len(cells):
                    m = re.search(r"(~?)(0\.\d{2,3})(-ish)?", _clean(cells[i]))
                    if m:
                        facts.append(_mk("F5", m.group(2), ln, version=ver, model=model,
                                         binding=("rule1-config-cell" if ver else None),
                                         column=h[i],
                                         approx=(True if (m.group(1) or m.group(3)) else None)))
            for i, cell in enumerate(cells):
                if i in sc_i or (cfg_i is not None and i == cfg_i) or (h and i == 0 and h[0] == "date"):
                    continue
                fs, _ = line_facts(cell, ln, tok)
                facts += [f for f in fs if f["field"] != "F5"]
            out.append((ln, row_text, facts, "table-row", sorted(set(TASK_RX.findall(row_text)))))
        return out
    # unrecognised: rows as prose lines
    for ln, cells in rows:
        row_text = " \u2502 ".join(cells)
        fs, _ = line_facts(row_text, ln, tok)
        out.append((ln, row_text, fs, "table-row-free", sorted(set(TASK_RX.findall(row_text)))))
    return out


# --------------------------------------------------------------------- LB source

def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class LBIndex:
    def __init__(self, rows, tok, path=""):
        from . import attribution
        self.path = path
        self.subs = []
        for r in rows or []:
            desc = r.get("description", "") or ""
            toks = tok.tokens(desc)
            vs = _vers(toks)
            status = (r.get("status") or "").replace("SubmissionStatus.", "")
            score = _f(r.get("publicScore")) if status == "COMPLETE" else None
            self.subs.append({"ref": str(r.get("ref")), "status": status, "score": score,
                              "desc": desc, "date": (r.get("date") or "")[:10],
                              "first_version": vs[0] if vs else None,
                              "track": attribution.description_track(desc)})
        self.by_ref = {s["ref"]: s for s in self.subs}
        self.scores = sorted({round(s["score"], 3) for s in self.subs if s["score"] is not None})

    def mapped(self, version, model, hints):
        out = []
        for s in self.subs:
            how = None
            if s["first_version"] == version:
                how = "description first version token"
            else:
                for h in hints:
                    if h["version"] == version and h["text"].lower() in s["desc"].lower():
                        how = f"type-C description hint L{h['line']}"
                        break
            if how is None:
                continue
            if model and _MODEL_TRACK.get(model) and s["track"] != _MODEL_TRACK[model]:
                continue
            out.append((s, how))
        return out


def _score_eq(claim, approx, actual):
    c = float(claim)
    if approx:
        return abs(c - actual) <= 0.02 + 1e-9
    return round(c, 2) == round(actual, 2)


def check_f5(f, lb, hints):
    val = f["value"].lstrip("~")
    approx = bool(f.get("approx"))
    ev = [{"path": lb.path, "note": "LB source"}] if lb.path else []
    if f.get("ref"):
        s = lb.by_ref.get(f["ref"])
        if s is None:
            return {"status": "UNVERIFIED", "reason": f"ref {f['ref']} not in LB source",
                    "evidence": ev}
        if s["score"] is None:
            return {"status": "UNVERIFIED", "reason": f"ref {f['ref']} is {s['status'] or 'unscored'}",
                    "evidence": ev}
        ok = _score_eq(val, approx, s["score"])
        return {"status": "SUPPORTED" if ok else "CONTRADICTED",
                "reason": f"ref {f['ref']} publicScore {s['score']:.2f} (ref-bound)",
                "evidence": ev, "refs": [f["ref"]]}
    if not lb.subs:
        return {"status": "UNVERIFIED", "reason": "submissions history not available"}
    if not f.get("version"):
        hit = [s["ref"] for s in lb.subs if s["score"] is not None and _score_eq(val, approx, s["score"])]
        return {"status": "UNVERIFIED", "reason": "no version bound"
                + (f"; score exists in LB source (refs {hit[:4]})" if hit else ""), "evidence": ev}
    mp = [(s, how) for s, how in lb.mapped(f["version"], f.get("model"), hints)
          if s["score"] is not None]
    if not mp:
        hit = [s["ref"] for s in lb.subs if s["score"] is not None and _score_eq(val, approx, s["score"])]
        return {"status": "UNVERIFIED",
                "reason": ("score exists, version mapping unknown" if hit
                           else "no COMPLETE submission with this score")
                + f" ({f['version']})", "evidence": ev}
    agree = [s["ref"] for s, _ in mp if _score_eq(val, approx, s["score"])]
    if agree:
        return {"status": "SUPPORTED", "reason": f"{f['version']} -> refs {sorted(agree)}",
                "evidence": ev, "refs": sorted(agree)}
    return {"status": "CONTRADICTED",
            "reason": f"{f['version']} maps to " + ", ".join(
                f"{s['ref']}={s['score']:.2f}" for s, _ in sorted(mp, key=lambda x: x[0]["ref"]))
            + f"; none has {val}", "evidence": ev,
            "refs": sorted(s["ref"] for s, _ in mp)}


# ------------------------------------------------------------------------ runs index

_LOCAL_CUE = re.compile(
    r"(?i)\b(?:parity[ _-]?rig|local[ _-]rig|the rig|rig run|rig arm|m1_\w+|sweeps?|gate_run"
    r"|local_eval[\\/](?:parity_rig|runs))\b")


class RunIndex:
    def __init__(self, rows):
        by_run = {}
        for r in rows or []:
            by_run.setdefault(r["run_id"], []).append(r)
        self.runs = {}
        self.by_label = {}
        self.pulled_by_label = {}
        for rid in sorted(by_run):
            rs = by_run[rid]
            first = rs[0]
            if first.get("run_kind") in ("kaggle-pulled", "kaggle-pulled-legacy"):
                # `kernels output` = latest version only (D5-10): never evidence
                # for a log claim about a version unless attributed.
                for lab in {canon(first.get("version_label") or ""), canon(first.get("arm") or "")}:
                    if lab:
                        self.pulled_by_label.setdefault(lab, []).append(rid)
                continue
            tasks = {r["task"]: r for r in rs}
            known = {t: (r.get("outcome") or {}).get("resolved") for t, r in tasks.items()}
            info = {"run_id": rid, "label": canon(first.get("version_label") or ""),
                    "arm": canon(first.get("arm") or ""), "track": first.get("track"),
                    "platform": (first.get("stack") or {}).get("platform"),
                    "rows": tasks, "n_tasks": len(tasks),
                    "n_known": sum(1 for v in known.values() if v is not None),
                    "resolved": sorted(t for t, v in known.items() if v is True),
                    "config": first.get("config") or {}}
            self.runs[rid] = info
            labs = {info["label"], info["arm"]}
            if info["label"].startswith("-"):
                # hand-pulled legacy dirs (`_v10_kaggle_pull`, `_v6out`) are reps of the
                # version they name: bind them under that version too (rule (d): check all)
                vt = [t["canon"] for t in _regex_tokens(info["label"].lstrip("-"))
                      if t["kind"] == "v"]
                if vt:
                    labs.add(re.sub(r"out$", "", vt[0]) if re.fullmatch(r"v\d+out", vt[0]) else vt[0])
            for lab in sorted(l for l in labs if l):
                self.by_label.setdefault(lab, []).append(rid)

    def candidates(self, version, model, unit_text, cite_text=None):
        """cite_text = the claim's own text + its unit heading: binding rule (a)
        (a cited run path) is scoped there; the local-stack cue reads the unit."""
        cite_text = unit_text if cite_text is None else cite_text
        rids = self.by_label.get(version or "", [])
        if not rids:
            if self.pulled_by_label.get(version or ""):
                return [], (f"no local data for {version} (only a latest-at-pull pulled "
                            f"output, not attributed to this claim)")
            return [], f"no local data for {version}"
        runs = [self.runs[x] for x in rids]
        basis = []
        if model and model in _MODEL_TRACK:
            runs = [r for r in runs if r["track"] == _MODEL_TRACK[model]]
            if not runs:
                return [], f"no local {model} run for {version}"
            basis.append(f"track {_MODEL_TRACK[model]} ({model})")
        else:
            tracks = sorted({r["track"] for r in runs})
            if len(tracks) > 1:
                if "main" in tracks:
                    runs = [r for r in runs if r["track"] == "main"]
                    basis.append("main track preferred (no model token)")
                else:
                    return [], f"ambiguous track for {version}: {tracks}"
        plats = {r["platform"] for r in runs}
        if not _LOCAL_CUE.search(unit_text):
            # stacks are never pooled (R5.2): an entry that does not name the
            # local rig/sweep is judged only against Kaggle runs
            runs = [r for r in runs if r["platform"] == "kaggle"]
            if not runs:
                return [], (f"only local-rig/sweep runs carry {version}; the entry does not "
                            f"name the local stack (stacks are never pooled)")
            if len(plats) > 1:
                basis.append("kaggle stack (entry names no local stack)")
        else:
            basis.append("entry names the local stack")
        cited = [r for r in runs if r["run_id"] in cite_text
                 or r["run_id"].replace("/", "\\") in cite_text]
        if cited:
            runs = cited
            basis.append("run path cited in unit")
        return runs, "; ".join(basis) or "label match"


def _verdict(agree, disagree, what, observed=None):
    a = [r["run_id"] for r in agree]
    d = [r["run_id"] for r in disagree]
    res = {"runs_agree": a[:6], "runs_disagree": d[:6], "n_agree": len(a), "n_disagree": len(d),
           "evidence": [{"path": "kb/runs.jsonl", "note": f"run {x}"} for x in (a + d)[:3]]}
    obs = ""
    if observed and len(d) <= 3:
        obs = " (" + "; ".join(f"{x}: {observed.get(x)}" for x in d) + ")"
    if a and not d:
        res["status"] = "SUPPORTED"
        res["reason"] = f"{what}: all {len(a)} bound run(s) agree"
    elif d and not a:
        res["status"] = "CONTRADICTED"
        res["reason"] = f"{what}: all {len(d)} bound run(s) disagree{obs}"
    else:
        res["status"] = "UNVERIFIED"
        res["reason"] = (f"ambiguous binding: agrees with {len(a)} run(s), disagrees with "
                         f"{len(d)} run(s)")
    return res


def check_run_fact(f, ri, unit_text, cite_text=None):
    if f.get("binding") == "ambiguous-duplicate-column":
        return {"status": "UNVERIFIED",
                "reason": f"two columns name {f.get('version')}; curate a run_tag"}
    if not f.get("version"):
        return {"status": "UNVERIFIED", "reason": "no version bound"}
    runs, basis = ri.candidates(f["version"], f.get("model"), unit_text, cite_text)
    if not runs:
        return {"status": "UNVERIFIED", "reason": basis}
    fld = f["field"]
    if fld in ("F1", "F1v"):
        n_, m_ = (int(x) for x in f["value"].split("/"))
        comp = [r for r in runs if r["n_tasks"] == m_ and r["n_known"] == r["n_tasks"]]
        if not comp:
            sizes = sorted({r["n_tasks"] for r in runs})
            return {"status": "UNVERIFIED",
                    "reason": f"different sample size (claim {m_}; bound runs have {sizes[:6]})"}
        agree = [r for r in comp if len(r["resolved"]) == n_]
        res = _verdict(agree, [r for r in comp if r not in agree], f"resolved {n_}/{m_}",
                       {r["run_id"]: f"{len(r['resolved'])}/{r['n_tasks']}" for r in comp})
    elif fld == "F2":
        comp = [r for r in runs if f.get("task") in r["rows"]
                and (r["rows"][f["task"]].get("outcome") or {}).get("resolved") is not None]
        if not comp:
            return {"status": "UNVERIFIED", "reason": f"no bound run has {f.get('task')}"}
        agree = [r for r in comp if r["rows"][f["task"]]["outcome"]["resolved"] == f["value"]]
        res = _verdict(agree, [r for r in comp if r not in agree], f"{f['task']} resolved",
                       {r["run_id"]: r["rows"][f["task"]]["outcome"]["resolved"] for r in comp})
    elif fld == "F2b":
        want = set(f["value"])
        m_ = int(f["with_f1"].split("/")[1]) if f.get("with_f1") else None
        comp = [r for r in runs if want <= set(r["rows"]) and r["n_known"] == r["n_tasks"]
                and (m_ is None or r["n_tasks"] == m_)]
        if not comp:
            return {"status": "UNVERIFIED", "reason": "no bound run with that task set"}
        agree = [r for r in comp if set(r["resolved"]) == want]
        res = _verdict(agree, [r for r in comp if r not in agree], "resolved task set",
                       {r["run_id"]: r["resolved"] for r in comp})
    elif fld in ("F3", "F3t"):
        col = "calls_total" if fld == "F3t" else f.get("column")
        comp = []
        for r in runs:
            row = r["rows"].get(f.get("task"))
            if row is None:
                continue
            if fld == "F3t":
                v = (row.get("trace") or {}).get("calls_total")
            else:
                v = (row.get("outcome") or {}).get(col)
            if v is not None:
                comp.append((r, v))
        if not comp:
            return {"status": "UNVERIFIED", "reason": f"no bound run has {col} for {f.get('task')}"}
        if col == "tool_calls":
            over = [r for r, _ in comp if r["config"].get("max_tool_calls") is not None
                    and float(f["value"]) > float(r["config"]["max_tool_calls"])]
            if over and len(over) == len(comp):
                return {"status": "UNVERIFIED",
                        "reason": (f"claimed {f['value']} calls exceeds the bound run's "
                                   f"max_tool_calls={over[0]['config']['max_tool_calls']} -> the "
                                   f"claim is about a different {f['version']} run")}
        tol = 0
        if col == "duration_s":       # log seconds are often truncated integers
            tol = 0.5 if float(f["value"]) != int(float(f["value"])) else 1.0
        agree = [r for r, v in comp if abs(float(v) - float(f["value"])) <= tol]
        res = _verdict(agree, [r for r, _ in comp if r not in agree], f"{f.get('task')} {col}",
                       {r["run_id"]: v for r, v in comp})
    elif fld == "F4":
        col = f.get("column")
        comp = [(r, r["config"].get(col)) for r in runs if r["config"].get(col) is not None]
        if not comp:
            return {"status": "UNVERIFIED", "reason": f"bound runs have no config {col}"}
        agree = [r for r, v in comp if float(v) == float(f["value"])]
        res = _verdict(agree, [r for r, _ in comp if r not in agree], f"config {col}")
    elif fld == "F6":
        row = None
        if f.get("task"):
            for r in runs:
                if f["task"] in r["rows"]:
                    row = r["rows"][f["task"]]
                    break
        if row is None or not row.get("trace"):
            return {"status": "UNVERIFIED", "reason": "F6: no bound trace"}
        att = row["trace"].get("edit_attempts") or []
        obs = sorted({str(a.get("observed")) for a in att})
        return {"status": "UNVERIFIED",
                "reason": f"F6 never forced binary: attempts={len(att)} observed={obs[:4]}"}
    else:
        return {"status": "UNVERIFIED", "reason": f"{fld} not auto-checked"}
    res["binding_basis"] = basis
    return res


# ---------------------------------------------------------------------- extraction

def _cid(entry_heading, text):
    return "C-" + hashlib.sha1((_norm_heading(entry_heading) + "\n" + _norm(text))
                               .encode("utf-8")).hexdigest()[:10]


def _rtf_id(text):
    first = re.split(r"(?<=[.!?])\s", _clean(text).strip(), maxsplit=1)[0]
    return "RTF-" + hashlib.sha1(_norm(first).encode("utf-8")).hexdigest()[:8]


def _blocks(lines, fence, a, b):
    """Own-line blocks of a unit: ('table', [(ln, line)]) / ('para', [...])."""
    out, cur, curk = [], [], None
    for k in range(a, b + 1):
        if k < 1 or k > len(lines):
            continue
        ln = lines[k - 1]
        if fence[k - 1] or not ln.strip() or _level(ln):
            if cur:
                out.append((curk, cur))
            cur, curk = [], None
            continue
        kind = "table" if ln.lstrip().startswith("|") else "para"
        if curk is not None and kind != curk:
            out.append((curk, cur))
            cur = []
        curk = kind
        cur.append((k, ln))
    if cur:
        out.append((curk, cur))
    return out


def _load_jsonl(p):
    rows, errs = [], []
    p = pathlib.Path(p) if p else None
    if p is None or not p.is_file():
        return rows, errs
    for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            o = json.loads(ln)
            o["_line"] = i
            rows.append(o)
        except ValueError as e:
            errs.append({"line": i, "error": str(e)[:120]})
    return rows, errs


def _load_rows_arg(x):
    if x is None:
        return []
    if isinstance(x, (str, pathlib.Path)):
        p = pathlib.Path(x)
        if not p.is_file():
            return []
        with p.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    return list(x)


def _ev_path(raw):
    s = str(raw).strip()
    p = re.split(r"[#\s]", s, maxsplit=1)[0]
    line = None
    m = re.search(r"#L(\d+)", s)
    if m:
        line = int(m.group(1))
    if "/" in p and re.search(r"\.[A-Za-z0-9]{1,6}$|/$", p):
        return p, line
    return None, None


def merge_curated(curated_rows, root, auto_ids):
    out, orphans = [], []
    last = {}
    for r in curated_rows:
        key = r.get("claim_id") or r.get("id")
        if key:
            last[key] = r
    for key in sorted(last):
        r = last[key]
        ev = []
        for e in r.get("evidence") or []:
            raw = e if isinstance(e, str) else json.dumps(e, sort_keys=True)
            p, line = _ev_path(e.get("path") if isinstance(e, dict) else e)
            exists = (root / p).exists() if (p and root) else None
            ev.append({"raw": raw[:240], "path": p, "line": line, "exists": exists})
        paths = [e for e in ev if e["path"]]
        missing = [e["path"] for e in paths if e["exists"] is False]
        row = {"id": key, "kind": r.get("kind"), "status": r.get("status") or "UNVERIFIED",
               "text": (r.get("text") or r.get("reason") or "")[:600],
               "author": r.get("author"), "curated_line": r.get("_line"), "evidence": ev,
               "evidence_ok": not missing, "evidence_missing": missing,
               "applies_to_auto": key in auto_ids}
        if r.get("claim_id") and key not in auto_ids:
            orphans.append({"id": key, "reason": "claim_id absent from this build"})
        out.append(row)
    return out, orphans


def extract(log_text, lb_source_rows, curated_claims_path, baseline_info, runs_rows=None,
            *, lb_source_path="", run_labels=None, lexicon_fn=None):
    """cl-4 entry point. Returns {claims, units, curated, orphans, curated_errors,
    scored_submissions, live_best_chain, chains, candidate_links,
    unresolved_citations, contradictions, hints, stats, cl_version}."""
    run_labels = run_labels or {}
    runs_rows = runs_rows or []
    labels = sorted({r.get("version_label") for r in runs_rows if r.get("version_label")}
                    | {r.get("arm") for r in runs_rows if r.get("arm")})
    homonyms = label_collisions(runs_rows, log_text)
    aliases = dict(run_labels.get("aliases") or {})
    for h in homonyms:
        for k in h["route_aliases"]:
            aliases.setdefault(k, h["kernel_label"])
    tok = Tokenizer(labels, aliases)
    homonym_tokens = {h["token"]: h for h in homonyms}
    lever_fn = lexicon_fn or (lambda text: [])
    units, lines, fence = segment(log_text, tok, lever_fn)
    by_id = {u["id"]: u for u in units}
    lb_rows = _load_rows_arg(lb_source_rows)
    hints = []
    raw_claims = []

    def unit_text(u):
        top = u if u["level"] == 2 else u["parent"]
        return "\n".join(lines[top["start"] - 1:top["end"]])

    for u in units:
        a, b = u["own"]
        own_blocks = _blocks(lines, fence, a, b)
        ukind = u["kind"]
        # heading block
        hfacts, htoks = line_facts(u["heading_block"], u["start"], tok)
        if ukind == "verdict" or VERDICT_RX.search(u["heading_block"]) \
                or CORRECTION_RX.search(u["heading_block"]):
            raw_claims.append(dict(unit=u, kind="heading", text=u["heading_block"],
                                   line=u["start"], lines=(u["start"], u["heading_end"]),
                                   facts=hfacts, tokens=htoks, rule=3))
        elif any(f["field"] in FACTLINE_FIELDS and f.get("version") for f in hfacts):
            raw_claims.append(dict(unit=u, kind="fact-line", text=u["heading_block"],
                                   line=u["start"], lines=(u["start"], u["heading_end"]),
                                   facts=hfacts, tokens=htoks, rule=5))
        for bk, blk in own_blocks:
            if bk == "table":
                hdr, rows = None, []
                if len(blk) >= 2 and _SEP.match(blk[1][1].strip()):
                    hdr = _cells(blk[0][1])
                    rows = [(k, _cells(l)) for k, l in blk[2:] if not _SEP.match(l.strip())]
                else:
                    rows = [(k, _cells(l)) for k, l in blk if not _SEP.match(l.strip())]
                tf = table_facts(hdr or [], rows, tok, u["first_version"], hints) if hdr \
                    else table_facts([], rows, tok, u["first_version"], hints)
                for ln, rtxt, facts, kind, rtasks in tf:
                    keep = kind == "version-row" or any(
                        f["field"] in FACTLINE_FIELDS and f.get("version") for f in facts) \
                        or (ukind == "verdict" and rtasks)
                    if keep:
                        raw_claims.append(dict(unit=u, kind=kind, text=rtxt, line=ln,
                                               lines=(ln, ln), facts=facts,
                                               tokens=tok.tokens(_clean(rtxt)), rule=2))
                continue
            # RTF numbered items
            if ukind == "read-this-first":
                items, cur = [], None
                for k, ln in blk:
                    if re.match(r"^\d+\.\s", ln):
                        if cur:
                            items.append(cur)
                        cur = [(k, ln)]
                    elif cur is not None:
                        cur.append((k, ln))
                if cur:
                    items.append(cur)
                for it in items:
                    text = "\n".join(l for _, l in it)
                    facts, toks = [], []
                    for k, l in it:
                        fs, ts = line_facts(l, k, tok)
                        facts += fs
                        toks += ts
                    raw_claims.append(dict(unit=u, kind="standing-truth", text=text,
                                           line=it[0][0], lines=(it[0][0], it[-1][0]),
                                           facts=facts, tokens=toks, rule=1))
                continue
            # paragraphs chunked <= 12 lines
            chunks = [blk[i:i + 12] for i in range(0, len(blk), 12)]
            for ci, ch in enumerate(chunks):
                text = "\n".join(l for _, l in ch)
                per_line = []
                for k, l in ch:
                    fs, ts = line_facts(l, k, tok)
                    per_line.append((k, l, fs, ts))
                if VERDICT_RX.search(text) or CORRECTION_RX.search(text):
                    facts = [f for _, _, fs, _ in per_line for f in fs]
                    toks = [t for _, _, _, ts in per_line for t in ts]
                    raw_claims.append(dict(unit=u, kind=("verdict" if ukind == "verdict" else "paragraph"),
                                           text=text, line=ch[0][0], lines=(ch[0][0], ch[-1][0]),
                                           facts=facts, tokens=toks, rule=4,
                                           chunk=(f"{ci + 1}/{len(chunks)}" if len(chunks) > 1 else None)))
                    continue
                for k, l, fs, ts in per_line:
                    if any(f["field"] in FACTLINE_FIELDS and f.get("version") for f in fs):
                        raw_claims.append(dict(unit=u, kind="fact-line", text=l, line=k,
                                               lines=(k, k), facts=fs, tokens=ts, rule=5))

    # ------------------------------------------------------------ binding rules 3/4
    lb = LBIndex(lb_rows, tok, lb_source_path)
    ri = RunIndex(runs_rows)
    base_label = canon((baseline_info or {}).get("label"))
    claims = []
    seen_ids = {}
    for rc in raw_claims:
        u = rc["unit"]
        cvers = _vers(rc["tokens"])
        first_tok = next((t for t in rc["tokens"] if t["kind"] != "model"), None)
        for f in rc["facts"]:
            line_first = f.pop("_line_first", None)
            if f["field"] in ("bar", "unkeyed", "F9"):
                continue
            if f.get("version") is None:
                if line_first is not None:
                    f["version"], f["model"] = line_first
                    f["binding"] = "rule3-line-first"
                elif first_tok is not None:
                    f["version"], f["model"] = first_tok["canon"], first_tok.get("model")
                    f["binding"] = "rule3-claim-first"
                elif rc["rule"] != 5 and u["first_version"]:
                    f["version"] = u["first_version"]
                    f["binding"] = "rule4-unit-first"
            if f["field"] in ("F1", "F1v", "F2b") and not TASK_RX.search(rc["text"]):
                f["task_set_unstated"] = True
        rc["facts"] = [{k: v for k, v in f.items() if v is not None and k != "pos"}
                       for f in rc["facts"]]
        if rc["kind"] == "standing-truth":
            cid = _rtf_id(rc["text"])
        else:
            cid = _cid(u["entry_heading"], rc["text"])
        n = seen_ids.get(cid, 0) + 1
        seen_ids[cid] = n
        if n > 1:
            cid = f"{cid}-{n}"
        claims.append({"claim_id": cid, "id": cid, "kind": rc["kind"], "unit_id": u["id"],
                       "unit_level": u["level"], "unit_kind": u["kind"],
                       "entry_heading": u["entry_heading"][:200],
                       "heading": u["heading_block"][:160],
                       "unit_start_line": u["start"], "line": rc["line"],
                       "lines": f"{rc['lines'][0]}-{rc['lines'][1]}",
                       "chunk": rc.get("chunk"), "date": u["date"],
                       "date_suspect": u["date_suspect"] or None,
                       "versions": sorted(set(cvers) | {f["version"] for f in rc["facts"]
                                                       if f.get("version")}),
                       "models": _models(rc["tokens"]),
                       "tasks": sorted(set(TASK_RX.findall(rc["text"]))),
                       "levers": lever_fn(rc["text"]),
                       "text": rc["text"][:600], "facts": rc["facts"],
                       "correction_unit": u["correction_unit"]})

    # ------------------------------------------------------------------- checks
    n_checked = 0
    ut_cache = {}
    for c in claims:
        uid = c["unit_id"]
        if uid not in ut_cache:
            ut_cache[uid] = unit_text(by_id[uid])
        ut = ut_cache[uid]
        for f in c["facts"]:
            fld = f["field"]
            if fld not in CHECK_FIELDS:
                continue
            if f.get("quoted"):
                f["check"] = {"status": "UNVERIFIED",
                              "reason": "quoted (retracted) statement inside a correction; "
                                        "not asserted"}
                continue
            if fld == "F5":
                chk = check_f5(f, lb, hints)
            elif fld == "F10":
                chk = _check_f10(f, base_label, lb, hints)
            elif fld == "F9":
                chk = _check_f9(f, ri)
            else:
                chk = check_run_fact(f, ri, ut, c["text"] + "\n" + by_id[uid]["heading_block"])
            if chk.get("status") == "CONTRADICTED" and fld != "F5":
                chk["downgraded_from"] = "CONTRADICTED"   # cleared below if asserted
            if chk.get("status") == "CONTRADICTED" and fld == "F4":
                chk["status"] = "UNVERIFIED"
                chk["reason"] = ("config differs (F4 is never asserted as a contradiction: "
                                 "the line may describe a variant) — " + chk["reason"])
            elif chk.get("status") == "CONTRADICTED" and \
                    (str(f.get("binding", "")).startswith("rule4")
                     or f.get("binding") == "rule3-claim-first"):
                chk["status"] = "UNVERIFIED"
                chk["reason"] = (f"bound only by a weak fallback ({f.get('binding')}: version token "
                                 "not on the fact's line); disagreement not asserted — "
                                 + chk["reason"])
            elif chk.get("status") == "CONTRADICTED" and \
                    f.get("binding") == "rule1-version-column" and \
                    f.get("version") != by_id[uid]["first_version"] and \
                    "run path cited" not in chk.get("binding_basis", ""):
                # a comparison column inside another version's entry: the label
                # may name a different rep than the one on disk (run identity
                # != label identity); never asserted without a cited run.
                chk["status"] = "UNVERIFIED"
                chk["reason"] = (f"comparison column in a {by_id[uid]['first_version']} entry; "
                                 f"may be a different {f.get('version')} rep (run not cited) — "
                                 + chk["reason"])
            elif chk.get("status") == "CONTRADICTED" and f.get("version") in homonym_tokens:
                h = homonym_tokens[f["version"]]
                chk["status"] = "UNVERIFIED"
                chk["reason"] = (f"label collision: {f['version']} names both experiment run(s) "
                                 f"{sorted(h['experiment_runs_tasks'])} and kernel "
                                 f"{h['kernel_label']} ({h['kernel_runs_tasks']} tasks); "
                                 f"referent not determined — " + chk["reason"])
            if chk.get("status") == "CONTRADICTED":
                chk.pop("downgraded_from", None)
            f["check"] = chk
        # a cell whose call count exceeds the bound run's budget is about another
        # run: none of that cell's facts can contradict the bound run
        foreign = {(f.get("version"), f.get("task"), f["line"]) for f in c["facts"]
                   if "exceeds the bound run" in (f.get("check") or {}).get("reason", "")}
        for f in c["facts"]:
            if (f.get("version"), f.get("task"), f["line"]) in foreign and \
                    (f.get("check") or {}).get("status") == "CONTRADICTED":
                f["check"]["status"] = "UNVERIFIED"
                f["check"]["downgraded_from"] = "CONTRADICTED"
                f["check"]["reason"] = ("same cell claims more calls than the bound run's "
                                        "budget (different run) — " + f["check"]["reason"])
        n_checked += sum(1 for f in c["facts"] if "check" in f)
        sts = [f["check"]["status"] for f in c["facts"] if "check" in f and not f.get("quoted")]
        if "CONTRADICTED" in sts:
            st = "CONTRADICTED"
            reason = next(f["check"]["reason"] for f in c["facts"]
                          if f.get("check", {}).get("status") == "CONTRADICTED")
        elif "UNVERIFIED" in sts:
            st = "UNVERIFIED"
            reason = next(f["check"]["reason"] for f in c["facts"]
                          if f.get("check", {}).get("status") == "UNVERIFIED")
        elif sts:
            st, reason = "SUPPORTED", "all checked facts agree"
        else:
            st, reason = "UNVERIFIED", "judgment claim, not curated"
        c["status"] = c["auto_status"] = st
        c["reason"] = reason
        c["basis"] = "auto" if sts else "none"
        ev = [{"path": "GEMMA_EXPERIMENT_LOG.md", "line": c["line"]}]
        for f in c["facts"]:
            for e in (f.get("check") or {}).get("evidence") or []:
                if e not in ev:
                    ev.append(e)
        c["evidence"] = ev[:6]

    # ------------------------------------------------------------- supersession
    links, unresolved, candidates = _supersession(units, lines, fence, tok)
    links += _quote_links(claims, by_id, links)
    sup_by = {}            # unit-level supersession
    sup_claim = {}         # claim-level (quoted-fact links retract one statement)
    for lk in links:
        if not lk["applied"]:
            continue
        if lk.get("old_claim"):
            sup_claim.setdefault(lk["old_claim"], []).append(lk)
        else:
            sup_by.setdefault(lk["old"], []).append(lk)
    # chains (union-find over applied links)
    parent = {u["id"]: u["id"] for u in units}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for lk in links:
        if lk["applied"] and lk["new"]:
            ra, rb = find(lk["old"]), find(lk["new"])
            if ra != rb:
                parent[ra] = rb
    comps = {}
    linked_units = {lk["old"] for lk in links if lk["applied"]} | \
        {lk["new"] for lk in links if lk["applied"] and lk["new"]}
    for u in units:
        if u["id"] in linked_units:
            comps.setdefault(find(u["id"]), []).append(u)
    chain_of = {}
    chains = []
    for root_id, us in comps.items():
        us = sorted(us, key=lambda x: x["start"])
        ids = [x["id"] for x in us]
        for x in us:
            chain_of[x["id"]] = ids
        chains.append({"chain": ids, "lines": [x["start"] for x in us],
                       "newest": ids[-1], "newest_heading": us[-1]["heading_block"][:200],
                       "newest_line": us[-1]["start"],
                       "newest_superseded": us[-1]["id"] in sup_by})
    chains.sort(key=lambda c: c["lines"][0])
    head_claim = {}
    for c in claims:
        if c["kind"] == "heading":
            head_claim.setdefault(c["unit_id"], c["claim_id"])
    n_sup = 0
    for c in claims:
        u = by_id[c["unit_id"]]
        hits = list(sup_by.get(u["id"], [])) + list(sup_claim.get(c["claim_id"], []))
        if u["level"] == 3 and u["parent"]["id"] in sup_by:
            hits += sup_by[u["parent"]["id"]]
        cid_chain = chain_of.get(u["id"]) or (chain_of.get(u["parent"]["id"]) if u["level"] == 3 else None)
        c["chain"] = cid_chain or []
        c["superseded_by"] = [{"unit_id": lk["new"], "claim_id": head_claim.get(lk["new"]),
                               "line": lk["new_line"], "link_basis": lk["basis"],
                               "drift_tolerance": lk.get("drift_tolerance")}
                              for lk in sorted(hits, key=lambda x: (x["new_line"] or 0, x["basis"]))]
        c["superseded_by"] = [{k: v for k, v in s.items() if v is not None}
                              for s in c["superseded_by"]]
        if hits:
            c["status"] = "SUPERSEDED"
            n_sup += 1
    # the log disagreeing with ITSELF (same field / version / task / sample size,
    # different value, no correction linking them) means the label may name
    # different runs: report both lines, never assert either against one run
    self_dis = _self_disagreements(claims)
    # ------------------------------------------------------------- live-best chain
    lbc = []
    for c in claims:
        for f in c["facts"]:
            if f["field"] == "F10" and f.get("version"):
                lbc.append({"claim_id": c["claim_id"], "line": f["line"], "version": f["version"],
                            "polarity": f["value"], "phrase": f.get("phrase"),
                            "status": (f.get("check") or {}).get("status"),
                            "claim_status": c["status"]})
    lbc.sort(key=lambda x: (x["line"], x["claim_id"]))
    prev = None
    for x in lbc:
        if x["polarity"] != "live-best":
            continue
        if prev is not None and prev["version"] != x["version"]:
            x["supersedes_live_best_of"] = prev["version"]
        prev = x
    # ------------------------------------------------------------- contradictions
    contradictions = _contradictions(claims, links)
    # --------------------------------------------------------------------- curated
    cur_path = pathlib.Path(curated_claims_path) if curated_claims_path else None
    root = cur_path.resolve().parents[3] if cur_path is not None and len(cur_path.resolve().parents) > 3 else None
    cur_rows, cur_errs = _load_jsonl(cur_path)
    auto_ids = {c["claim_id"] for c in claims}
    curated, orphans = merge_curated(cur_rows, root, auto_ids)
    conflicts = []
    for cr in curated:
        if cr["applies_to_auto"] and cr["evidence_ok"]:
            for c in claims:
                if c["claim_id"] == cr["id"]:
                    if c["status"] != cr["status"]:
                        conflicts.append({"id": cr["id"], "auto": c["status"], "curated": cr["status"]})
                    c["status"] = cr["status"]
                    c["basis"] = "curated"

    scored = {}
    for s in lb.subs:
        if s["score"] is not None:
            scored.setdefault(s["score"], []).append(s["desc"][:60])
    n_facts = sum(len(c["facts"]) for c in claims)
    n_decided = sum(1 for c in claims for f in c["facts"]
                    if (f.get("check") or {}).get("status") in ("SUPPORTED", "CONTRADICTED"))
    weak = [{"claim_id": c["claim_id"], "line": f["line"], "field": f["field"],
             "version": f.get("version"), "task": f.get("task"), "value": f["value"],
             "reason": f["check"]["reason"][:300]}
            for c in claims for f in c["facts"]
            if (f.get("check") or {}).get("downgraded_from") == "CONTRADICTED"]
    stats = {"units": len(units), "claims": len(claims), "facts": n_facts,
             "facts_checked": n_checked, "facts_decided": n_decided,
             "disagreements_not_asserted": len(weak),
             "label_collisions": len(homonyms), "self_disagreements": len(self_dis),
             "quoted_facts": sum(1 for c in claims for f in c["facts"] if f.get("quoted")),
             "quoted_fact_links": sum(1 for lk in links if lk["basis"] == "quoted-fact"),
             "superseded_claims": n_sup, "chains": len(chains),
             "links_applied": sum(1 for lk in links if lk["applied"]),
             "links_total": len(links)}
    unit_rows = [{"id": u["id"], "level": u["level"], "start": u["start"], "end": u["end"],
                  "heading": u["heading_block"][:200], "kind": u["kind"], "date": u["date"],
                  "date_raw": u["date_raw"], "date_suspect": u["date_suspect"],
                  "versions": u["versions"], "tasks": u["tasks"], "levers": u["levers"],
                  "correction_unit": u["correction_unit"],
                  "superseded": u["id"] in sup_by,
                  "parent": u["parent"]["id"] if u["parent"] else None}
                 for u in units]
    return {"claims": claims, "units": unit_rows, "curated": curated, "orphans": orphans,
            "curated_errors": cur_errs, "curation_conflicts": conflicts,
            "scored_submissions": scored, "live_best_chain": lbc, "chains": chains,
            "links": links, "candidate_links": candidates,
            "unresolved_citations": unresolved, "contradictions": contradictions,
            "weak_disagreements": weak, "label_collisions": homonyms,
            "self_disagreements": self_dis,
            "hints": hints, "stats": stats, "lb_source_path": lb_source_path,
            "cl_version": CL_VERSION}


_KVER_LABEL = re.compile(r"-version(\d+)$")
_KVER_LOG = re.compile(r"(?i)\bv(\d+)\s+(?:config|caps)\b|\bv(\d+)\s*=\s*\d+-task version\b"
                       r"|\bv(\d+)\s+V\d+\b")


def label_collisions(runs_rows, log_text):
    """Version tokens that name two different things: an experiment label vN
    (e.g. Outputs/v10, the 10-task budget-40 run) and version N of a kernel
    (e.g. gemma-sibling-conform-31b-a3-hard-version10, a 129-task run). Pure;
    measured from run labels + explicit log patterns (`vN config`, `vN caps`,
    `vN = 129-task version`, `vN V2`)."""
    exp = {}
    kern = {}
    for r in runs_rows or []:
        lab = r.get("version_label") or ""
        m = _KVER_LABEL.search(lab)
        if m:
            kern.setdefault(m.group(1), {}).setdefault(lab, set()).add(r["task"])
        elif re.fullmatch(r"v\d+", canon(lab)):
            exp.setdefault(canon(lab)[1:], {}).setdefault(r["run_id"], set()).add(r["task"])
    log_hits = {}
    for i, ln in enumerate((log_text or "").split("\n"), 1):
        for m in _KVER_LOG.finditer(ln):
            n = next(g for g in m.groups() if g)
            log_hits.setdefault(n, []).append(i)
    out = []
    for n in sorted(set(kern) & (set(exp) | set(log_hits)), key=int):
        klab = sorted(kern[n])[0]
        out.append({
            "token": f"v{n}",
            "kernel_label": canon(klab),
            "kernel_runs_tasks": {k: len(v) for k, v in sorted(kern[n].items())},
            "experiment_runs_tasks": {k: len(v) for k, v in sorted(exp.get(n, {}).items())},
            "log_kernel_version_lines": log_hits.get(n, [])[:12],
            "n_log_kernel_version_lines": len(log_hits.get(n, [])),
            "route_aliases": [f"v{n} config", f"v{n} caps"],
        })
    return out


def _check_f10(f, base_label, lb, hints):
    v = f.get("version")
    if not v:
        return {"status": "UNVERIFIED", "reason": "live-best phrase with no version token"}
    ev = [{"path": "kb/curated/run_labels.json", "note": "curated baseline pointer"}]
    if f["value"] == "not-live-best":
        if v != base_label:
            return {"status": "SUPPORTED", "reason": f"{v} is not the curated baseline ({base_label})",
                    "evidence": ev}
        return {"status": "CONTRADICTED", "reason": f"{v} IS the curated baseline", "evidence": ev}
    if v == base_label:
        return {"status": "SUPPORTED", "reason": f"curated baseline is {base_label}", "evidence": ev}
    note = ""
    best = [s for s in lb.subs if s["score"] is not None and s["track"] == "main"]
    if best:
        top = max(s["score"] for s in best)
        tops = [s["ref"] for s in best if s["score"] == top and s["first_version"] == v]
        if tops:
            note = f"; LB source main-track best {top:.2f} maps to {v} (refs {sorted(tops)})"
    return {"status": "UNVERIFIED",
            "reason": f"BASELINE-CLAIM: names {v}; curated baseline is {base_label or 'unset'} "
                      f"(never adopted){note}", "evidence": ev}


def _check_f9(f, ri):
    res = set()
    for r in ri.runs.values():
        if r["track"] == "main" and r["platform"] == "kaggle":
            res.update(r["resolved"])
    n = len(res)
    if n == f["value"]:
        return {"status": "SUPPORTED", "reason": f"{n} distinct resolved tasks on main-track Kaggle rows"}
    return {"status": "UNVERIFIED",
            "reason": f"measured now {n} distinct resolved tasks on main-track Kaggle rows "
                      f"(includes runs after the claim)"}


_CITE_OTHER_FILE = re.compile(
    r"(?i)(?:(?<!LOG)\.(?:py|md|json|jsonl|yaml|yml|ipynb|txt|csv|log)|README|_src)\s*:?\s*$")
_CITE_IS_SOURCE_PRE = re.compile(
    r"(?i)\b(?:retract\w*|correct\w*|refut\w*|overturn\w*|supersed\w*|falsif\w*)\s+"
    r"(?:\w+\s+){0,2}by\b[^.;]{0,40}$|\b(?:per|see|via|according to)\s+(?:the\s+)?$")
_CITE_IS_SOURCE_POST = re.compile(r"(?i)\s*(?:'s\s+)?(?:retraction|correction|audit|refute)\b")

_STOP = frozenset("the of a an to in on at is are was were and or for by with not no it "
                  "this that as be we i my our from see end log".split())


_QUOTE_FIELDS = ("F1", "F1v", "F2", "F2b", "F5")


def _gkey(f):
    """(field, version, task, sample size) group of a fact."""
    fld = f["field"].rstrip("v")
    m = str(f["value"]).split("/")[1] if fld == "F1" and "/" in str(f["value"]) else ""
    return (fld, f.get("version"), f.get("task") or "", m, f.get("ref") or "")


def _self_disagreements(claims):
    """Downgrade a CONTRADICTED fact when another (non-quoted, non-superseded)
    log fact in the same group states a different value. Returns the list."""
    idx = {}
    for c in claims:
        if c["status"] == "SUPERSEDED":
            continue
        for f in c["facts"]:
            if f["field"] in _QUOTE_FIELDS and f.get("version") and not f.get("quoted"):
                idx.setdefault(_gkey(f), []).append((f["line"], str(f["value"]), c["claim_id"]))
    out = []
    for c in claims:
        if c["status"] != "CONTRADICTED":
            continue
        changed = False
        for f in c["facts"]:
            chk = f.get("check") or {}
            if chk.get("status") != "CONTRADICTED":
                continue
            others = sorted({x for x in idx.get(_gkey(f), [])
                             if x[1] != str(f["value"]) and x[2] != c["claim_id"]})
            if not others:
                continue
            lines = "; ".join(f"L{ln} says {v}" for ln, v, _ in others[:4])
            chk["status"] = "UNVERIFIED"
            chk["downgraded_from"] = "CONTRADICTED"
            chk["reason"] = (f"the log disagrees with itself (L{f['line']} says {f['value']}; "
                             f"{lines}) and no correction links them, so the label may name "
                             f"different runs — " + chk["reason"])
            out.append({"claim_id": c["claim_id"], "line": f["line"], "field": f["field"],
                        "version": f.get("version"), "value": f["value"],
                        "other_lines": [{"line": ln, "value": v, "claim_id": cid}
                                        for ln, v, cid in others[:6]]})
            changed = True
        if changed:
            sts = [f["check"]["status"] for f in c["facts"] if "check" in f and not f.get("quoted")]
            c["status"] = "CONTRADICTED" if "CONTRADICTED" in sts else "UNVERIFIED"
            c["reason"] = next(f["check"]["reason"] for f in c["facts"]
                               if (f.get("check") or {}).get("status") == c["status"])
    return out


def _fkey(f):
    v = f["value"]
    return (f["field"].rstrip("v"), f.get("version"), f.get("task") or "",
            tuple(v) if isinstance(v, list) else str(v))


def _quote_links(claims, by_id, existing):
    """A correction that QUOTES a retracted statement supersedes every earlier
    claim that asserted exactly that fact (same field, version, task, value).
    E.g. L9281 `CORRECTED: "... v6 scored 1/6 on the v6b sample."` -> the L6746
    claim `v6 scored 1/6 on this sample`."""
    have = {(lk["old"], lk["new"]) for lk in existing}
    out = []
    asserted = []
    for c in claims:
        for f in c["facts"]:
            if f["field"] in _QUOTE_FIELDS and f.get("version") and not f.get("quoted"):
                asserted.append((f["line"], _fkey(f), c["unit_id"], c["claim_id"]))
    for c in claims:
        for f in c["facts"]:
            if not f.get("quoted") or f["field"] not in _QUOTE_FIELDS or not f.get("version"):
                continue
            k = _fkey(f)
            new = by_id[c["unit_id"]]
            for line, k2, uid, ocid in asserted:
                if k2 != k or line >= f["line"] or uid == new["id"]:
                    continue
                if (ocid, new["id"]) in have:
                    continue
                have.add((ocid, new["id"]))
                old = by_id[uid]
                out.append({"old": uid, "old_claim": ocid, "old_line": old["start"], "new": new["id"],
                            "new_line": new["start"], "basis": "quoted-fact",
                            "cite_line": f["line"], "applied": True,
                            "quoted_fact": f"{k[0]} {k[1]}{(' ' + k[2]) if k[2] else ''}={f['value']}",
                            "asserted_line": line})
    return out


def _bigrams(text):
    """Two-word heading phrases (no stopwords; dates/numbers dropped)."""
    w = [x for x in re.findall(r"[a-z]+", text.lower())]
    return {f"{a} {b}" for a, b in zip(w, w[1:]) if a not in _STOP and b not in _STOP}


def _containing(units, line):
    best = None
    for u in units:
        if u["start"] <= line <= u["end"]:
            if best is None or u["level"] > best["level"]:
                best = u
    return best


def _tokset(u):
    return set(u["versions"]) | set(u["tasks"]) | set(u["levers"])


def _supersession(units, lines, fence, tok):
    links, unresolved, candidates = [], [], []
    order = sorted(units, key=lambda u: u["start"])

    def add(old, new, basis, line, applied=True, **kw):
        lk = {"old": old["id"], "old_line": old["start"], "new": new["id"] if new else None,
              "new_line": new["start"] if new else None, "basis": basis, "cite_line": line,
              "applied": applied}
        lk.update(kw)
        links.append(lk)

    # (2) heading tags
    for i, u in enumerate(order):
        if not u["self_retracted"]:
            continue
        hb = _bigrams(u["heading_block"])
        hv = set(_vers(u["head_tokens"]))
        tgt, basis = None, "heading-tag (no correcting unit found)"
        for v in order[i + 1:]:
            if v["start"] <= u["end"] and v["level"] > u["level"]:
                continue
            if v["self_retracted"]:
                continue
            if CORRECTION_RX.search(v["heading_block"]) and (
                    (hv & set(_vers(v["head_tokens"])))
                    or len(hb & _bigrams(v["heading_block"])) >= 1):
                tgt, basis = v, "heading-tag"
                break
            # the correction may be a paragraph inside a later entry
            va, vb = v["own"]
            para = []
            hit = False
            for k in range(va, min(vb, len(lines)) + 1):
                ln = lines[k - 1]
                if ln.strip() and not fence[k - 1]:
                    para.append(ln)
                    continue
                txt = " ".join(para)
                para = []
                if txt and CORRECTION_RX.search(txt) and len(hb & _bigrams(txt)) >= 2:
                    hit = True
                    break
            txt = " ".join(para)
            if not hit and txt and CORRECTION_RX.search(txt) and len(hb & _bigrams(txt)) >= 2:
                hit = True
            if hit:
                tgt, basis = v, "heading-tag (correcting paragraph)"
                break
        add(u, tgt, basis, u["start"])
    # (3) CORRECTION/RETRACTION ... ABOVE
    for i, u in enumerate(order):
        if u["self_retracted"] or not _ABOVE.search(u["heading_block"]):
            continue
        hv = set(_vers(u["head_tokens"]))
        if not hv:
            unresolved.append({"unit_id": u["id"], "line": u["start"], "cite": "ABOVE",
                               "reason": "no version token in the heading"})
            continue
        tgt = None
        for v in reversed(order[:i]):
            if v["start"] <= u["start"] <= v["end"] and v["level"] < u["level"]:
                continue
            if hv & set(v["versions"]):
                tgt = v
                break
        if tgt:
            add(tgt, u, "correction-above", u["start"])
        else:
            unresolved.append({"unit_id": u["id"], "line": u["start"], "cite": "ABOVE",
                               "reason": "no earlier unit shares a version token"})
    # (1) cited lines in correction units / correction-stem paragraphs
    n = len(lines)
    for u in order:
        a, b = u["own"]
        paras = [[(u["start"], u["heading_block"])]]
        cur = []
        for k in range(u["heading_end"] + 1, b + 1):
            if k > n:
                break
            ln = lines[k - 1]
            if fence[k - 1] or not ln.strip():
                if cur:
                    paras.append(cur)
                    cur = []
                continue
            cur.append((k, ln))
        if cur:
            paras.append(cur)
        for pi, p in enumerate(paras):
            text = " ".join(l for _, l in p)
            if not (CORRECTION_RX.search(text) or (u["correction_unit"] and pi <= 1)):
                continue
            if u["self_retracted"] and pi == 0:
                continue
            ptoks = set(_vers(tok.tokens(text))) | set(TASK_RX.findall(text)) | set(u["levers"]) \
                | set(_vers(u["head_tokens"]))
            sspans = _sent_spans(text)
            for m in _CITE.finditer(text):
                cl = int(next(g for g in m.groups() if g))
                if cl < 1 or cl > n:
                    continue
                sa, sb = _sent_of(sspans, m.start())
                if not CORRECTION_RX.search(text[sa:sb]):
                    continue        # a reference, not a correction of the cited line
                pre = text[max(0, m.start() - 60):m.start()]
                post = text[m.end():m.end() + 20]
                if _CITE_OTHER_FILE.search(pre):
                    continue        # a line of another file (README, notebook_src.py, ...)
                if _CITE_IS_SOURCE_PRE.search(pre) or _CITE_IS_SOURCE_POST.match(post):
                    unresolved.append({"unit_id": u["id"], "line": p[0][0], "cite": m.group(0),
                                       "reason": "cited line is the SOURCE of a correction "
                                                 "(e.g. 'retracted by ... at Lx', 'the Lx "
                                                 "retraction'), not its target"})
                    continue
                tgt = _containing(units, cl)
                if tgt is not None and tgt["kind"] in ("read-this-first", "version-history"):
                    unresolved.append({"unit_id": u["id"], "line": p[0][0], "cite": m.group(0),
                                       "reason": f"cites the in-place-edited {tgt['kind']} unit "
                                                 "(never superseded by citation)"})
                    continue
                basis, drift = "cited-line", None
                if tgt is None or tgt is u or not (_tokset(tgt) & ptoks):
                    tgt = None
                    near = sorted(((abs(v["start"] - cl), v["start"], v["id"], v) for v in units
                                   if abs(v["start"] - cl) <= 40 and v is not u
                                   and v["kind"] not in ("read-this-first", "version-history")
                                   and (_tokset(v) & ptoks)), key=lambda x: x[:3])
                    if near:
                        tgt = near[0][3]
                        basis, drift = "cited-line-nearest", 40
                if tgt is None:
                    unresolved.append({"unit_id": u["id"], "line": p[0][0], "cite": m.group(0),
                                       "reason": "no unit at/near the cited line shares a token"})
                    continue
                if tgt["start"] >= u["start"] or (u["start"] <= tgt["start"] <= u["end"]):
                    add(tgt, u, basis + " (forward/inside; not applied)", p[0][0],
                        applied=False, drift_tolerance=drift)
                elif u["level"] == 3 and tgt is u["parent"]:
                    add(tgt, u, basis + " (parent; not applied)", p[0][0], applied=False,
                        drift_tolerance=drift)
                else:
                    add(tgt, u, basis, p[0][0], drift_tolerance=drift)
    # candidate links (keyword-overlap; never applied): nearest earlier unit
    for i, u in enumerate(order):
        if not u["correction_unit"] or u["self_retracted"]:
            continue
        mine = _tokset(u)
        for v in reversed(order[:i]):
            if v["start"] <= u["start"] <= v["end"]:
                continue
            if len(mine & _tokset(v)) >= 2:
                candidates.append({"new": u["id"], "new_line": u["start"], "old": v["id"],
                                   "old_line": v["start"],
                                   "shared": sorted(mine & _tokset(v))[:6],
                                   "link_basis": "keyword-overlap"})
                break
    # dedupe links
    seen, out = set(), []
    for lk in sorted(links, key=lambda x: (x["old_line"], x["new_line"] or 0, x["basis"],
                                           x["cite_line"])):
        key = (lk["old"], lk["new"], lk["applied"])
        if key in seen:
            continue
        seen.add(key)
        out.append(lk)
    unresolved.sort(key=lambda x: (x["line"], x["cite"]))
    candidates.sort(key=lambda x: (x["new_line"], x["old_line"]))
    return out, unresolved, candidates


def _contradictions(claims, links):
    groups = {}
    for c in claims:
        for f in c["facts"]:
            if f["field"] not in ("F1", "F1v", "F5") or not f.get("version"):
                continue
            key = (f["field"].rstrip("v"), f["version"], f.get("task") or "", f.get("ref") or "")
            groups.setdefault(key, []).append((str(f["value"]), c["unit_id"], c["claim_id"], f["line"]))
    linked = {(lk["old"], lk["new"]) for lk in links if lk["applied"]}
    linked |= {(b, a) for a, b in linked}
    out = []
    for key in sorted(groups):
        vals = {}
        for v, uid, cid, ln in sorted(groups[key], key=lambda x: x[3]):
            vals.setdefault(v, (uid, cid, ln))
        if len(vals) < 2:
            continue
        items = sorted(vals.items(), key=lambda x: x[1][2])
        uids = [x[1][0] for x in items]
        resolved = any((a, b) in linked for a in uids for b in uids if a != b)
        out.append({"field": key[0], "version": key[1], "task": key[2] or None,
                    "values": [{"value": v, "claim_id": x[1], "line": x[2]} for v, x in items],
                    "resolved_by_supersession": resolved})
    return out
