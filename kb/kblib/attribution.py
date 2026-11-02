"""Pulled-output attribution + pull targets (plan D5-10, D5-11). Pure, offline.

`kernels output` returns only the LATEST version of a kernel, so a pulled run is
never assumed to be the run behind any submission. For each submission mapped to
the pulled run (label/alias in the description, the Notebook-title slug, a local
submission zip with equal package hashes, or an explicit --for-ref) we compare:

  * the description's stated config facts (temperature X, top_k N, thinking N,
    budget quad a/b/c/d, max_tool_calls N, model token) with the pulled config;
  * the local submission zip's package hashes with the pulled package.

  ATTRIBUTION-CONFIRMED   package hashes equal (and no stated fact differs)
  ATTRIBUTION-MISMATCH    any stated fact or package file differs -> the pull
                          never explains that ref
  ATTRIBUTION-UNVERIFIED  nothing to compare (no stated facts differ, no zip)
"""
from __future__ import annotations

import csv
import hashlib
import io as _io
import pathlib
import re
import zipfile

AT_VERSION = "at-1"

CONFIRMED = "ATTRIBUTION-CONFIRMED"
MISMATCH = "ATTRIBUTION-MISMATCH"
UNVERIFIED = "ATTRIBUTION-UNVERIFIED"

_MODEL_TOK = re.compile(r"(?i)(?<![a-z0-9])(31b|e4b|e2b|12b)(?![a-z0-9])")
_ARROW_MODEL = re.compile(r"(?i)->\s*gemma-4-(31b|e4b|e2b|12b)\b")
_NUM = r"(\d+(?:\.\d+)?)"
_FACT_RES = {
    "temperature": re.compile(r"(?i)\btemp(?:erature)?\s*[=:]?\s*" + _NUM
                              + r"(?:\s*->\s*" + _NUM + r")?"),
    "top_k": re.compile(r"(?i)\btop[_ ]?k\s*[=:]?\s*(\d+)(?:\s*->\s*(\d+))?"),
    "thinking_budget": re.compile(r"(?i)\bthinking(?:[_ ]budget)?\s*[=:]?\s*(\d+)"
                                  r"(?:\s*->\s*(\d+))?"),
    "max_tool_calls": re.compile(r"(?i)\bmax_tool_calls\s*[=:]?\s*(\d+)(?:\s*->\s*(\d+))?"),
}
_QUAD = re.compile(r"(?<![\d/.])(\d{1,3})/(\d{1,3})/(\d{1,4})/(\d{2,4})(?![\d/])")
_QUAD_KEYS = ("max_tool_calls", "max_time_minutes", "max_turns", "timeout_seconds")
_NOTEBOOK = re.compile(r"^\s*Notebook\s+(.+?)\s*\|\s*Version\s+(\d+)\s*$")
_TITLE_VER = re.compile(r"^\s*(.+?)\s+-\s+Version\s+(\d+)\s*$")
_VERSIONISH = re.compile(r"^(?:v\d+[a-z0-9]*|a\d{1,2}|ca\d+|d\d|e\d|p\d|off12|b12|m\d+)$")
_PKG_FIXED = ("agent.yaml", "eval_config.yaml", "configs/sampling.yaml")


# ----------------------------------------------------------------- descriptions

def model_family(s) -> str | None:
    if not s:
        return None
    m = _MODEL_TOK.search(str(s))
    return m.group(1).lower() if m else None


def description_model(desc: str) -> str | None:
    """Model a submission description names: an explicit `-> gemma-4-<m>-it`
    switch wins, else the first model token, else None (untagged)."""
    m = _ARROW_MODEL.search(desc or "")
    if m:
        return m.group(1).lower()
    return model_family(desc)


def description_track(desc: str) -> str:
    m = description_model(desc)
    if m in ("e4b", "e2b"):
        return "small-model"
    if m == "12b":
        return "dev-proxy"
    return "main"           # 31B or untagged (the Kaggle default model)


def description_facts(desc: str) -> dict:
    """Stated config facts; a field stated with two different values is dropped
    into `_ambiguous` (never guessed). `a -> b` means the value became b."""
    desc = desc or ""
    facts, amb = {}, []

    def put(k, v):
        if k in facts and facts[k] != v:
            amb.append(k)
        facts.setdefault(k, v)

    for k, rx in _FACT_RES.items():
        for m in rx.finditer(desc):
            val = m.group(2) or m.group(1)
            put(k, float(val) if k == "temperature" else int(val))
    for m in _QUAD.finditer(desc):
        for k, v in zip(_QUAD_KEYS, m.groups()):
            put(k, int(v))
    mod = description_model(desc)
    if mod:
        facts["model"] = mod
    for k in sorted(set(amb)):
        facts.pop(k, None)
    if amb:
        facts["_ambiguous"] = sorted(set(amb))
    return facts


def notebook_slug(desc: str) -> str | None:
    """`Notebook <Title> | Version N` / `<Title> - Version N` -> kernel slug."""
    for rx in (_NOTEBOOK, _TITLE_VER):
        m = rx.match((desc or "").strip())
        if m:
            return slugify(m.group(1))
    return None


def slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s


# ---------------------------------------------------------------------- hashes

def _h(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _member_ok(name: str) -> bool:
    return name in _PKG_FIXED or (
        name.startswith("prompts/") and name.endswith(".md") and name.count("/") == 1)


def zip_hashes(zip_path) -> dict | None:
    """Package-member hashes of a submission zip, read in memory (LF-normalised)."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            out = {}
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if info.is_dir() or not _member_ok(name):
                    continue
                out[name] = _h(zf.read(info))
            return out
    except (zipfile.BadZipFile, OSError):
        return None


def dir_hashes(pkg_dir) -> dict | None:
    pkg_dir = pathlib.Path(pkg_dir)
    if not pkg_dir.is_dir():
        return None
    out = {}
    for rel in _PKG_FIXED:
        p = pkg_dir / rel
        if p.is_file():
            out[rel] = _h(p.read_bytes())
    pd = pkg_dir / "prompts"
    if pd.is_dir():
        for p in sorted(pd.glob("*.md")):
            out["prompts/" + p.name] = _h(p.read_bytes())
    return out or None


def pulled_package_hashes(run_dir) -> dict | None:
    run_dir = pathlib.Path(run_dir)
    if (run_dir / "submission.zip").is_file():
        z = zip_hashes(run_dir / "submission.zip")
        if z:
            return z
    return dir_hashes(run_dir / "submission")


def local_submission_zips(g) -> dict:
    """{ref: G-rel path} for local_eval/pull_submissions/<ref>_<desc>.zip."""
    d = pathlib.Path(g) / "local_eval" / "pull_submissions"
    out = {}
    if d.is_dir():
        for p in sorted(d.glob("*.zip")):
            m = re.match(r"^(\d{6,10})_", p.name)
            if m:
                out[m.group(1)] = "local_eval/pull_submissions/" + p.name
    return out


# ------------------------------------------------------------------ attribution

def _fmt(v):
    if v is None:
        return "unset"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def compare_facts(pulled_cfg: dict, facts: dict) -> list:
    """Fields where the pulled config differs from a stated fact."""
    out = []
    for k in sorted(facts):
        if k.startswith("_"):
            continue
        want = facts[k]
        if k == "model":
            have = model_family(pulled_cfg.get("model"))
        else:
            have = pulled_cfg.get(k)
        if have is None:
            continue    # pulled side unset: not comparable (defaults unknown)
        try:
            same = float(have) == float(want) if k != "model" else have == want
        except (TypeError, ValueError):
            same = str(have) == str(want)
        if not same:
            out.append(f"{k}: pulled {_fmt(have)} vs submission {_fmt(want)}")
    return out


def label_aliases(label: str) -> list:
    """Tokens a submission description may use for a run label."""
    label = (label or "").lower()
    out = {label} if label else set()
    base = label[len("packager-"):] if label.startswith("packager-") else label
    if base:
        out.add(base)
    for tok in re.split(r"[-_]", base):
        if _VERSIONISH.match(tok):
            out.add(tok)
            break
    return sorted(t for t in out if t and t != "packager")


def _mentions(desc: str, token: str) -> bool:
    """Whole-token mention. Version tokens `v<N>...` are matched with a lowercase
    `v` only ("V1" in prose means a kernel version, not the v1 run); other
    tokens (A25, ca5, E4B) are case-insensitive."""
    t = re.escape(token[1:]) if token[:1] == "v" else None
    if t is not None and re.match(r"v\d", token):
        rx = r"(?<![A-Za-z0-9])v(?i:" + t + r")(?![A-Za-z0-9])"
    else:
        rx = r"(?i)(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
    return re.search(rx, desc or "") is not None


def map_refs(label, slug, sub_rows, pulled_hashes, zip_hash_by_ref, for_ref=None):
    """Submissions this pulled run could be claimed to explain, with how."""
    aliases = label_aliases(label)
    out = []
    for r in sub_rows:
        ref = str(r.get("ref", ""))
        desc = r.get("description", "") or ""
        how = []
        if for_ref and ref == str(for_ref):
            how.append("--for-ref")
        nb = notebook_slug(desc)
        if slug and nb and nb == slug:
            how.append("notebook-title slug")
        hit = [a for a in aliases if _mentions(desc, a)]
        if hit:
            how.append("description mentions " + "/".join(hit))
        zh = zip_hash_by_ref.get(ref)
        if pulled_hashes and zh and zh == pulled_hashes:
            how.append("local zip hash-equal")
        if how:
            out.append((r, how))
    return out


def attribute(pulled_cfg, pulled_hashes, mapped, zip_hash_by_ref, zip_path_by_ref):
    """mapped: [(sub_row, how)] -> sorted list of per-ref attribution records."""
    recs = []
    for r, how in mapped:
        ref = str(r.get("ref", ""))
        facts = description_facts(r.get("description", ""))
        diffs = compare_facts(pulled_cfg or {}, facts)
        zh = zip_hash_by_ref.get(ref)
        zdiff = []
        if zh is not None and pulled_hashes is not None:
            zdiff = sorted(k for k in set(zh) | set(pulled_hashes)
                           if zh.get(k) != pulled_hashes.get(k))
        if diffs or zdiff:
            parts = diffs + ([f"package files differ from {zip_path_by_ref[ref]}: {zdiff}"]
                             if zdiff else [])
            flag = MISMATCH
            detail = (f"{MISMATCH}: pulled output does not explain ref {ref} ("
                      + "; ".join(parts) + ")")
        elif zh is not None and pulled_hashes is not None:
            flag = CONFIRMED
            detail = f"{CONFIRMED}: package hashes equal {zip_path_by_ref[ref]}"
        else:
            flag = UNVERIFIED
            why = []
            why.append("no stated config fact differs" if facts else
                       "description states no config facts")
            why.append("no local submission zip for this ref" if zh is None else
                       "pulled run has no package to hash")
            detail = f"{UNVERIFIED}: " + "; ".join(why)
        recs.append({"ref": ref, "flag": flag, "detail": detail, "mapped_by": how,
                     "stated_facts": {k: v for k, v in facts.items()},
                     "status": r.get("status", ""), "publicScore": r.get("publicScore", "")})
    recs.sort(key=lambda x: x["ref"])
    return recs


# ------------------------------------------------------------------ pull targets

def read_csv_rows(path) -> list:
    p = pathlib.Path(path)
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    return [dict(r) for r in csv.DictReader(_io.StringIO(text))]


def newest_kernels_list(kb):
    d = pathlib.Path(kb) / "pulled" / "kernels"
    files = sorted(d.glob("*.csv")) if d.is_dir() else []
    if not files:
        return [], None
    return read_csv_rows(files[-1]), "pulled/kernels/" + files[-1].name


def local_output_slugs(g, disc) -> set:
    """Kernel slugs (no owner) that already have an output on disk."""
    g = pathlib.Path(g)
    kd = disc.get("kernel_dirs", {})
    out = set()
    dirs = (disc.get("run_dirs", []) + disc.get("eval_runs", []) + disc.get("failed_run_dirs", [])
            + disc.get("empty_run_dirs", []) + disc.get("pulled_runs", [])
            + disc.get("scored_zips", []))
    for rd in dirs:
        parts = rd.split("/")
        for i in range(len(parts), 0, -1):
            cand = "/".join(parts[:i])
            if cand in kd:
                out.add(kd[cand]["id"].split("/", 1)[-1])
                break
        d = g / rd
        for lf in sorted(d.glob("*.log")):
            out.add(lf.stem.lower())
    pulled = g / "kb" / "pulled"
    if pulled.is_dir():
        for c in pulled.iterdir():
            if c.is_dir() and any((x / "_pull_meta.json").is_file()
                                  for x in c.iterdir() if x.is_dir()):
                out.add(c.name)
    return out


def _date(r):
    return r.get("date", "") or ""


def pull_targets(g, snapshot_rows, kernels_list_rows, local_slugs, kernel_dirs,
                 log_text, force=False):
    """D5-11 targets -> ([{slug, reason, kind}], notes). Deterministic order:
    (a) producers of COMPLETE/ERROR refs, newest ref first; (b) local kernel dirs
    whose label appears in the log, listed by Kaggle, with no local output."""
    listed = {}
    for r in kernels_list_rows:
        ref = (r.get("ref") or "").strip()
        if ref.startswith("comfyops/"):
            listed[ref.split("/", 1)[1]] = r
    notes = []
    if not listed:
        notes.append("no kernels-list snapshot: producers cannot be confirmed; "
                     "no targets (run `pull --submissions` first)")
        return [], notes
    if len(kernels_list_rows) >= 100:
        notes.append(f"kernels list has {len(kernels_list_rows)} rows (>= 100: the "
                     "server may cap the page; kernels beyond it are unseen)")
    targets, seen = [], set()

    def add(slug, reason, kind):
        if slug in seen:
            return
        if slug in local_slugs and not force:
            notes.append(f"skip {slug}: an output for this slug is already on disk "
                         f"(candidate kind {kind})")
            seen.add(slug)
            return
        seen.add(slug)
        targets.append({"slug": "comfyops/" + slug, "reason": reason, "kind": kind})

    rows = sorted((r for r in snapshot_rows
                   if any(s in (r.get("status") or "") for s in ("COMPLETE", "ERROR"))),
                  key=lambda r: (_date(r), str(r.get("ref", ""))), reverse=True)
    unknown = []
    for r in rows:
        ref = str(r.get("ref", ""))
        desc = r.get("description", "") or ""
        cands = []
        nb = notebook_slug(desc)
        if nb and nb in listed:
            cands.append((nb, "notebook-title slug"))
        dmodel = description_model(desc) or "31b"
        for slug in sorted(listed):
            if not (slug.startswith("gemma-") or "full129" in slug):
                continue
            label = _label_from_slug(slug)
            smodel = model_family(slug)
            if smodel and smodel != dmodel:
                continue
            hit = [a for a in label_aliases(label) if a not in ("31b", "e4b", "e2b", "12b")
                   and _mentions(desc, a)]
            if hit:
                cands.append((slug, "description mentions " + "/".join(hit)))
        if not cands:
            unknown.append(ref)
        for slug, how in cands:
            add(slug, f"producer candidate of ref {ref} ({r.get('status', '')} "
                      f"{r.get('publicScore', '') or '-'}; {how})", "scored-ref")
    if unknown:
        notes.append("refs with no identifiable producing kernel (description names none): "
                     + ", ".join(unknown))
    # (b) local kernel dirs with a kernel id, listed by Kaggle, label in the log
    for kdir in sorted(kernel_dirs):
        slug = kernel_dirs[kdir]["id"].split("/", 1)[-1]
        if slug not in listed:
            continue
        label = _label_from_slug(slug)
        if label and _mentions(log_text, label):
            add(slug, f"log names {label}; kernel dir {kdir}; no output for this slug "
                      f"on disk", "log-version")
    return targets, notes


def _label_from_slug(slug):
    slug = slug.split("/", 1)[-1]
    if slug.startswith("gemma-sibling-conform-"):
        return slug[len("gemma-sibling-conform-"):]
    if slug.startswith("gemma-submission-packager"):
        return "packager" + slug[len("gemma-submission-packager"):]
    return slug
