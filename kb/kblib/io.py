"""Safe, deterministic I/O (design §4, §7).

safe_write is the ONLY write path. It enforces the write-boundary allowlist:
writes are permitted only under KB/ and only to generated-output locations, and
NEVER to curated/, proposals/, audits/, replays/manual/, submit_*, the log, or
.kiro/steering/*. A rejected target exits via SafeWriteError (CLI maps to exit 5).

Writes are atomic (temp + os.replace) and skip when new bytes equal existing
bytes (minimise OneDrive churn, idempotence). JSON dumps are deterministic
(sort_keys=True, ensure_ascii=False).
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time

from . import paths


class SafeWriteError(Exception):
    pass


# Relative-to-KB prefixes the builder is allowed to generate.
_ALLOWED_GENERATED = (
    "runs.jsonl",
    "tasks_gold.json",
    "near_miss.jsonl",
    "log_claims.md",
    "log_claims.jsonl",
    "KB_SUMMARY.md",
    "STANDING_TRUTHS.md",
    "build_meta.json",
    "build_stamp.json",
    "build_log.txt",
)
_ALLOWED_GENERATED_DIRS = (
    "replays/",
    "nearmiss_cache/",
    "pulled/",
)
# Exact generated files allowed inside an otherwise protected dir.
_ALLOWED_CURATED_EXACT = ("curated/_proposed_updates.md",)
# Hand-maintained / other-actor areas the builder must never write.
_PROTECTED_KB_DIRS = (
    "curated/",
    "proposals/",
    "audits/",
    "replays/manual/",
)


def _kb_rel(target: pathlib.Path) -> str:
    kb = paths.kb_root().resolve()
    t = target.resolve()
    try:
        return t.relative_to(kb).as_posix()
    except ValueError:
        raise SafeWriteError(f"target outside KB: {target}")


def _check_allowed(target: pathlib.Path) -> None:
    rel = _kb_rel(target)
    # REV5 D5-14: the ONE generated file under curated/ (exact path only;
    # every other curated/ path stays protected).
    if rel in _ALLOWED_CURATED_EXACT:
        return
    for prot in _PROTECTED_KB_DIRS:
        if rel == prot.rstrip("/") or rel.startswith(prot):
            raise SafeWriteError(f"protected path: {rel}")
    if rel in _ALLOWED_GENERATED:
        return
    for d in _ALLOWED_GENERATED_DIRS:
        if rel.startswith(d):
            return
    raise SafeWriteError(f"not an allowed generated output: {rel}")


def safe_write(target: pathlib.Path, data: bytes | str) -> bool:
    """Write bytes to target atomically. Returns True if bytes changed."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    _check_allowed(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            if target.read_bytes() == data:
                return False
        except OSError:
            pass
    tmp = target.with_suffix(target.suffix + f".tmp{os.getpid()}")
    last_err = None
    for _ in range(5):
        try:
            tmp.write_bytes(data)
            os.replace(tmp, target)
            return True
        except OSError as e:  # OneDrive can briefly lock files
            last_err = e
            time.sleep(0.2)
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    raise SafeWriteError(f"could not write {target}: {last_err}")


def dumps_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1)


def dumps_jsonl(rows: list) -> str:
    """One compact JSON object per line, deterministic key order."""
    return "".join(
        json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text_bomaware(p: pathlib.Path) -> tuple[str, int]:
    """Decode a file BOM-aware. Returns (text, replacement_count)."""
    raw = p.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), 0
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    return text, text.count("\ufffd")
