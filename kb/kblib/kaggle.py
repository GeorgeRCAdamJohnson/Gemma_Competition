"""Read-only Kaggle pulls (design R5.5 / plan D5-9). Invoked ONLY by `build_kb.py pull`.

The Kaggle CLI is called through `subprocess.run(<argv list>)` (never through a
shell). Every argv is checked by `validate_argv` against an exact allowlist of
read-only commands; anything else (an upload/submit verb, a versioned kernel ref
`owner/slug/N`, a foreign owner, an output path outside kb/pulled/) raises
ArgvError before any process starts.

Layout written (and nothing else):
  kb/pulled/submissions/<utc>.csv (+ <utc>.meta.json)    submissions snapshot
  kb/pulled/kernels/<utc>.csv (+ <utc>.meta.json)        `kernels list --mine`
  kb/pulled/cli/kernels_output_help.txt                  `kernels output --help`
  kb/pulled/<slug>/<utc>.partial/ -> <utc>/              one kernel output pull
     <kernel output files>, source/ (kernels pull -m), _pull_meta.json
  kb/pulled/<slug>/<utc>.failed.json                     a failed output pull

`kernels output` returns only the LATEST kernel version, so every pull is
`latest_only: true`; attribution to a submission is decided by the build
(kblib/attribution.py), never assumed here.

The build never imports this module (pure helpers live in attribution.py).
"""
from __future__ import annotations

import csv
import datetime
import io as _io
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

from . import io, paths

KAGGLE_EXE = (r"C:\Users\Biges\AppData\Local\Packages\PythonSoftwareFoundation."
              r"Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\kaggle.exe")
COMPETITION = "gemma-4-developer-agent"
OWNER = "comfyops"
TIMEOUT_S = 600

_SLUG_RE = re.compile(r"^comfyops/[a-z0-9][a-z0-9-]*$")
# Downloads everything except large-binary extensions (the post-download sweep
# still runs: a .safetensors <= 50 MB is kept only if the pattern is unsupported).
NO_BINARIES_PATTERN = r"^(?!.*\.(?:safetensors|bin|gguf|pt|pth)$).*$"
_BINARY_EXTS = (".bin", ".gguf", ".pt", ".pth")
_SAFETENSORS_MAX = 50 * 1024 * 1024

# The exact read-only argv shapes ('<slug>', '<dir>', '<re>' are placeholders).
ALLOWED_TEMPLATES = (
    ("competitions", "submissions", COMPETITION, "--csv"),
    ("kernels", "list", "--mine", "--csv", "--page-size", "200"),
    ("kernels", "output", "--help"),
    ("kernels", "output", "<slug>", "-p", "<dir>"),
    ("kernels", "output", "<slug>", "-p", "<dir>", "--file-pattern", "<re>"),
    ("kernels", "pull", "<slug>", "-p", "<dir>", "-m"),
)


class ArgvError(ValueError):
    pass


def utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_slug(s: str) -> str:
    """'x' -> 'comfyops/x'; validates owner and rejects a /N version suffix."""
    s = (s or "").strip()
    if "/" not in s:
        s = OWNER + "/" + s
    if not _SLUG_RE.match(s):
        raise ArgvError(f"bad kernel ref {s!r}: must be comfyops/<slug> "
                        "(lowercase, no /N version suffix, no other owner)")
    return s


def slug_dirname(slug: str) -> str:
    return normalize_slug(slug).split("/", 1)[1]


def _dir_ok(d: str) -> bool:
    pulled = (paths.kb_root() / "pulled").resolve()
    try:
        pathlib.Path(d).resolve().relative_to(pulled)
        return True
    except ValueError:
        return False


def validate_argv(argv) -> list:
    """Return argv (as a list of str) iff it matches an allowed template exactly."""
    argv = [str(a) for a in argv]
    for tpl in ALLOWED_TEMPLATES:
        if len(tpl) != len(argv):
            continue
        ok = True
        for t, a in zip(tpl, argv):
            if t == "<slug>":
                ok = bool(_SLUG_RE.match(a))
            elif t == "<dir>":
                ok = _dir_ok(a)
            elif t == "<re>":
                try:
                    re.compile(a)
                    ok = not a.startswith("-")
                except re.error:
                    ok = False
            else:
                ok = (t == a)
            if not ok:
                break
        if ok:
            return argv
    raise ArgvError(f"argv not in the read-only allowlist: {argv!r}")


def run(argv, dry_run=False):
    """Run one allowed kaggle CLI call. Returns {argv, exit, output_text}.

    stdout+stderr go to a TEMP scratch file (removed afterwards); never a shell.
    """
    argv = validate_argv(argv)
    if dry_run:
        return {"argv": argv, "exit": None, "output_text": "", "dry_run": True}
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    fd, tmp = tempfile.mkstemp(prefix="gkb_kaggle_", suffix=".txt")
    os.close(fd)
    try:
        with open(tmp, "wb") as fh:
            try:
                cp = subprocess.run([KAGGLE_EXE] + argv, stdout=fh,
                                    stderr=subprocess.STDOUT, env=env,
                                    timeout=TIMEOUT_S, shell=False)
                code = cp.returncode
            except subprocess.TimeoutExpired:
                code = -9
            except OSError as e:
                fh.write(f"OSError starting kaggle CLI: {e}".encode("utf-8"))
                code = -1
        text = pathlib.Path(tmp).read_bytes().decode("utf-8", errors="replace")
        if code == -9:
            text += f"\n[gkb] TIMEOUT after {TIMEOUT_S}s"
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return {"argv": argv, "exit": code, "output_text": text}


# ------------------------------------------------------------------ helpers

def _csv_body(text: str, header_start: str) -> str | None:
    """Strip CLI warnings printed before the CSV header."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith(header_start):
            body = "\n".join(lines[i:]).rstrip("\n") + "\n"
            return body
    return None


def _snapshot(kind, argv, header_start, dry_run, utc):
    kb = paths.kb_root()
    res = run(argv, dry_run=dry_run)
    if dry_run:
        return res
    body = _csv_body(res["output_text"], header_start) if res["exit"] == 0 else None
    meta = {"kind": kind, "pull_utc": utc, "argv": res["argv"], "exit": res["exit"],
            "ok": body is not None,
            "output_text": res["output_text"][:2000] if body is None else ""}
    if body is not None:
        io.safe_write(kb / "pulled" / kind / f"{utc}.csv", body)
        meta["csv"] = f"pulled/{kind}/{utc}.csv"
        meta["rows"] = sum(1 for _ in csv.DictReader(_io.StringIO(body)))
        meta["sha256"] = io.sha256_text(body)
    io.safe_write(kb / "pulled" / kind / f"{utc}.meta.json", io.dumps_json(meta))
    res["meta"] = meta
    return res


def pull_submissions(dry_run=False, utc=None):
    return _snapshot("submissions", ["competitions", "submissions", COMPETITION, "--csv"],
                     "ref,", dry_run, utc or utc_stamp())


def list_mine(dry_run=False, utc=None):
    return _snapshot("kernels", ["kernels", "list", "--mine", "--csv", "--page-size", "200"],
                     "ref,", dry_run, utc or utc_stamp())


def help_text_path() -> pathlib.Path:
    return paths.kb_root() / "pulled" / "cli" / "kernels_output_help.txt"


def has_file_pattern(dry_run=False) -> bool:
    """Parse the saved `kernels output --help` text (fetch it once if absent)."""
    p = help_text_path()
    if not p.is_file():
        if dry_run:
            return False
        res = run(["kernels", "output", "--help"])
        if res["exit"] != 0:
            return False
        io.safe_write(p, res["output_text"])
    return "--file-pattern" in p.read_text(encoding="utf-8", errors="replace")


def already_pulled(slug) -> list:
    """Completed pulls of this slug (dirs with _pull_meta.json), sorted."""
    d = paths.kb_root() / "pulled" / slug_dirname(slug)
    if not d.is_dir():
        return []
    return sorted(c.name for c in d.iterdir()
                  if c.is_dir() and not c.name.endswith(".partial")
                  and (c / "_pull_meta.json").is_file())


def _sweep_binaries(base: pathlib.Path) -> list:
    deleted = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        size = p.stat().st_size
        if ext in _BINARY_EXTS or (ext == ".safetensors" and size > _SAFETENSORS_MAX):
            deleted.append({"path": p.relative_to(base).as_posix(), "size": size})
            p.unlink()
    return deleted


def _pulled_config(base: pathlib.Path):
    from . import configs, sources
    sub = base / "submission"
    if sub.is_dir():
        return configs.extract_config(sub, "pulled submission folder")
    adir = sources.agent_dir_config(base)
    if adir is not None:
        return configs.extract_config(adir, f"pulled agent dir {adir.name}")
    return configs.extract_config(None)


def output_argv(slug, out_dir, file_pattern):
    a = ["kernels", "output", normalize_slug(slug), "-p", str(out_dir)]
    if file_pattern:
        a += ["--file-pattern", NO_BINARIES_PATTERN]
    return a


def pull_argv(slug, src_dir):
    return ["kernels", "pull", normalize_slug(slug), "-p", str(src_dir), "-m"]


def pull_output(slug, for_ref=None, dry_run=False, file_pattern=None):
    """Download the LATEST output + source of comfyops/<slug> into kb/pulled/."""
    slug = normalize_slug(slug)
    kb = paths.kb_root()
    utc = utc_stamp()
    sdir = kb / "pulled" / slug_dirname(slug)
    base = sdir / f"{utc}.partial"
    if file_pattern is None:
        file_pattern = has_file_pattern(dry_run=dry_run)
    a_out = validate_argv(output_argv(slug, base, file_pattern))
    a_src = validate_argv(pull_argv(slug, base / "source"))
    if dry_run:
        return {"slug": slug, "dry_run": True, "argv": [a_out, a_src]}
    io._check_allowed(base / "_pull_meta.json")       # boundary check before mkdir
    base.mkdir(parents=True, exist_ok=False)          # this process owns base
    r_out = run(a_out)
    (base / "source").mkdir(exist_ok=True)
    r_src = run(a_src)
    deleted = _sweep_binaries(base)
    files = sorted(({"path": p.relative_to(base).as_posix(), "size": p.stat().st_size}
                    for p in base.rglob("*") if p.is_file()), key=lambda f: f["path"])
    out_files = [f for f in files if not f["path"].startswith("source/")]
    meta = {"slug": slug, "pull_utc": utc, "latest_only": True, "for_ref": for_ref,
            "argv": [r_out["argv"], r_src["argv"]],
            "exit": r_out["exit"], "source_exit": r_src["exit"],
            "output_text": r_out["output_text"][-4000:],
            "source_output_text": r_src["output_text"][-2000:],
            "files": files, "deleted": deleted,
            "file_pattern": NO_BINARIES_PATTERN if file_pattern else None}
    ok = r_out["exit"] == 0 and bool(out_files)
    if not ok:
        # a failed pull is recorded, never left as data: remove what we created
        shutil.rmtree(base, ignore_errors=True)
        meta["ok"] = False
        io.safe_write(sdir / f"{utc}.failed.json", io.dumps_json(meta))
        return meta
    meta["ok"] = True
    meta["submission_config"] = _pulled_config(base)
    io.safe_write(base / "_pull_meta.json", io.dumps_json(meta))
    finalize_partial(base)
    return meta


def finalize_partial(base: pathlib.Path) -> pathlib.Path:
    """Rename <utc>.partial -> <utc>. OneDrive briefly locks freshly written
    dirs (WinError 5), so retry, then fall back to copy + remove. Only a
    .partial dir holding an ok _pull_meta.json (written by this tool) is
    finalized."""
    import json as _json
    import time
    base = pathlib.Path(base)
    if not base.name.endswith(".partial"):
        raise ValueError(f"not a .partial dir: {base}")
    io._check_allowed(base / "_pull_meta.json")
    meta = _json.loads((base / "_pull_meta.json").read_text(encoding="utf-8"))
    if not meta.get("ok"):
        raise ValueError(f"refusing to finalize a failed pull: {base}")
    final = base.with_name(base.name[:-len(".partial")])
    last = None
    for _ in range(20):
        try:
            base.rename(final)
            return final
        except PermissionError as e:
            last = e
            time.sleep(1.0)
    if final.exists():
        raise OSError(f"cannot finalize {base}: {final} exists ({last})")
    shutil.copytree(base, final)
    shutil.rmtree(base, ignore_errors=True)
    return final


def leftover_partials() -> list:
    """Completed (ok meta) .partial dirs left behind by an interrupted run."""
    pulled = paths.kb_root() / "pulled"
    out = []
    if pulled.is_dir():
        for p in sorted(pulled.glob("*/*.partial")):
            mp = p / "_pull_meta.json"
            if mp.is_file():
                try:
                    import json as _json
                    if _json.loads(mp.read_text(encoding="utf-8")).get("ok"):
                        out.append(p)
                except ValueError:
                    pass
    return out
