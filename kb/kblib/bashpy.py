"""Bash front-end for static edit reconstruction (design §8.1).

Turns a `run_command` command string into a list of simple commands and the
*effects* each would have, WITHOUT executing anything. Heredocs are extracted
first (so a junk terminator like `PY'` lands inside the Python body, as bash
does), then the remainder is tokenized with shlex and split on `; && || |`.

This module imports no subprocess / os process API and contains no exec/eval/
compile(..., "exec") (test-enforced). Its output feeds reconstruct.PyEval.
"""
from __future__ import annotations

import re
import shlex

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
_READ_ONLY_CMDS = {"cat", "sed", "head", "tail", "nl", "grep", "ls", "find",
                   "pytest", "echo", "true", "pwd", "wc", "diff"}
_MUTATION_CMDS = {"mv", "cp", "rm", "patch", "perl", "awk"}


class Effect:
    """One modelled effect of a simple command."""
    __slots__ = ("kind", "payload", "snippet", "reason", "path")

    def __init__(self, kind, payload=None, snippet=None, reason=None, path=None):
        self.kind = kind          # python-exec | file-write | sed-sub | read-only | unmodeled | bash-error
        self.payload = payload    # python source / written text / (old,new,global)
        self.snippet = snippet
        self.reason = reason
        self.path = path


def _normalize_path(raw: str):
    """Strip /workspace/ and leading /, reject .. and .git. Returns (path|None, unsafe_reason|None)."""
    p = raw.strip().strip("'\"")
    if p.startswith("/workspace/"):
        p = p[len("/workspace/"):]
    p = p.lstrip("/")
    parts = [x for x in p.replace("\\", "/").split("/") if x]
    if ".." in parts:
        return None, "UNSAFE_PATH (.. component)"
    if parts and parts[0] == ".git":
        return None, "UNSAFE_PATH (.git)"
    return "/".join(parts), None


def _extract_heredocs(command: str):
    """Return (lines_without_bodies_joined, {token: body}, unterminated_flag)."""
    lines = command.split("\n")
    bodies = {}
    out_lines = []
    i = 0
    tok_n = 0
    unterminated = False
    while i < len(lines):
        line = lines[i]
        m = _HEREDOC.search(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        quoted = bool(m.group(1))
        delim = m.group(2)
        strip_tabs = line[m.start():m.start() + 3].startswith("<<-")
        token = f"__GKB_HEREDOC_{tok_n}__"
        tok_n += 1
        # the command line with the heredoc operator replaced by a placeholder
        out_lines.append(line[:m.start()] + token + line[m.end():])
        body = []
        j = i + 1
        found = False
        while j < len(lines):
            bl = lines[j]
            cmp_bl = bl.lstrip("\t") if strip_tabs else bl
            if cmp_bl.rstrip() == delim:
                found = True
                j += 1
                break
            body.append(bl)
            j += 1
        if not found:
            unterminated = True
        text = "\n".join(body)
        if not quoted:
            # limited expansion handling: line-continuation and simple escapes
            text = text.replace("\\\n", "").replace("\\\\", "\\")
            text = text.replace("\\$", "$").replace("\\`", "`")
        bodies[token] = {"text": text, "quoted": quoted,
                         "unterminated_in": not found}
        i = j
    return "\n".join(out_lines), bodies, unterminated


def _simple_commands(remainder: str):
    """Split the (heredoc-stripped) remainder into simple commands.

    Returns a list of token lists, one per simple command. shlex failure raises
    BashTokenizeError.
    """
    # split on separators at top level by first tokenizing with punctuation_chars
    try:
        lex = shlex.shlex(remainder, posix=True, punctuation_chars=";&|<>")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError as e:
        raise BashTokenizeError(str(e))
    cmds = []
    cur = []
    seps = {";", "&&", "||", "|", "&"}
    for t in toks:
        if t in seps:
            if cur:
                cmds.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        cmds.append(cur)
    return cmds


class BashTokenizeError(Exception):
    pass


def parse_command(command: str) -> dict:
    """Parse one agent command string into modelled effects.

    Returns {"effects": [Effect...], "heredoc_unterminated": bool,
             "bash_error": str|None}.
    """
    remainder, bodies, unterminated = _extract_heredocs(command)
    try:
        cmds = _simple_commands(remainder)
    except BashTokenizeError as e:
        return {"effects": [Effect("bash-error", reason=str(e), snippet=command)],
                "heredoc_unterminated": unterminated, "bash_error": str(e)}

    effects = []
    for toks in cmds:
        effects.append(_classify_simple(toks, bodies))
    return {"effects": effects, "heredoc_unterminated": unterminated,
            "bash_error": None}


def _body_for_token(tok, bodies):
    b = bodies.get(tok)
    return b["text"] if b else None


def _classify_simple(toks, bodies):
    if not toks:
        return Effect("read-only")
    exe = toks[0]
    exe_base = exe.split("/")[-1]

    # python heredoc / -c / file
    if exe_base in ("python3", "python"):
        # python3 - <<D  or  python3 <<D  -> heredoc body is a token placeholder
        for t in toks[1:]:
            if t.startswith("__GKB_HEREDOC_"):
                body = _body_for_token(t, bodies)
                return Effect("python-exec", payload=body, snippet=body)
        # python3 -c <src>
        if "-c" in toks:
            idx = toks.index("-c")
            if idx + 1 < len(toks):
                return Effect("python-exec", payload=toks[idx + 1],
                              snippet=toks[idx + 1])
        # python3 <path>  (read-only unless the file was written in scratch — not modelled here)
        return Effect("read-only")

    # cat > P <<D ; tee P <<D ; cat <<D > P  -> heredoc write
    if exe_base in ("cat", "tee"):
        # find a redirect target and a heredoc token
        target = None
        body_tok = None
        for k, t in enumerate(toks):
            if t == ">" and k + 1 < len(toks):
                target = toks[k + 1]
            elif t.startswith("__GKB_HEREDOC_"):
                body_tok = t
            elif exe_base == "tee" and k >= 1 and not t.startswith(("-", ">", "<")) \
                    and not t.startswith("__GKB_HEREDOC_"):
                target = target or t
        if body_tok and target:
            path, unsafe = _normalize_path(target)
            if unsafe:
                return Effect("unmodeled", reason=unsafe, snippet=" ".join(toks))
            if path and path.startswith("tmp/"):
                return Effect("read-only")   # scratch write; not an edit attempt
            return Effect("file-write", payload=_body_for_token(body_tok, bodies),
                          path=path)
        return Effect("read-only")

    # sed -i 's/A/B/[g]' FILE
    if exe_base == "sed" and any(t.startswith("-i") for t in toks):
        sub = next((t for t in toks if t.startswith("s") and t.count("/") >= 3), None)
        file_tok = toks[-1] if toks else None
        if sub and file_tok:
            m = re.match(r"s/(.*?)/(.*?)/(g?)$", sub)
            if m and not re.search(r"[.*+?^$\[\](){}\\|]", m.group(1)):
                path, unsafe = _normalize_path(file_tok)
                if unsafe:
                    return Effect("unmodeled", reason=unsafe, snippet=" ".join(toks))
                return Effect("sed-sub", payload=(m.group(1), m.group(2),
                                                  bool(m.group(3))), path=path)
        return Effect("unmodeled", reason="sed -i not statically modelled",
                      snippet=" ".join(toks))

    # redirect to a workspace path:  foo > P  /  foo >> P
    for k, t in enumerate(toks):
        if t in (">", ">>") and k + 1 < len(toks):
            path, unsafe = _normalize_path(toks[k + 1])
            if path and not path.startswith("tmp/"):
                return Effect("unmodeled", reason="redirect to workspace path",
                              snippet=" ".join(toks))

    if exe_base in _MUTATION_CMDS or (exe_base == "git" and len(toks) > 1
                                      and toks[1] in ("checkout", "apply", "stash",
                                                      "reset")):
        return Effect("unmodeled", reason=f"{exe_base} mutation",
                      snippet=" ".join(toks))

    return Effect("read-only")
