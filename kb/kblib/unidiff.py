"""Minimal unified-diff parser (design §6/§7.2).

Tolerates patches without `diff --git` headers; records hunks with old/new
ranges, added/removed/context lines, and the file list. Rejects `..` and
absolute paths in target names.
"""
from __future__ import annotations

import re

_FILE_OLD = re.compile(r"^--- (?:a/)?(.+?)\s*$")
_FILE_NEW = re.compile(r"^\+\+\+ (?:b/)?(.+?)\s*$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


class UniDiffError(Exception):
    pass


def _safe_path(p: str) -> str:
    if p == "/dev/null":
        return p
    if p.startswith("/") or ".." in p.split("/"):
        raise UniDiffError(f"unsafe path: {p}")
    return p


def parse(patch: str) -> list[dict]:
    """Return a list of file dicts: {old_path,new_path,hunks:[...]}."""
    lines = patch.split("\n")
    files = []
    cur = None
    hunk = None
    i = 0
    while i < len(lines):
        line = lines[i]
        mo = _FILE_OLD.match(line)
        if mo and i + 1 < len(lines) and _FILE_NEW.match(lines[i + 1]):
            if cur:
                files.append(cur)
            old = _safe_path(mo.group(1))
            new = _safe_path(_FILE_NEW.match(lines[i + 1]).group(1))
            cur = {"old_path": old, "new_path": new, "hunks": []}
            i += 2
            hunk = None
            continue
        mh = _HUNK.match(line)
        if mh and cur is not None:
            hunk = {
                "old_start": int(mh.group(1)),
                "old_len": int(mh.group(2) or 1),
                "new_start": int(mh.group(3)),
                "new_len": int(mh.group(4) or 1),
                "header": mh.group(5).strip(),
                "added": [], "removed": [], "context": [],
                # rp-5: new-side line numbers of '+' lines, and the new-side
                # line a '-' run sits before (removal anchor)
                "added_new_lines": [], "removed_at_new": [],
            }
            hunk["_new_no"] = hunk["new_start"]
            hunk["_old_seen"] = 0
            hunk["_new_seen"] = 0
            cur["hunks"].append(hunk)
            i += 1
            continue
        if hunk is not None and line and line[0] in "+- ":
            body = line[1:]
            if line[0] == "+":
                hunk["added"].append(body)
                hunk["added_new_lines"].append(hunk["_new_no"])
                hunk["_new_no"] += 1
                hunk["_new_seen"] += 1
            elif line[0] == "-":
                hunk["removed"].append(body)
                hunk["removed_at_new"].append(hunk["_new_no"])
                hunk["_old_seen"] += 1
            else:
                hunk["context"].append(body)
                hunk["_new_no"] += 1
                hunk["_new_seen"] += 1
                hunk["_old_seen"] += 1
        elif (hunk is not None and line == ""
              and (hunk["_new_seen"] < hunk["new_len"] or hunk["_old_seen"] < hunk["old_len"])):
            # a blank context line whose leading space was stripped: keep counting
            hunk["_new_no"] += 1
            hunk["_new_seen"] += 1
            hunk["_old_seen"] += 1
        i += 1
    for f in files + ([cur] if cur else []):
        for h in f["hunks"]:
            for k in ("_new_no", "_old_seen", "_new_seen"):
                h.pop(k, None)
    if cur:
        files.append(cur)
    return files
