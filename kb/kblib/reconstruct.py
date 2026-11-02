"""Static Python symbolic interpreter + edit reconstruction (design §8.2, §8.5).

Reconstructs what an agent's `python3`/heredoc edit tried to do over a virtual
file system, WITHOUT executing it. The source goes through ast.parse; a
SyntaxError predicts SYNTAX_ERROR. Supported statements/expressions are a small
subset covering str.replace / re.sub / open().write / Path.write_text, which is
every shape measured in the real traces (§2.8).

This module imports no subprocess / os process API and contains no exec/eval/
compile(..., "exec") (test-enforced).
"""
from __future__ import annotations

import ast
import re

from . import bashpy

MAX_FOR_ITERS = 200

# prediction enum shared with traces.py edit_attempts
PRED = ("APPLIED", "NOOP", "ANCHOR_MISS", "SYNTAX_ERROR", "BASH_ERROR",
        "TOOL_ERROR", "UNPARSED")


class ReconResult:
    __slots__ = ("prediction", "detail", "changed", "old_literals",
                 "new_literals", "files", "unparsed")

    def __init__(self):
        self.prediction = None   # set by _finish() unless an error path sets it
        self.detail = None
        self.changed = {}        # path -> new content (str)
        self.old_literals = []   # OLD-side string literals (for near-miss)
        self.new_literals = []   # NEW-side string literals (for near-miss)
        self.files = []          # target file paths touched
        self.unparsed = None     # reason string if UNPARSED


# --------------------------------------------------------------------------- VFS

class VFS:
    """Virtual file system: path -> content string. Loader supplies base blobs."""

    def __init__(self, loader=None):
        self._files = {}
        self._loader = loader   # callable(path) -> str | None

    def read(self, path):
        if path in self._files:
            return self._files[path]
        if self._loader is not None:
            txt = self._loader(path)
            if txt is not None:
                self._files[path] = txt
            return txt
        return None

    def write(self, path, content):
        self._files[path] = content

    def exists(self, path):
        return self.read(path) is not None

    def copy(self):
        v = VFS(self._loader)
        v._files = dict(self._files)
        return v

    def changed_vs(self, other_loader_vfs):
        """Return {path: content} for files this VFS wrote (present in _files)."""
        return dict(self._files)


# --------------------------------------------------------------- R1 span extraction

def extract_escaped_quote_spans(src: str):
    """R1 (§8.5): decode escaped-quote OLD/NEW payloads in a `-c '...'` script.

    A payload opens at `<NAME> = \\"` and closes at the first `\\"` followed by
    optional spaces then `;`, newline, or end. Inner `\\"` followed by anything
    else stays inside the span. Decoding happens only inside each span.
    Returns a repaired source string (spans replaced by repr of decoded text) or
    None if no such span exists.
    """
    if '\\"' not in src:
        return None
    out = []
    i = 0
    n = len(src)
    changed = False
    assign = re.compile(r'(\w+)\s*=\s*\\"')
    while i < n:
        m = assign.match(src, i)
        if not m:
            out.append(src[i])
            i += 1
            continue
        # found NAME = \"  -> scan for the closing \"
        out.append(src[i:m.end() - 2])   # keep `NAME = ` without the opening \"
        j = m.end()
        span = []
        closed = False
        while j < n - 1:
            if src[j] == "\\" and src[j + 1] == '"':
                # candidate close: look ahead past spaces
                k = j + 2
                while k < n and src[k] == " ":
                    k += 1
                if k >= n or src[k] in ";\n'":
                    closed = True
                    j += 2
                    break
                else:
                    span.append('"')   # inner escaped quote stays in the span
                    j += 2
                    continue
            span.append(src[j])
            j += 1
        raw = "".join(span)
        decoded = _decode_escapes(raw)
        out.append(repr(decoded))
        changed = True
        i = j
    return "".join(out) if changed else None


def _decode_escapes(s: str) -> str:
    res = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            res.append({"n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}.get(nxt, nxt))
            i += 2
        else:
            res.append(s[i])
            i += 1
    return "".join(res)


# ----------------------------------------------------------------- Python eval

class _StopEval(Exception):
    def __init__(self, prediction, detail=None):
        self.prediction = prediction
        self.detail = detail


class PyEval:
    """Symbolic evaluator over a VFS. Never executes real code."""

    def __init__(self, vfs: VFS):
        self.vfs = vfs
        self.env = {}
        self.result = ReconResult()

    def run(self, src: str) -> ReconResult:
        # R1 repair first if escaped-quote spans are present
        repaired = extract_escaped_quote_spans(src)
        use = repaired if repaired is not None else src
        try:
            tree = ast.parse(use)
        except SyntaxError as e:
            # try the raw source if the repair broke it
            if repaired is not None:
                try:
                    tree = ast.parse(src)
                except SyntaxError as e2:
                    self.result.prediction = "SYNTAX_ERROR"
                    self.result.detail = str(e2.msg)
                    return self.result
            else:
                self.result.prediction = "SYNTAX_ERROR"
                self.result.detail = str(e.msg)
                return self.result
        try:
            for node in tree.body:
                self._stmt(node)
        except _StopEval as st:
            self.result.prediction = st.prediction
            self.result.detail = st.detail
            return self._finish()
        except _Unparsed as u:
            self.result.prediction = "UNPARSED"
            self.result.unparsed = u.reason
            return self._finish()
        return self._finish()

    def _finish(self):
        if self.result.prediction in ("SYNTAX_ERROR", "UNPARSED", "ANCHOR_MISS",
                                      "TOOL_ERROR", "BASH_ERROR"):
            self.result.files = sorted(self.result.changed.keys())
            return self.result
        self.result.prediction = "APPLIED" if self.result.changed else "NOOP"
        self.result.files = sorted(self.result.changed.keys())
        return self.result

    # -- statements --
    def _stmt(self, node):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)):
            return
        if isinstance(node, ast.Assign):
            val = self._expr(node.value)
            for tgt in node.targets:
                self._assign(tgt, val)
            return
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            cur = self.env.get(self._name(node.target), "")
            self.env[self._name(node.target)] = (cur or "") + (self._expr(node.value) or "")
            return
        if isinstance(node, ast.Expr):
            self._expr(node.value)
            return
        if isinstance(node, ast.Assert):
            if not self._truthy(self._expr(node.test)):
                raise _StopEval("ANCHOR_MISS", "assert failed")
            return
        if isinstance(node, ast.If):
            if self._truthy(self._expr(node.test)):
                for s in node.body:
                    self._stmt(s)
            else:
                for s in node.orelse:
                    self._stmt(s)
            return
        if isinstance(node, ast.For):
            self._for(node)
            return
        if isinstance(node, ast.With):
            self._with(node)
            return
        raise _Unparsed(f"{type(node).__name__} at line {getattr(node, 'lineno', '?')}")

    def _assign(self, tgt, val):
        if isinstance(tgt, ast.Name):
            self.env[tgt.id] = val
        elif isinstance(tgt, ast.Tuple) and isinstance(val, (list, tuple)):
            for t, v in zip(tgt.elts, val):
                self._assign(t, v)

    def _name(self, node):
        return node.id if isinstance(node, ast.Name) else None

    def _for(self, node):
        it = node.iter
        items = None
        if isinstance(it, (ast.List, ast.Tuple)):
            items = [self._expr(e) for e in it.elts]
        if items is None:
            raise _Unparsed(f"for over non-literal at line {node.lineno}")
        for idx, item in enumerate(items):
            if idx >= MAX_FOR_ITERS:
                break
            self._assign(node.target, item)
            for s in node.body:
                self._stmt(s)

    def _with(self, node):
        # with open(p[, 'w'|'r']) as f: ...
        if not node.items:
            raise _Unparsed("with: no items")
        item = node.items[0]
        ctx = item.context_expr
        if not (isinstance(ctx, ast.Call) and self._is_open(ctx.func)):
            raise _Unparsed("with: non-open context")
        path = self._expr(ctx.args[0]) if ctx.args else None
        mode = self._expr(ctx.args[1]) if len(ctx.args) > 1 else "r"
        asname = item.optional_vars.id if isinstance(item.optional_vars, ast.Name) else "_f"
        self.env[asname] = {"__file__": path, "__mode__": mode}
        for s in node.body:
            self._stmt(s)

    # -- expressions --
    def _expr(self, node):
        if node is None:
            return None
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self.env.get(node.id)
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                elif isinstance(v, ast.FormattedValue):
                    val = self._expr(v.value)
                    parts.append("" if val is None else str(val))
                else:
                    raise _Unparsed("f-string with unknown part")
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            a = self._expr(node.left)
            b = self._expr(node.right)
            if isinstance(a, str) and isinstance(b, str):
                return a + b
            raise _Unparsed("non-string + ")
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._expr(e) for e in node.elts]
        raise _Unparsed(f"expr {type(node).__name__} at line {getattr(node, 'lineno', '?')}")

    def _compare(self, node):
        left = self._expr(node.left)
        for op, comp in zip(node.ops, node.comparators):
            right = self._expr(comp)
            if isinstance(op, ast.In):
                return (left in right) if right is not None else False
            if isinstance(op, ast.NotIn):
                return (left not in right) if right is not None else True
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            raise _Unparsed("compare op")
        return False

    def _is_open(self, func):
        return isinstance(func, ast.Name) and func.id == "open"

    def _is_path_ctor(self, func):
        if isinstance(func, ast.Name) and func.id == "Path":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "Path":
            return True
        return False

    def _call(self, node):
        func = node.func
        # Path(x) / pathlib.Path(x)
        if self._is_path_ctor(func):
            arg = self._expr(node.args[0]) if node.args else None
            return {"__path__": arg}
        # os.path.join(a, b, ...)
        if isinstance(func, ast.Attribute) and func.attr == "join":
            parts = [self._expr(a) for a in node.args]
            if all(isinstance(p, str) for p in parts):
                return "/".join(parts)
        # open(p).read()  handled via attribute chain below
        if self._is_open(func):
            path = self._expr(node.args[0]) if node.args else None
            mode = self._expr(node.args[1]) if len(node.args) > 1 else "r"
            return {"__file__": path, "__mode__": mode}
        if isinstance(func, ast.Attribute):
            return self._method(func, node)
        if isinstance(func, ast.Name) and func.id == "len":
            v = self._expr(node.args[0]) if node.args else None
            return len(v) if v is not None else 0
        if isinstance(func, ast.Name) and func.id == "print":
            return None
        raise _Unparsed(f"call {ast.dump(func)[:40]}")

    def _method(self, func: ast.Attribute, node: ast.Call):
        obj = self._expr(func.value)
        meth = func.attr
        args = [self._expr(a) for a in node.args]

        # pathlib Path method .read_text / .write_text
        if isinstance(obj, dict) and "__path__" in obj:
            path = _clean_path(obj["__path__"])
            if meth == "read_text":
                self.result.files.append(path)
                txt = self.vfs.read(path)
                if txt is None:
                    raise _StopEval("TOOL_ERROR", f"read_text missing file {path}")
                return txt
            if meth == "write_text":
                content = args[0] if args else ""
                self.result.new_literals.append(content)
                self._apply_write(path, content)
                return None
        # file handle .read / .write
        if isinstance(obj, dict) and "__file__" in obj:
            path = _clean_path(obj["__file__"])
            if meth == "read":
                txt = self.vfs.read(path)
                if txt is None:
                    raise _StopEval("TOOL_ERROR", f"read missing file {path}")
                return txt
            if meth == "write":
                content = args[0] if args else ""
                self.result.new_literals.append(content)
                self._apply_write(path, content)
                return None

        # str methods
        if isinstance(obj, str):
            if meth == "replace":
                old = args[0] if args else ""
                new = args[1] if len(args) > 1 else ""
                self.result.old_literals.append(old)
                self.result.new_literals.append(new)
                count = args[2] if len(args) > 2 else -1
                return obj.replace(old, new, count) if count is not None and count >= 0 \
                    else obj.replace(old, new)
            if meth in ("strip", "rstrip", "lstrip"):
                return getattr(obj, meth)(*[a for a in args if a is not None])
            if meth == "count":
                return obj.count(args[0]) if args else 0
            if meth == "find":
                return obj.find(args[0]) if args else -1
            if meth in ("startswith", "endswith"):
                return getattr(obj, meth)(args[0]) if args else False
            if meth == "split":
                return obj.split(*args) if args else obj.split()
            if meth == "splitlines":
                return obj.splitlines()
            if meth == "join":
                return obj.join(args[0]) if args and args[0] is not None else obj

        # re.sub / re.subn  (func.value is `re`)
        if isinstance(func.value, ast.Name) and func.value.id == "re" \
                and meth in ("sub", "subn"):
            pat = args[0]
            repl = args[1]
            s = args[2] if len(args) > 2 else ""
            if not (isinstance(pat, str) and isinstance(repl, str) and isinstance(s, str)):
                raise _Unparsed("re.sub non-constant")
            self.result.old_literals.append(pat)
            self.result.new_literals.append(repl)
            try:
                out = re.sub(pat, repl, s)
            except re.error as e:
                raise _StopEval("TOOL_ERROR", f"re.error: {e}")
            return out if meth == "sub" else out

        raise _Unparsed(f"method {meth}")

    def _apply_write(self, path, content):
        path = _clean_path(path)
        if path is None:
            raise _Unparsed("write to non-constant path")
        self.vfs.write(path, content)
        self.result.changed[path] = content

    def _truthy(self, v):
        return bool(v)


class _Unparsed(Exception):
    def __init__(self, reason):
        self.reason = reason


def _clean_path(p):
    if not isinstance(p, str):
        return None
    p = p.strip()
    if p.startswith("/workspace/"):
        p = p[len("/workspace/"):]
    return p.lstrip("/")


# --------------------------------------------------------- top-level reconstruction

def reconstruct_run_command(command: str, vfs: VFS) -> ReconResult:
    """Reconstruct a `run_command` edit attempt statically.

    Dispatches through the bash front-end: python-exec effects go to PyEval;
    file-write / sed-sub are applied directly; unmodeled / bash errors are
    reported.
    """
    parsed = bashpy.parse_command(command)
    if parsed["bash_error"]:
        r = ReconResult()
        r.prediction = "BASH_ERROR"
        r.detail = parsed["bash_error"]
        return r
    # fold the effects in command order; stop at the first that fails/writes
    agg = ReconResult()
    agg.prediction = "NOOP"
    for eff in parsed["effects"]:
        if eff.kind == "python-exec":
            if eff.payload is None:
                agg.prediction = "UNPARSED"
                agg.unparsed = "empty python body"
                return agg
            pe = PyEval(vfs)
            res = pe.run(eff.payload)
            agg.old_literals.extend(res.old_literals)
            agg.new_literals.extend(res.new_literals)
            for p, c in res.changed.items():
                agg.changed[p] = c
            if res.prediction in ("SYNTAX_ERROR", "ANCHOR_MISS", "TOOL_ERROR",
                                  "UNPARSED", "BASH_ERROR"):
                agg.prediction = res.prediction
                agg.detail = res.detail
                agg.unparsed = res.unparsed
                agg.files = sorted(agg.changed.keys())
                return agg
            if res.prediction == "APPLIED":
                agg.prediction = "APPLIED"
        elif eff.kind == "file-write":
            if eff.path and eff.payload is not None:
                vfs.write(eff.path, eff.payload)
                agg.changed[eff.path] = eff.payload
                agg.new_literals.append(eff.payload)
                agg.prediction = "APPLIED"
        elif eff.kind == "sed-sub":
            old, new, glob = eff.payload
            cur = vfs.read(eff.path) if eff.path else None
            agg.old_literals.append(old)
            agg.new_literals.append(new)
            if cur is not None:
                nc = cur.replace(old, new) if glob else cur.replace(old, new, 1)
                if nc != cur:
                    vfs.write(eff.path, nc)
                    agg.changed[eff.path] = nc
                    agg.prediction = "APPLIED"
        elif eff.kind == "unmodeled":
            agg.prediction = "UNPARSED"
            agg.unparsed = eff.reason
            agg.files = sorted(agg.changed.keys())
            return agg
        elif eff.kind == "bash-error":
            agg.prediction = "BASH_ERROR"
            agg.detail = eff.reason
            return agg
    agg.files = sorted(agg.changed.keys())
    if agg.prediction == "NOOP" and agg.changed:
        agg.prediction = "APPLIED"
    return agg
