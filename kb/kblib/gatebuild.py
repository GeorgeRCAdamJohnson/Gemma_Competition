"""Gate builder (REV5 D5-26): `gate-build` / `gate-check`.

build_gate() creates exactly ONE new kernel dir G/submit_<name>/ from a frozen
base dir, applies a single-variable change-spec inside the NEW dir only, writes
GATE_MANIFEST.json + GATE_PREREG.md and returns the push command for the USER.
check_gate() verifies a dir it built (declared changes only, _assemble.py exit 0,
leakcheck clean, base untouched). Neither function writes anywhere else.

Safety (test-enforced):
- never imports kblib.kaggle and never runs the Kaggle CLI; the push command is
  only RETURNED as text (the user runs it).
- own write guard: _Guard.write() refuses any path outside a dir this process
  created (G/submit_<name>/); an existing target is refused up front.
- the only subprocess is `python _assemble.py` in the gate dir (gate-check).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from . import io, leak, paths

GATE_SCHEMA = "gemma-gate/1"
MANIFEST = "GATE_MANIFEST.json"
PREREG = "GATE_PREREG.md"
OWNER = "comfyops"
KERNEL_PREFIX = "gemma-gate-"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]{1,40}$")
# Printed for the USER only (never executed here).
_KAGGLE_EXE_HINT = (r"C:\Users\Biges\AppData\Local\Packages\PythonSoftwareFoundation."
                    r"Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\kaggle.exe")
_ASSEMBLE_TIMEOUT_S = 300
_TOOL_FILES = (MANIFEST, PREREG)
_TEXT_SUFFIXES = {".py", ".ipynb", ".md", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg"}
_HARNESS_SUFFIXES = {".py", ".ipynb"}
_AUDIT_JSON = re.compile(r"<!--\s*AUDIT-JSON\s*(\{.*?\})\s*-->", re.S)
_PASS_LINE = re.compile(r"Pass [12] \((?:AUDIT|REFUTE)\):.*?([A-Za-z]:\\[^\r\n]*?\.md)\s*$", re.M)


class GateError(Exception):
    """A refusal; str(e) is the reason printed by the CLI (exit 1)."""


class _Guard:
    """Writes only inside dirs this process created under G/submit_*."""

    def __init__(self, g: pathlib.Path):
        self.g = g.resolve()
        self.roots: list[pathlib.Path] = []

    def adopt_created(self, d: pathlib.Path) -> None:
        d = d.resolve()
        if d.parent != self.g or not d.name.startswith("submit_"):
            raise GateError(f"write guard: {d} is not a G\\submit_* dir")
        self.roots.append(d)

    def _check(self, p: pathlib.Path) -> pathlib.Path:
        p = p.resolve()
        for r in self.roots:
            if p == r or r in p.parents:
                return p
        raise GateError(f"write guard: {p} is outside the gate dir created by this process")

    def write(self, p: pathlib.Path, data: bytes | str) -> None:
        p = self._check(p)
        if isinstance(data, str):
            data = data.encode("utf-8")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def rmtree(self, d: pathlib.Path) -> None:
        d = d.resolve()
        if d not in self.roots:
            raise GateError(f"write guard: refusing to remove {d}")
        shutil.rmtree(d, ignore_errors=True)


# ----------------------------------------------------------------- file walking

def _ignored(dirpath: str, name: str) -> bool:
    if name.startswith("out") or name in ("results", "__pycache__") or name in _TOOL_FILES:
        return True
    if name.lower().endswith(".zip"):
        return True
    p = os.path.join(dirpath, name)
    try:
        return os.path.isfile(p) and os.path.getsize(p) > paths.LARGE_FILE_BYTES
    except OSError:
        return True


def _copy_ignore(dirpath, names):
    return [n for n in names if _ignored(dirpath, n)]


def _walk(root: pathlib.Path) -> dict:
    """rel POSIX -> absolute path for every non-ignored file under root."""
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if not _ignored(dp, d))
        for f in sorted(fns):
            if _ignored(dp, f):
                continue
            ap = pathlib.Path(dp) / f
            out[ap.relative_to(root).as_posix()] = ap
    return out


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snapshot(root: pathlib.Path) -> tuple[dict, dict]:
    files = _walk(root)
    return ({r: _sha(p) for r, p in files.items()},
            {r: p.stat().st_mtime_ns for r, p in files.items()})


# ------------------------------------------------------------------ audit / bar

def _first_line(p: pathlib.Path) -> str:
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    lines = text.lstrip("\ufeff").splitlines()
    return lines[0].rstrip("\r") if lines else ""


def _audit_json(p: pathlib.Path):
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _AUDIT_JSON.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def find_bar(final: pathlib.Path):
    """The PROCEED bar: the final report's own AUDIT-JSON, else pass 1, else pass 2."""
    cands = [final]
    try:
        cands += [pathlib.Path(m) for m in _PASS_LINE.findall(final.read_text(encoding="utf-8",
                                                                               errors="replace"))]
    except OSError:
        pass
    for c in cands:
        aj = _audit_json(c)
        if aj and isinstance(aj.get("bar"), dict):
            return aj["bar"], str(c)
    return None, None


# --------------------------------------------------------------- spec handling

def load_spec(spec_path: pathlib.Path) -> dict:
    try:
        spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GateError(f"change-spec unreadable: {e}")
    if not isinstance(spec, dict) or not isinstance(spec.get("variable"), str) \
            or not spec["variable"].strip():
        raise GateError("change-spec must be an object with one non-empty 'variable' "
                        "(single-variable rule)")
    ch = spec.get("changes")
    if not isinstance(ch, list) or not ch:
        raise GateError("change-spec 'changes' must be a non-empty list")
    for i, c in enumerate(ch):
        if not isinstance(c, dict) or not isinstance(c.get("file"), str):
            raise GateError(f"change {i}: needs a 'file'")
        kinds = ("old" in c and "new" in c, "replace_with_path" in c)
        if kinds.count(True) != 1:
            raise GateError(f"change {i}: exactly one of {{old,new}} or replace_with_path")
        if "variable" in c and c["variable"] != spec["variable"]:
            raise GateError(f"change {i}: variable {c['variable']!r} != spec variable "
                            f"{spec['variable']!r} (single-variable rule)")
        rel = c["file"].replace("\\", "/")
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
            raise GateError(f"change {i}: file must be relative inside the gate dir: {c['file']}")
        if pathlib.PurePosixPath(rel).name in _TOOL_FILES:
            raise GateError(f"change {i}: {rel} is tool-owned")
    return spec


def spec_files(spec: dict) -> list:
    return sorted({c["file"].replace("\\", "/") for c in spec["changes"]})


def _apply(guard: _Guard, d: pathlib.Path, spec: dict) -> list:
    applied = []
    for i, c in enumerate(spec["changes"]):
        rel = c["file"].replace("\\", "/")
        tgt = d / rel
        if "replace_with_path" in c:
            src = pathlib.Path(c["replace_with_path"])
            if not src.is_absolute():
                src = paths.gemma_root() / src
            if not src.is_file():
                raise GateError(f"change {i}: replace_with_path not a file: {src}")
            if d.resolve() in src.resolve().parents:
                raise GateError(f"change {i}: replace_with_path must not be inside the gate dir")
            data = src.read_bytes()
            if tgt.is_file() and tgt.read_bytes() == data:
                raise GateError(f"change {i}: {rel} already equals {src} (no change)")
            guard.write(tgt, data)
            kind = "replace_with_path"
        else:
            if not tgt.is_file():
                raise GateError(f"change {i}: {rel} does not exist in the base copy")
            try:
                text = tgt.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                raise GateError(f"change {i}: {rel} is not UTF-8 text")
            old, new = c["old"], c["new"]
            if old == new or not old:
                raise GateError(f"change {i}: old must be non-empty and differ from new")
            n = text.count(old)
            if n == 0 and "\r\n" in text:
                old, new = old.replace("\r\n", "\n").replace("\n", "\r\n"), \
                    new.replace("\r\n", "\n").replace("\n", "\r\n")
                n = text.count(old)
            if n != 1:
                raise GateError(f"change {i}: 'old' occurs {n} times in {rel} (need exactly 1)")
            guard.write(tgt, text.replace(old, new, 1).encode("utf-8"))
            kind = "replace"
        applied.append({"file": rel, "kind": kind, "sha256_after": _sha(tgt)})
    return applied


# ------------------------------------------------------------------ kernel ids

def local_kernel_ids(g: pathlib.Path) -> set:
    """Every kernel id named by a kernel-metadata.json under G (+ the newest
    pulled kernels list, if any). Read-only walk."""
    g = pathlib.Path(g)
    ids = set()
    skip_rel = {"local_eval/repos"}
    for dp, dns, fns in os.walk(g):
        rel = pathlib.Path(dp).relative_to(g).as_posix()
        depth = 0 if rel == "." else rel.count("/") + 1
        dns[:] = [x for x in dns
                  if x not in paths.SKIP_DIRS and not x.startswith(paths.SKIP_DIR_PREFIXES)
                  and x not in ("results", "traces", "node_modules", ".venv")
                  and ((rel + "/" + x) if rel != "." else x) not in skip_rel
                  and depth < paths.MAX_WALK_DEPTH]
        if "kernel-metadata.json" in fns:
            try:
                kid = json.loads((pathlib.Path(dp) / "kernel-metadata.json")
                                 .read_text(encoding="utf-8")).get("id")
            except (OSError, json.JSONDecodeError, AttributeError):
                kid = None
            if isinstance(kid, str):
                ids.add(kid.strip().lower())
    kl = g / "kb" / "pulled" / "kernels"
    if kl.is_dir():
        import csv
        files = sorted(kl.glob("*.csv"))
        if files:
            for r in csv.DictReader(files[-1].read_text(encoding="utf-8",
                                                        errors="replace").splitlines()):
                ref = (r.get("ref") or "").strip().lower()
                if ref:
                    ids.add(ref)
    return ids


def kernel_id_for(name: str) -> str:
    return f"{OWNER}/{KERNEL_PREFIX}{name.replace('_', '-')}"


def push_command(target: pathlib.Path) -> str:
    """Text for the USER to run. Never executed by this module."""
    exe = shutil.which("kaggle") or _KAGGLE_EXE_HINT
    return f'& "{exe}" kernels push -p "{target}"'


# ------------------------------------------------------------------- prereg

def _difficulty_maps(g: pathlib.Path):
    rich = {}
    p = g / "RICH_48_DIFFICULTY_MAP.md"
    if p.is_file():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            cells = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(cells) >= 6 and re.match(r"^[a-z]+_\d+$", cells[0]):
                rich[cells[0]] = cells[5].replace("*", "").strip()
    mech = {}
    tg = g / "kb" / "tasks_gold.json"
    if tg.is_file():
        try:
            tasks = json.loads(tg.read_text(encoding="utf-8")).get("tasks") or {}
            for tid, t in tasks.items():
                mech[tid] = ((t.get("difficulty") or {}).get("kb_mech_class")) or "?"
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    return rich, mech


def _prereg_md(g, target, base_rel, audit, bar_src, bar, spec, kid, push) -> str:
    rich, mech = _difficulty_maps(g)
    L = [f"# GATE PRE-REGISTRATION — {target.name}", "",
         "Written by `build_kb.py gate-build` BEFORE any run. A result that misses this bar is a "
         "FAILURE, reported as such.", "",
         "## The one change",
         f"- variable: `{spec['variable']}`",
         f"- base (frozen, read-only): `G\\{base_rel.replace('/', chr(92))}`",
         f"- kernel id: `{kid}`"]
    for c in spec["changes"]:
        how = (f"replace_with_path `{c['replace_with_path']}`" if "replace_with_path" in c
               else f"exact single-occurrence replacement ({len(c['old'])} -> {len(c['new'])} chars)")
        L.append(f"- `{c['file']}`: {how}")
    if spec.get("description"):
        L.append(f"- description: {spec['description']}")
    L += ["", "## Pass / fail bar (copied from the audit's AUDIT-JSON `bar`)",
          f"- audit (final, VERDICT: PROCEED): `{audit}`",
          f"- bar source: `{bar_src}`",
          f"- change (audit): {bar.get('change', '?')}",
          f"- PASS: {bar.get('pass', '?')}",
          f"- FAIL: {bar.get('fail', '?')}",
          f"- mechanism check: {bar.get('mechanism_check', '?')}", "",
          "## Task set (difficulty classes)",
          "| task | audit class | RICH_48 map class | KB mechanical class |",
          "|---|---|---|---|"]
    for t in bar.get("task_set") or []:
        tid = t.get("task", "?") if isinstance(t, dict) else str(t)
        cls = t.get("class", "?") if isinstance(t, dict) else "?"
        L.append(f"| {tid} | {cls} | {rich.get(tid, '-')} | {mech.get(tid, '-')} |")
    L += ["", "## Judge",
          "- FREE Kaggle rich gate (this kernel). The daily SCORED slot is NOT to be used until this "
          "bar has PASSED and the winning config has been re-confirmed alone.",
          "- Dev-internal stacks (local rig, sweeps, Colab) are hypotheses, never this judge.", "",
          "## Push (for the USER to run — the tooling never runs it)",
          "```", push, "```", ""]
    return "\n".join(L)


# -------------------------------------------------------------------- build

def build_gate(audit, base, name, spec_path, g=None) -> dict:
    g = pathlib.Path(g or paths.gemma_root()).resolve()
    audit = pathlib.Path(audit)
    if not audit.is_file():
        raise GateError(f"audit file not found: {audit}")
    if not audit.name.endswith("-final.md"):
        raise GateError("--audit must be the FINAL report (<date>-<slug>-final.md), "
                        "never a single pass")
    l1 = _first_line(audit)
    if l1 != "VERDICT: PROCEED":
        raise GateError(f"audit line 1 is {l1!r}, not 'VERDICT: PROCEED' — refusing")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise GateError(f"bad --name {name!r} (need ^[a-z0-9][a-z0-9_]{{1,40}}$)")
    target = g / f"submit_{name}"
    if target.exists():
        raise GateError(f"target exists: {target} (never modify an existing submit_* dir)")
    base_p = pathlib.Path(base)
    base_p = (base_p if base_p.is_absolute() else g / base_p).resolve()
    if g not in base_p.parents or not base_p.is_dir():
        raise GateError(f"--base must be an existing dir under G: {base}")
    if (g / "kb") == base_p or (g / "kb") in base_p.parents:
        raise GateError("--base must not be inside G\\kb")
    if not (base_p / "kernel-metadata.json").is_file():
        raise GateError("base has no kernel-metadata.json (a FREE gate needs a kernel dir)")
    base_rel = base_p.relative_to(g).as_posix()
    spec = load_spec(pathlib.Path(spec_path))
    bar, bar_src = find_bar(audit)
    if bar is None:
        raise GateError("no AUDIT-JSON 'bar' found in the final report or its pass reports")
    if bar.get("base_dir"):
        want = pathlib.Path(bar["base_dir"])
        want = (want if want.is_absolute() else g / want).resolve()
        if want != base_p:
            raise GateError(f"--base {base_rel} != the bar's base_dir {bar['base_dir']}")
    kid = kernel_id_for(name)
    if kid in local_kernel_ids(g):
        raise GateError(f"kernel id {kid} already exists locally — pick another --name")

    base_sha, base_mt = _snapshot(base_p)
    guard = _Guard(g)
    shutil.copytree(base_p, target, ignore=_copy_ignore)  # refuses an existing target
    guard.adopt_created(target)
    try:
        applied = _apply(guard, target, spec)
        km_p = target / "kernel-metadata.json"
        km = json.loads(km_p.read_text(encoding="utf-8"))
        km["id"] = kid
        km["title"] = f"Gemma Gate {name.replace('_', '-')}"
        guard.write(km_p, json.dumps(km, indent=2, ensure_ascii=False) + "\n")
        push = push_command(target)
        manifest = {
            "schema": GATE_SCHEMA, "target": target.name, "base": base_rel,
            "base_file_sha256": base_sha, "base_file_mtime_ns": base_mt,
            "created_utc": datetime.datetime.now(datetime.timezone.utc)
                                   .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "audit": str(audit), "bar_source": bar_src, "bar": bar,
            "change_spec": spec, "applied": applied, "kernel_id": kid,
            "code_file": km.get("code_file"),
        }
        guard.write(target / MANIFEST, io.dumps_json(manifest) + "\n")
        guard.write(target / PREREG, _prereg_md(g, target, base_rel, audit, bar_src, bar,
                                                 spec, kid, push))
    except Exception:
        guard.rmtree(target)
        raise
    return {"dir": str(target), "kernel_id": kid, "prereg": str(target / PREREG),
            "push": push, "applied": applied}


# -------------------------------------------------------------------- check

def _is_text(p: pathlib.Path) -> bool:
    if p.suffix.lower() not in _TEXT_SUFFIXES:
        return False
    try:
        b = p.read_bytes()
        b.decode("utf-8")
        return b"\x00" not in b
    except (OSError, UnicodeDecodeError):
        return False


def check_gate(d, g=None) -> tuple[bool, list]:
    g = pathlib.Path(g or paths.gemma_root()).resolve()
    d = pathlib.Path(d).resolve()
    lines = []

    def res(ok, what):
        lines.append(f"{'PASS' if ok else 'FAIL'} {what}")
        return ok

    mp = d / MANIFEST
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        res(False, f"manifest: {mp} unreadable ({e})")
        return False, lines
    ok = res(man.get("schema") == GATE_SCHEMA and man.get("target") == d.name
             and d.parent == g and d.name.startswith("submit_"),
             f"manifest: {d.name} holds its own {MANIFEST}")
    if not ok:
        return False, lines
    base_p = g / man["base"]
    spec = man["change_spec"]
    declared = set(spec_files(spec))
    code_file = man.get("code_file")

    # 1. _assemble.py (syntax gate) — runs first so its output is the checked state.
    if (d / "_assemble.py").is_file():
        try:
            cp = subprocess.run([sys.executable, "_assemble.py"], cwd=str(d),
                                capture_output=True, text=True, timeout=_ASSEMBLE_TIMEOUT_S,
                                shell=False)
            tail = (cp.stdout + cp.stderr).strip().splitlines()[-1:] or [""]
            ok &= res(cp.returncode == 0, f"_assemble.py exit {cp.returncode}: {tail[0][:160]}")
        except subprocess.TimeoutExpired:
            ok &= res(False, f"_assemble.py timed out after {_ASSEMBLE_TIMEOUT_S}s")
    else:
        lines.append("INFO no _assemble.py in the gate dir (nothing to assemble)")

    # 2. changed files == declared
    base_sha = man["base_file_sha256"]
    now = {r: _sha(p) for r, p in _walk(d).items()}
    changed = {r for r in set(base_sha) | set(now) if base_sha.get(r) != now.get(r)}
    derived = set()
    if code_file and code_file in changed and (d / "_assemble.py").is_file() \
            and code_file not in declared:
        derived.add(code_file)
    if "kernel-metadata.json" in changed and "kernel-metadata.json" not in declared:
        try:
            a = json.loads((base_p / "kernel-metadata.json").read_text(encoding="utf-8"))
            b = json.loads((d / "kernel-metadata.json").read_text(encoding="utf-8"))
            diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
            if diff <= {"id", "title"} and b.get("id") == man.get("kernel_id"):
                derived.add("kernel-metadata.json")
        except (OSError, json.JSONDecodeError):
            pass
    undeclared = sorted(changed - declared - derived)
    unchanged = sorted(declared - changed)
    ok &= res(not undeclared and not unchanged,
              f"changed files == spec files {sorted(declared)} (derived: {sorted(derived)}; "
              f"undeclared: {undeclared}; declared-but-unchanged: {unchanged})")

    # 3. leakcheck --scope config
    tasks = g / "comp_files" / "tasks.jsonl"
    if not tasks.is_file():
        ok &= res(False, f"leakcheck: {tasks} missing")
    else:
        targets = sorted((declared | derived) & set(now))
        targets += sorted(r for r in now if r.startswith("prompts/") and r.endswith(".md")
                          and r not in targets)
        hits_all = []
        for r in targets:
            p = d / r
            if not _is_text(p):
                continue
            text = p.read_text(encoding="utf-8")
            hits = leak.check(text, tasks, scope="config")
            if p.suffix.lower() in _HARNESS_SUFFIXES:
                # Kernel harness code selects the gate's tasks by id (not agent-
                # visible); gold lines / problem titles there still fail.
                tid = [h for h in hits if h["type"] == "task_id"]
                if tid:
                    lines.append(f"INFO {r}: {len(tid)} task id(s) in harness code "
                                 f"(gate task selection; not agent-visible)")
                hits = [h for h in hits if h["type"] != "task_id"]
            hits_all += [f"{r}: {h['type']} {h['text'][:60]}" for h in hits]
        for c in spec["changes"]:  # the change itself must not introduce any id/gold text
            if "new" in c:
                hits_all += [f"{c['file']} (change text): {h['type']} {h['text'][:60]}"
                             for h in leak.check(c["new"], tasks, scope="config")]
        ok &= res(not hits_all, f"leakcheck --scope config on {len(targets)} file(s)"
                  + (": " + "; ".join(hits_all[:10]) if hits_all else ""))

    # 4. base untouched
    cur_sha, cur_mt = _snapshot(base_p) if base_p.is_dir() else ({}, {})
    moved = sorted(r for r in set(base_sha) | set(cur_sha)
                   if base_sha.get(r) != cur_sha.get(r)
                   or man["base_file_mtime_ns"].get(r) != cur_mt.get(r))
    ok &= res(not moved, f"base {man['base']} hashes/mtimes unchanged"
              + (f" (changed: {moved[:10]})" if moved else ""))
    lines.append(("GATE-CHECK PASS " if ok else "GATE-CHECK FAIL ") + d.name)
    return ok, lines
