"""
Lightweight LOCAL harness: does OUR AGENT PATH actually solve a real SWE bug when the model
cooperates? Uses local ollama Gemma (gemma4:26b) as a cooperating stand-in for the comp's 31B.

NOT the Kaggle scorer. This answers ONE question: given our prompt + tools, can the loop
locate -> edit -> produce a patch that makes the task's hidden test_patch PASS?

Flow (mirrors the real harness minimally):
  1. git stash/reset the repo to base_commit (clean tree).
  2. Run the agent loop: model + tools (read_file, edit_file, run_command, submit_patch),
     our tightened system prompt, bounded tool calls.
  3. Take the agent's git diff. Apply it to a FRESH checkout, apply the task.test_patch,
     run the specific tests. resolved = pytest exit 0.

Usage: python run_local.py --task rich_4077 --model gemma4:26b --max-tool-calls 15
"""
import argparse, json, shutil, subprocess, re, os, sys, time, urllib.error, urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:8081/v1/chat/completions"  # llama-server (--jinja tool-calling), not Ollama
TASKS = Path(__file__).parent.parent / "comp_files" / "tasks.jsonl"
REPOS_DIR = Path(__file__).parent / "repos"
REPO = REPOS_DIR / "rich"

# repo name -> github clone url (for per-task checkout in batch mode)
REPO_URLS = {
    "rich": "https://github.com/Textualize/rich.git",
    "fastapi": "https://github.com/fastapi/fastapi.git",
    "requests": "https://github.com/psf/requests.git",
    "httpx": "https://github.com/encode/httpx.git",
}

def set_repo(repo_short):
    """Point the global REPO at a given repo's local clone (clone if missing)."""
    global REPO
    REPO = REPOS_DIR / repo_short
    if not REPO.exists():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", REPO_URLS[repo_short], str(REPO)], check=True)
    return REPO

SYSTEM_PROMPT = """You are an expert autonomous software engineer. You have a HARD budget of ~15 tool calls. BE DECISIVE AND FAST.

The one rule that matters: LOCATE then EDIT. Spend AT MOST 3-4 tool calls locating the bug, then IMMEDIATELY call edit_file. 

DO NOT write reproduction scripts. DO NOT try to reproduce or verify the bug before fixing. DO NOT use run_command to create test files. The moment you have read the buggy code, make your edit_file call. Reproducing wastes your entire budget — go straight from reading the code to editing it.

Strategy: most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, similar functions in the same file). Fix the exact deviation only.

Workflow:
1. Locate the bug FAST: use search_code(query) to find the symbol/function (e.g. search_code("isatty")), then read_file(path, start_line, end_line) around the hit to see the code. MAX 3-4 locate calls.
2. Make the minimal fix with edit_file(path, old_string, new_string). old_string must be an EXACT unique snippet from the file. Match existing conventions.
3. Call submit_patch ONCE. When it returns ok, STOP: no more tool calls.

Tools: search_code(query), read_file(path, start_line, end_line), edit_file(path, old_string, new_string), run_command(command), submit_patch(). ONE tool call per turn via function-calling. Do NOT modify test files. You MUST make at least one edit_file call before submitting.

CRITICAL: Keep your reasoning to ONE OR TWO SENTENCES, then IMMEDIATELY emit a tool call. Do NOT write long analysis. Do NOT explain at length. Every response must end in a tool call."""

TOOLS = [
    {"type": "function", "function": {"name": "read_file", "description": "Read a file (optionally a line range) from the repo. Returns numbered lines.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_code", "description": "Search the repo for a string/symbol; returns matching file:line results.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace old_string with new_string in an existing file. old_string must be an EXACT snippet copied verbatim from the file content, and must appear exactly once. new_string is the corrected code and MUST differ from old_string (it must change program behavior, not just reformat).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}, "required": ["path", "old_string", "new_string"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Run a shell command in the repo root",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "submit_patch", "description": "Submit the final patch; call once when done",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_similar_code", "description": "Find code nodes whose SYMBOL name matches the query. Pass a class/function/module SYMBOL name (e.g. 'ServerSentEvent', 'analyze_param'), NOT a natural-language sentence. Returns top-k matching dotted symbol paths.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_code_neighbors", "description": "Return the call/dependency-graph neighbors (incoming callers + outgoing callees) of a symbol. Pass a class/function SYMBOL name. Optional edge_type filter (e.g. 'calls').",
        "parameters": {"type": "object", "properties": {"node": {"type": "string"}, "edge_type": {"type": "string"}, "max_neighbors": {"type": "integer"}}, "required": ["node"]}}},
    {"type": "function", "function": {"name": "get_code_subgraph", "description": "Return the local neighborhood (symbols within `depth` edges) of a symbol in the call/dependency graph.",
        "parameters": {"type": "object", "properties": {"node": {"type": "string"}, "depth": {"type": "integer"}}, "required": ["node"]}}},
        {"type": "function", "function": {"name": "get_status", "description": "Return live budget consumption and patch status. FREE - does not consume a tool call.",
            "parameters": {"type": "object", "properties": {}}}},
    ]

def _fn(name, desc, props, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(required)}}}


# The scorer's tool surface (HARNESS_README 6.1-6.3 and agent.yaml `tools:`): filepath (not path), allow_multiple,
# write_file, get_code_subgraph(nodes), and NO search_code. Descriptions are paraphrased from the README because the
# swegemma docstrings that ADK turns into declarations are not in the local copy of the harness.
KAGGLE_TOOLS = [
    _fn("run_command", "Execute a shell command with /bin/bash in /workspace. Returns stdout, stderr and exit_code.",
        {"command": {"type": "string"}}, ["command"]),
    _fn("submit_patch", "Submit the final patch (the git diff of your changes). Free; call once when done.", {}),
    _fn("get_status", "Return live budget consumption and patch status. FREE - does not consume a tool call.", {}),
    _fn("read_file", "Read a file from /workspace with 1-indexed inclusive line slicing. Capped at 150 lines and 10,000 characters per call.",
        {"filepath": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["filepath"]),
    _fn("edit_file", "Replace old_string with new_string in an existing file using exact, then whitespace-flexible, then regex matching. Fails if old_string matches more than once unless allow_multiple is true.",
        {"filepath": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"},
         "allow_multiple": {"type": "boolean"}}, ["filepath", "old_string", "new_string"]),
    _fn("write_file", "Create or overwrite a file at /workspace/<filepath>, creating parent directories.",
        {"filepath": {"type": "string"}, "content": {"type": "string"}}, ["filepath", "content"]),
    _fn("get_code_neighbors", "Find the callers and callees of a symbol node in the repository call graph.",
        {"node": {"type": "string"}, "edge_type": {"type": "string"}, "max_neighbors": {"type": "integer"}}, ["node"]),
    _fn("search_similar_code", "Find the top-k graph nodes most similar to a query (a dotted symbol path or short symbol name).",
        {"query": {"type": "string"}, "k": {"type": "integer"}}, ["query"]),
    _fn("get_code_subgraph", "Extract the induced call subgraph (nodes and interconnecting edges) for a list of symbols.",
        {"nodes": {"type": "array", "items": {"type": "string"}}}, ["nodes"]),
]
ACTIVE_TOOLS = TOOLS
RESULT_CAP = 3000      # legacy cap on the JSON tool result shown to the model; the scorer does NOT cut results here
PARITY = False         # True in 'kaggle' mode: scorer-style validation (malformed/unknown calls are free)


def set_tools_mode(mode):
    """'legacy' = the original local schema (path, search_code); 'kaggle' = the scorer's tool surface."""
    global ACTIVE_TOOLS, RESULT_CAP, PARITY
    ACTIVE_TOOLS = KAGGLE_TOOLS if mode == "kaggle" else TOOLS
    PARITY = mode == "kaggle"
    RESULT_CAP = 40000 if PARITY else 3000   # real read_file results reach ~25k chars (JSON-escaped), median 2.5k


def _missing_required(fn, args):
    """Parameter names ADK would report as mandatory-but-absent (it rejects such calls before the tool runs)."""
    for t in ACTIVE_TOOLS:
        if t["function"]["name"] == fn:
            return [k for k in t["function"]["parameters"].get("required", []) if k not in args]
    return None   # unknown tool


def _adk_missing_msg(fn, missing):
    return {"error": f"Invoking `{fn}()` failed as the following mandatory input parameters are not present:\n"
                     + "\n".join(missing)
                     + "\nYou could retry calling this tool, but it is IMPORTANT for you to provide all the mandatory parameters."}


# per-task graph tools instance (set by load_graph_for_task); None if no graph for the task.
GRAPH = None

def load_graph_for_task(repo_short, base_commit):
    """Load the per-task code graph so search_similar_code/get_code_neighbors/get_code_subgraph work
    like the real harness. Sets module-global GRAPH. No-op-safe if the graph file is missing."""
    global GRAPH
    try:
        from graph_tools import GraphTools
        GRAPH = GraphTools(repo_short, base_commit)
        if not GRAPH.available:
            GRAPH = None
    except Exception:
        GRAPH = None
    return GRAPH


def load_task(tid):
    for l in open(TASKS, encoding="utf-8"):
        t = json.loads(l)
        if t["instance_id"] == tid:
            return t
    raise SystemExit(f"task {tid} not found")


def git(args, cwd=None):
    return subprocess.run(["git"] + args, cwd=cwd or REPO, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def reset_repo(base_commit):
    git(["reset", "--hard", base_commit])
    git(["clean", "-fd"])


# ---- scorer-parity helpers (used only when PARITY is True; legacy behaviour is unchanged) ----
CMD_TIMEOUT = 240            # eval_config command_timeout_seconds
REAL_MAX_TIME_S = 480.0      # eval_config max_time_minutes = 8.0
VCLOCK_S_PER_TURN = 8.0      # virtual clock for get_status when --max-time 0 (real 28-call runs take ~230 s of wall time)
SANDBOX_ID = "d257bafb-db9"  # shows up in the real FileReadError text; re-rolled per run
SYSTEM_DIRS = {"tmp", "usr", "etc", "var", "home", "opt", "root", "bin", "lib", "lib64", "sbin", "mnt", "proc", "dev", "sys", "srv", "run"}
PROTECTED_BASENAMES = {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini",
                       "sitecustomize.py", "usercustomize.py", "_swegemma_stubs.py"}


class PathEscape(Exception):
    """A path the scorer's sandbox rejects: '..' components or an absolute system path such as /tmp/x.py."""


def _escape_err(kind, p):
    return {"status": "error", "error_type": kind, "error_message": f"Path traversal detected: '{p}' escapes workspace root."}


def _repo_posix():
    """REPO as an MSYS path (/c/Users/...) so Git-bash can use it where the model typed /workspace."""
    p = REPO.resolve().as_posix()
    return "/" + p[0].lower() + p[2:] if len(p) > 1 and p[1] == ":" else p


def _is_protected(path):
    parts = path.split("/")
    base = parts[-1]
    if base in PROTECTED_BASENAMES or base.endswith(".pth"):
        return True
    if base.endswith(".py"):
        return base.startswith("test_") or base.endswith("_test.py") or any(x in ("tests", "test", "testing") for x in parts[:-1])
    return False


def strip_protected(diff):
    """strip_protected_files_from_patch (HARNESS_README 8.1): drop diff sections that touch tests or runner config."""
    kept, cur, keep = [], [], True
    for ln in diff.splitlines(keepends=True):
        if ln.startswith("diff --git "):
            if cur and keep:
                kept.extend(cur)
            m = re.match(r"diff --git a/(.*?) b/(.*)$", ln.rstrip("\r\n"))
            keep = not _is_protected(m.group(2) if m else "")
            cur = [ln]
        else:
            cur.append(ln)
    if cur and keep:
        kept.extend(cur)
    return "".join(kept)


def final_patch(base_commit):
    """What the scorer extracts at submit_patch or in its unsubmitted-patch fallback: `git add -N .`, diff vs the
    baseline (new files included), protected test/config files stripped."""
    git(["add", "-N", "."])
    return strip_protected(git(["diff", base_commit]).stdout)


def resolve_path(p):
    raw = str(p).strip()
    s = raw.lstrip("/")
    if PARITY:
        parts = [x for x in s.replace("\\", "/").split("/") if x]
        if ".." in parts or (raw.startswith("/") and not raw.startswith("/workspace") and parts and parts[0] in SYSTEM_DIRS):
            raise PathEscape(raw)
    if s.startswith("workspace/"):
        s = s[len("workspace/"):]
    return REPO / s


def tool_read_file(path=None, start_line=None, end_line=None, filepath=None):
    path = path or filepath
    if not path:
        raise ValueError("read_file requires filepath")
    try:
        fp = resolve_path(path)
    except PathEscape as pe:
        return _escape_err("FileReadError", pe)
    if not fp.exists() or fp.is_dir():
        if PARITY:
            rel = str(path).strip().lstrip("/")
            rel = rel[len("workspace/"):] if rel.startswith("workspace/") else rel
            return {"status": "error", "error_type": "FileReadError",
                    "error_message": f"Source path /workspace/{rel} not found in sandbox {SANDBOX_ID}"}
        return {"status": "error", "error": f"not found: {path}"}
    lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    s = max(1, int(start_line)) if start_line else 1
    want_end = min(total, int(end_line)) if end_line else total
    e = min(total, int(end_line)) if end_line else min(total, s + 149)
    if PARITY and s > e:
        return {"status": "error", "error_type": "ValueError",
                "error_message": f"start_line ({s}) cannot be greater than end_line ({e})", "details": {}}
    if e - s + 1 > 150:
        e = s + 149
    # Return RAW content exactly like the real swegemma read_file (no 'N: ' prefix in the body).
    # Line numbers are metadata only (start_line/end_line), NOT embedded in content. Injecting
    # 'N: ' prefixes trained the model to echo prefixed lines into edit_file old/new_string, which
    # then never matched the real file -> no-op / mangled edits. This was a HARNESS bug, not the model.
    body = "\n".join(lines[s-1:e])
    if len(body) > 10000:
        # dual cap like the real tool: stop at the last complete line that fits in 10,000 chars
        kept, size = [], 0
        for ln in lines[s-1:e]:
            if size + len(ln) + 1 > 10000:
                break
            kept.append(ln)
            size += len(ln) + 1
        e = s + len(kept) - 1
        body = "\n".join(kept)
    return {"status": "ok", "filepath": path, "content": body, "start_line": s, "end_line": e,
            "total_lines": total, "is_truncated": (e < want_end) if PARITY else (e < total)}


def tool_search_code(query):
    """grep-style search across the repo (stand-in for search_similar_code). Fixed-string, robust."""
    r = subprocess.run(["git", "grep", "-n", "-I", "-F", query, "--", "*.py"],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout or ""
    hits = out.splitlines()[:20]
    if not hits:
        # fallback: case-insensitive fixed-string
        r2 = subprocess.run(["git", "grep", "-n", "-I", "-F", "-i", query, "--", "*.py"],
                            cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        hits = (r2.stdout or "").splitlines()[:20]
    return {"status": "ok", "query": query, "results": hits, "count": len(hits)}


def _strip_line_numbers(s):
    """The model sometimes echoes our 'N: <code>' read_file format into edit args.
    Strip a leading '<digits>: ' / '<digits>|' prefix from each line so exact-match works."""
    out = []
    for ln in s.split("\n"):
        out.append(re.sub(r'^\s*\d+[:|]\s?', '', ln))
    return "\n".join(out)


# "real": the scorer's own matcher (adk_eval_core.editing.edit.apply_replacement: exact -> flexible ->
#         regex -> JSON-unescape). "strict": the first local matcher (exact substring only). The strict one was
#         used by every local run before 2026-10-16 and is NOT what Kaggle runs.
EDIT_ENGINE = "real"
_APPLY_REPL = None
_AMBIG_ERR = None
_MAKE_DIFF = None


def _load_real_edit():
    """Load the scorer's matcher without executing adk_eval_core/__init__ (that needs pydantic).
    editing/edit.py only needs errors.py, so a stub parent package that carries __path__ is enough."""
    global _APPLY_REPL, _AMBIG_ERR, _MAKE_DIFF
    if _APPLY_REPL is None:
        import types
        pkg_dir = Path(__file__).resolve().parent.parent / "harness_src" / "x" / "adk_eval_core"
        if "adk_eval_core" not in sys.modules:
            stub = types.ModuleType("adk_eval_core")
            stub.__path__ = [str(pkg_dir)]
            sys.modules["adk_eval_core"] = stub
        from adk_eval_core.editing.edit import apply_replacement, make_diff
        from adk_eval_core.errors import AmbiguousMatchError
        _APPLY_REPL, _AMBIG_ERR, _MAKE_DIFF = apply_replacement, AmbiguousMatchError, make_diff


def _truthy(v):
    return v.strip().lower() == "true" if isinstance(v, str) else bool(v)


def _edit_err(msg):
    return {"status": "error", "error_type": "FileEditError", "error_message": msg}


def tool_edit_file(path=None, old_string="", new_string="", allow_multiple=False, filepath=None):
    path = path or filepath
    if not path:
        raise ValueError("edit_file requires filepath")
    try:
        fp = resolve_path(path)
    except PathEscape as pe:
        return _escape_err("FileEditError", pe)
    if not fp.exists():
        return _edit_err(f"File not found: {path}")
    txt = fp.read_text(encoding="utf-8", errors="replace")
    if EDIT_ENGINE == "strict":
        if old_string not in txt:
            old_string = _strip_line_numbers(old_string)
            new_string = _strip_line_numbers(new_string)
        if old_string not in txt:
            return _edit_err("old_string not found (after line-number strip). Provide the EXACT code text WITHOUT any leading line numbers.")
        if old_string == new_string:
            return _edit_err("old_string and new_string are identical - no change. Provide the corrected code in new_string.")
        if txt.count(old_string) > 1:
            return _edit_err(f"old_string matches {txt.count(old_string)}x; make it unique")
        fp.write_text(txt.replace(old_string, new_string, 1), encoding="utf-8")
        return {"status": "ok", "filepath": path, "strategy": "strict"}
    _load_real_edit()
    try:
        res = _APPLY_REPL(txt, old_string, new_string, _truthy(allow_multiple))
    except _AMBIG_ERR as e:
        return _edit_err(str(e))
    if res.error_message:
        return _edit_err(res.error_message)
    fp.write_text(res.new_content, encoding="utf-8")
    diff = _MAKE_DIFF(txt, res.new_content, path)
    out = {"status": "ok", "filepath": path, "occurrences": res.occurrences, "strategy": res.strategy,
           "diff": diff[:5000]}
    if PARITY:
        out["is_truncated"] = len(diff) > 5000
    return out


# Kaggle's sandbox is Linux/bash, and the system prompt tells the model to use `sed -n` and python heredocs.
# cmd.exe cannot run those, so route run_command through Git-for-Windows bash when it exists.
BASH_EXE = next((p for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe") if os.path.exists(p)), None)
USE_BASH = True


def _run_shell(cmd, timeout):
    """Run `cmd` (bash when available) with stdin closed. On timeout the whole process tree is killed by PID so a
    hung grandchild (pytest, python) cannot keep the pipes open and stall the gate."""
    use_bash = bool(USE_BASH and BASH_EXE)
    p = subprocess.Popen([BASH_EXE, "-c", cmd] if use_bash else cmd, cwd=REPO, shell=not use_bash,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace")
    try:
        so, se = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        try:
            p.communicate(timeout=10)
        except Exception:
            pass
        raise
    return p.returncode, so or "", se or ""


_WS_RE = re.compile(r"(?<![\w./-])/workspace(?=/|\s|['\"]|$)")


def _run_command_parity(command):
    """HARNESS_README 6.1 shapes: ok -> stdout/stderr/exit_code; failure -> CommandError with details; each stream
    cut to 5000 chars with no marker. The scorer's sandbox lives at /workspace; map it onto the local clone."""
    repo_posix = _repo_posix()
    cmd = _WS_RE.sub(repo_posix, command) if BASH_EXE and USE_BASH else command
    try:
        rc, so, se = _run_shell(cmd, CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error_type": "TimeoutExceeded",
                "error_message": f"Command timed out after {CMD_TIMEOUT} seconds"}
    so = so.replace(repo_posix, "/workspace")[:5000]
    se = se.replace(repo_posix, "/workspace")[:5000]
    if rc == 0:
        return {"status": "ok", "stdout": so, "stderr": se, "exit_code": 0}
    return {"status": "error", "error_type": "CommandError", "error_message": se,
            "details": {"stdout": so, "stderr": se, "exit_code": rc}}


def tool_run_command(command):
    if PARITY:
        return _run_command_parity(command)
    t_start = time.time()
    try:
        if USE_BASH and BASH_EXE:
            r = subprocess.run([BASH_EXE, "-c", command], cwd=REPO, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
        else:
            r = subprocess.run(command, cwd=REPO, shell=True, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "stderr": "command timed out (120s)"}
    out = {"status": "ok" if r.returncode == 0 else "error",
           "stdout": (r.stdout or "")[:5000] + ("... [truncated]" if len(r.stdout or "") > 5000 else ""),
           "stderr": (r.stderr or "")[:5000] + ("... [truncated]" if len(r.stderr or "") > 5000 else ""),
           "exit_code": r.returncode, "duration_seconds": round(time.time() - t_start, 2)}
    return {k: v for k, v in out.items() if v is not None and v != ""}


def tool_write_file(filepath=None, content="", path=None):
    filepath = filepath or path
    if not filepath:
        raise ValueError("write_file requires filepath")
    try:
        fp = resolve_path(filepath)
    except PathEscape as pe:
        return _escape_err("FileWriteError", pe)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return {"status": "ok", "filepath": filepath, "size": len(content.encode("utf-8"))}


def tool_get_code_subgraph(nodes=None, node=None, depth=None):
    """README 6.3: the INDUCED subgraph (listed nodes + the edges between them). Exact-id matching only, like the
    rest of graph_tools (0.2.7 behaviour)."""
    if GRAPH is None:
        return {"status": "error", "error": "no code graph available for this task"}
    if isinstance(nodes, str):
        try:
            nodes = json.loads(nodes)
        except Exception:
            nodes = [s.strip() for s in nodes.split(",") if s.strip()]
    nodes = list(nodes or ([node] if node else []))
    known = [n for n in nodes if n in GRAPH.g["nodes"]]
    keep = set(known)
    edges = [{"from": s, "to": t, "type": et} for s in known for t, et in GRAPH.g["out"].get(s, []) if t in keep]
    return {"status": "ok", "nodes": known, "edges": edges, "node_count": len(known), "edge_count": len(edges),
            "is_truncated": False}


TEMPERATURE = 0.2
# Per-turn generation cap. 1536 was TOO LOW: it truncated longer multiline edit_file new_string
# arguments mid-token (observed '...bo' cut-offs), producing mangled/no-op edits that looked like
# model failures but were our cap clipping the tool-call JSON. Raise so a full multiline edit fits;
# runaway-thinking is handled by the system prompt ("1-2 sentences then a tool call"), not this cap.
MAX_TOKENS = 4096
QUIET = False  # batch mode sets True to suppress noisy per-call prints (avoid console encoding crashes)
THINKING = True       # False -> chat_template_kwargs enable_thinking=false (server-side thinking off)
TOP_P = None          # None -> server default (the GGUF ships top_p 0.95)
TOP_K = None          # None -> server default (the GGUF ships top_k 64)
# Additive, backward-compatible decode penalties (decode_sweep.py axis (b)). Default 0.0 means the
# payload is byte-identical to the pre-2026-10-15 behaviour: chat() only forwards them when NON-ZERO,
# so a 0.0 penalty is never written into the request. These suppress the look-again repeat-loop.
FREQUENCY_PENALTY = 0.0
PRESENCE_PENALTY = 0.0
CHAT_TIMEOUT = None   # socket timeout in seconds; None waits forever, so a slow GPU cannot look like a model failure
MAX_NO_TOOL = 4       # legacy nudge mode only: consecutive no-tool turns tolerated before the run ends
# "legacy": MAX_NO_TOOL strikes with a local, more forceful nudge text (used by the early local runs).
# "kaggle": HARNESS_README 5.3 -- ADK turn without submit_patch => nudge; consecutive_nudges resets when the turn
#           executed a tool call, else increments; > 3 ends the task. Nudge text depends on how the turn ended.
NUDGE_MODE = "legacy"
KAGGLE_MAX_NUDGES = 3
KAGGLE_NUDGE_TEXT = {
    "unclosed": "Your previous response reached the token limit before the tool call finished closing (<|tool_call|> was cut off). Do NOT repeat your prior reasoning in thought\u2014emit your next tool call immediately, and if calling edit_file or write_file, split the change into smaller incremental edits.",
    "length": "Your previous response reached the token limit while thinking before a tool call was completed. Do NOT repeat your analysis in thought\u2014keep reasoning under a few sentences and emit your next tool call immediately, or call submit_patch when you have completed and verified your changes.",
    "stop": "Please continue your work using the available tools, or call submit_patch when you have completed and verified your changes.",
}
THINK_BUDGET = None   # tokens; forwarded as thinking_budget_tokens (llama-server per-request cap), like Kaggle's thinking_budget
SERVER_KIND = os.environ.get("GATE_SERVER", "llama")  # "vllm" -> send Kaggle's adk_submission thinking body
VERIFY_TIMEOUT = int(os.environ.get("GATE_VERIFY_TIMEOUT", "900"))  # seconds; an unfixed infinite-loop task (rich_3480) hangs pytest
HINT_FN = None        # diagnostics only: callable(task) -> text appended to the first user message (oracle localization)
TRACE_FILE = None     # when set, every model turn and tool result is appended to it as one JSON line
LAST_RUN = {}         # stats from the most recent run_agent call (end_reason, edit_ok, first_edit_call, ...)


def _trace(**ev):
    if TRACE_FILE:
        with open(TRACE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- scorer parity (2026-10-13)
# 1. CONTEXT. The scorer serves with max_model_len=32768 (n_ctx reported by llama-server). We had no
#    context management at all, so a long local run could exceed the window and behave unlike the board.
try:
    _mm = json.loads(urllib.request.urlopen("http://127.0.0.1:8081/v1/models", timeout=5).read())
    MAX_MODEL_LEN = int(_mm["data"][0]["meta"].get("n_ctx") or 32768)
except Exception:
    MAX_MODEL_LEN = 32768
# 2. COMPACTION. HARNESS_README 7.2 (comp_official): EventsCompactionConfig(compaction_interval=15, overlap_size=2,
#    token_threshold=14336, event_retention_size=5). The harness pins google-adk>=1.34,<2.0; in 1.34.0..1.39.1 the
#    interval/overlap path counts INVOCATIONS and is only evaluated after an invocation ends, so it essentially never
#    fires (<= 4 invocations per task). What fires is the TOKEN path: a request processor runs before EVERY model
#    call and compacts when the most recent event carrying usage_metadata reported prompt_token_count >= 14336.
#    Real traces agree: 74/106 runs cross 14,336 and the next prompt drops to 3.6-7.6k tokens (atif_prompt_curve.py).
#    Semantics copied from the v1.39.1 source (apps/compaction.py, apps/llm_event_summarizer.py, flows/llm_flows/
#    contents.py); the summarizer prompt is byte-identical, including its literal backslash-n separators.
COMPACTION_TOKEN_THRESHOLD = 14336
EVENT_RETENTION = 5
AGENT_AUTHOR = "sibling_conform_agent"       # ADK event.author of the model's turns; appears in the summarizer input
COMPACTION_SUMMARY_MAX_TOKENS = 2000          # the real summarizer call has no cap; this only protects a 30k slot
# NB: written with doubled backslashes on purpose. ADK ships '\\n\\n' / '\\n'.join(...), i.e. LITERAL backslash-n.
SUMMARY_TEMPLATE = ("The following is a conversation history between a user and an AI agent. Please summarize the "
                    "conversation, focusing on key information and decisions made, as well as any unresolved "
                    "questions or tasks. The summary should be concise and capture the essence of the interaction."
                    "\\n\\n{conversation_history}")


def _adk_events(body):
    """Group chat messages the way ADK's session does: one event per user message, one per assistant message, and
    one per run of tool messages (the parallel function responses of one model turn are merged into one event)."""
    ev = []
    for m in body:
        role = m.get("role")
        if role == "tool" and ev and ev[-1]["kind"] == "resp":
            ev[-1]["msgs"].append(m)
        else:
            ev.append({"kind": {"tool": "resp", "assistant": "model"}.get(role, "user"), "msgs": [m]})
    return ev


def _safe_split(ev, retention):
    """ADK _safe_token_compaction_split_index: the latest index <= len(ev)-retention at which the retained tail holds
    no tool response whose call lies in the compacted prefix (0 = nothing can be compacted)."""
    initial = len(ev) - retention
    if initial <= 0:
        return 0
    open_resp = 0
    for i in range(len(ev) - 1, -1, -1):
        if ev[i]["kind"] == "resp":
            open_resp += 1
        elif ev[i]["msgs"][0].get("tool_calls"):
            open_resp = max(0, open_resp - 1)
        if open_resp == 0 and i <= initial:
            return i
    return 0


def adk_compact(msgs, summary, model, tid, stats, ptok):
    """Token-threshold compaction as ADK 1.34-1.39.1 performs it. msgs[0] is the system message; when `summary` is set,
    msgs[1] is the summary message left by the previous compaction. Returns (new_msgs, new_summary), or None when ADK
    would not compact (too few events, or the summariser returned nothing)."""
    ev = _adk_events(msgs[2:] if summary is not None else msgs[1:])
    split = _safe_split(ev, EVENT_RETENTION) if len(ev) > EVENT_RETENTION else 0
    if split <= 0:
        return None
    lines = [f"model: {summary}"] if summary is not None else []
    for e in ev[:split]:
        m = e["msgs"][0]
        if e["kind"] == "user":
            lines.append(f"user: {m.get('content') or ''}")
        elif e["kind"] == "model":
            lines.extend(f"{AGENT_AUTHOR}: {t}" for t in (m.get("reasoning_content"), m.get("content")) if t)
    prompt = SUMMARY_TEMPLATE.format(conversation_history="\\n".join(lines))
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 1.0, "top_p": 0.95,
               "top_k": 64, "max_tokens": COMPACTION_SUMMARY_MAX_TOKENS, "stream": False,
               "chat_template_kwargs": {"enable_thinking": False}}
    t1 = time.time()
    try:
        req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as r:
            resp = json.loads(r.read())
        text = (resp["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        _trace(task=tid, kind="compaction_error", turn=stats["turns"], error=repr(e)[:300])
        return None
    if not text:
        return None
    head = {"role": "user", "content": "For context:\n[model] said: " + text}
    tail = [m for e in ev[split:] for m in e["msgs"]]
    if tail and tail[0].get("role") == "user":      # two user turns in a row would break the chat template
        head["content"] += "\n" + str(tail[0].get("content") or "")
        tail = tail[1:]
    _trace(task=tid, kind="compaction", turn=stats["turns"], ptok_before=ptok, events=len(ev), compacted=split,
           kept=len(ev) - split, summary_chars=len(text), prompt_chars=len(prompt),
           sprompt_tok=(resp.get("usage") or {}).get("prompt_tokens"), secs=round(time.time() - t1, 1))
    _p(f"  [compacted {split}/{len(ev)} events at prompt={ptok}tok -> {len(text)}ch summary]")
    return [msgs[0], head] + tail, text


def _p(*a):
    if not QUIET:
        try: print(*a)
        except Exception: pass

def chat(messages, model):
    payload = {"model": model, "messages": messages, "tools": ACTIVE_TOOLS,
               "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "stream": False}
    if TOP_P is not None:
        payload["top_p"] = TOP_P
    if TOP_K is not None:
        payload["top_k"] = TOP_K
    if FREQUENCY_PENALTY:
        payload["frequency_penalty"] = FREQUENCY_PENALTY
    if PRESENCE_PENALTY:
        payload["presence_penalty"] = PRESENCE_PENALTY
    if not THINKING:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    elif SERVER_KIND == "vllm":
        # Same body adk_submission.apply_thinking_config_to_model sends to vLLM on Kaggle;
        # the Gemma 4 template defaults enable_thinking to false.
        payload["chat_template_kwargs"] = {"enable_thinking": True}
        if THINK_BUDGET:
            payload["thinking_token_budget"] = THINK_BUDGET
    elif THINK_BUDGET:
        payload["thinking_budget_tokens"] = THINK_BUDGET
    req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT) as resp:
        return json.loads(resp.read())


CHAT_RETRIES = 5        # server-side faults (HTTP 5xx, dropped connection) are retried like the scorer's ModelRetryPlugin
                        # (5 retries, 2 s initial delay, x2 backoff); they are not model outcomes

def chat_retry(messages, model, stats, tid):
    for attempt in range(CHAT_RETRIES + 1):
        try:
            return chat(messages, model)
        except urllib.error.HTTPError as e:
            try: body = e.read().decode("utf-8", "replace")[:600]
            except Exception: body = ""
            _trace(task=tid, kind="chat_error", turn=stats["turns"] + 1, attempt=attempt, code=e.code, body=body)
            stats["chat_error_detail"] = f"{e.code}: {body[:300]}"
            if e.code == 500 and "Failed to parse" in body:
                # llama-server answers a generation that ends inside a tool call (almost always the max_tokens cut) with
                # HTTP 500. vLLM returns the cut-off text with finish_reason=length and the scorer sends its "unclosed"
                # nudge. The fault is deterministic, so retrying only repeats the same long generation.
                stats["unclosed_calls"] = stats.get("unclosed_calls", 0) + 1
                return {"choices": [{"finish_reason": "length",
                                     "message": {"role": "assistant", "content": "<|tool_call>"}}],
                        "usage": {"prompt_tokens": None, "completion_tokens": MAX_TOKENS},
                        "synthetic": "unclosed_tool_call"}
            if e.code < 500 or attempt == CHAT_RETRIES:
                raise
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            _trace(task=tid, kind="chat_error", turn=stats["turns"] + 1, attempt=attempt, code=None, body=repr(e)[:300])
            stats["chat_error_detail"] = repr(e)[:300]
            if attempt == CHAT_RETRIES:
                raise
        stats["chat_retries"] = stats.get("chat_retries", 0) + 1
        time.sleep(min(60, 2 * 2 ** attempt))


KAGGLE_PRUNE = {"docs", "docs_src", "tests", "examples", "benchmarks", "assets", "imgs", "questions"}
# The scorer drops these into /workspace; they are not tracked in the repo but they appear in its directory tree.
KAGGLE_RUNNER_FILES = ("conftest.py", "pytest.ini")


def _collate(p):
    """glibc-like first-level collation: case-insensitive, punctuation ignored (matches the order in the real sample)."""
    return [(re.sub(r"[^0-9a-z]", "", x.lower()), x) for x in p.split("/")]


def workspace_tree(cap=200, maxdepth=3):
    """Replica of the scorer's 'Workspace Layout' (HARNESS_README 5.2 item 7): <=200 breadth-first-selected entries of
    `find . -mindepth 1 -maxdepth 3`, hierarchically sorted, hidden/__pycache__/*.pyc/*.egg-info dropped, bulk
    directories listed but not descended. Validated against the real rich_4079 message (156/156 entries, same order);
    assets, imgs and questions had to be added to the README's 'such as' prune list to match."""
    files = git(["ls-files"]).stdout.splitlines()
    files += [f for f in KAGGLE_RUNNER_FILES if f not in files]
    ents = set()
    for f in files:
        parts = f.split("/")
        if any(x.startswith(".") for x in parts):
            continue
        if any(x == "__pycache__" or x.endswith((".pyc", ".egg-info")) for x in parts):
            continue
        if len(parts) >= 2 and parts[0] in KAGGLE_PRUNE:
            ents.add("./" + parts[0])
            continue
        for d in range(1, min(len(parts), maxdepth) + 1):
            ents.add("./" + "/".join(parts[:d]))
    bfs = sorted(ents, key=lambda e: (e.count("/"), _collate(e)))[:cap]
    return sorted(bfs, key=_collate)


KAGGLE_FIRST_MID = """## Task Budget (Session terminates when any budget is exhausted)
- Time allowance: 8.0 minutes
- Tool calls allowance: 28 calls
- Max loop iterations: 80 turns

## Execution Environment Rules
- Single command timeout: 240 seconds (commands exceeding this fail without ending the session)
- Command output limit: 5000 characters
- File view limit: 150 lines per read_file call
- File character limit: 10000 characters per read_file call
- Environment is offline (no network/PyPI access). All repository and test dependencies are ALREADY pre-installed. Do NOT attempt to run pip install or download packages.

## Instructions:
0. All source code is under `/workspace`. Do NOT search outside `/workspace` (e.g. `/usr/`, `/wheels/`, system site-packages). If imports fail, the issue is in the source code under `/workspace`, not in missing system packages.
1. Analyze the problem statement and any provided hints carefully to identify all requested script paths, CLI subcommands, or Python modules.
2. Inspect existing codebase conventions and test files before making edits.
3. Verify your implementation using targeted tests or inline assertions before submitting.
4. Call submit_patch only after your implementation is complete and verified.
5. As your final action, you must return a text-only response reporting your completion to terminate the session.
## Code Intelligence Tools
This repository has pre-built code graph and embedding data indexed by dotted symbol path (e.g. `pkg.module.Class.method`). Use these tools for fast, targeted navigation:
- `search_similar_code(query)`: Find functions/classes with similar precomputed embeddings given a symbol name (e.g. `pkg.module.Class.method`, `Class.method`, or `func_name`).
- `get_code_neighbors(node)`: Find callers and callees of a symbol node (e.g. `pkg.module.Class.method` or `Class.method`).
- `get_code_subgraph(nodes)`: Get the induced call subgraph connecting a list of symbol nodes.

## Workspace Layout
The repository is located at `/workspace`. Here is the directory tree (up to 3 levels):
"""


def kaggle_first_message(task, hint=""):
    """The first user message the scorer really sends (HARNESS_README 5.2; sample in runs/kaggle_first_user_4079.txt)."""
    tree = "\n".join(workspace_tree())
    return (f"You are evaluating a software engineering task for repository {task['repo']}.\n\n"
            f"Problem Statement:\n{task['problem_statement']}{hint}\n\n" + KAGGLE_FIRST_MID + f"```\n{tree}\n```\n")


FIRST_MSG = "legacy"   # "kaggle" -> kaggle_first_message
MAX_TURNS = 80         # the scorer's 'Max loop iterations' (counted here as model responses)


def run_agent(task, model, max_tool_calls, system_prompt=None, max_time_s=480, use_compaction=True):
    global LAST_RUN
    reset_repo(task["base_commit"])
    load_graph_for_task(task["repo"].split("/")[-1], task["base_commit"])
    hint = HINT_FN(task) if HINT_FN else ""
    first = (kaggle_first_message(task, hint) if FIRST_MSG == "kaggle" else
             f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:4000]}{hint}\n\nFix the bug. Locate fast, edit, submit_patch.")
    msgs = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
        {"role": "user", "content": first},
    ]
    calls = 0
    t0 = time.time()
    submitted = False
    submitted_size = 0          # get_status reports patch_size 0 until submit_patch has run (verified on real traces)
    no_tool_strikes = 0
    # scorer parity: get_status is FREE (count_tool_call=False). Track it separately from `calls`.
    free_status_used = 0
    compactions = 0
    summary = None              # text of the latest compaction summary; msgs[1] is then its user message
    last_ptok = None            # prompt_tokens of the previous model call; ADK's compaction trigger reads exactly this
    capped = bool(max_time_s) and max_time_s > 0   # max_time_s <= 0 means no wall cap
    tid = task["instance_id"]
    stats = {"end_reason": None, "turns": 0, "tool_counts": {}, "edit_ok": 0, "edit_err": 0,
             "first_edit_call": None, "no_tool_turns": 0, "length_turns": 0,
             "nudges": 0, "max_consecutive_nudges": 0}
    LAST_RUN = stats
    turn_had_tool = False       # kaggle nudge mode: did the current ADK turn execute a tool call?
    consecutive_nudges = 0
    while calls < max_tool_calls and not submitted:
        if capped and time.time() - t0 > max_time_s:      # scorer parity: 8-min wall budget per task
            _p(f"  [stopping: wall budget {max_time_s:.0f}s exhausted]"); stats["end_reason"] = "wall"; break
        if stats["turns"] >= MAX_TURNS:                   # scorer parity: 'Max loop iterations: 80 turns'
            _p(f"  [stopping: {MAX_TURNS} turns]"); stats["end_reason"] = "turn_cap"; break
        if use_compaction and last_ptok is not None and last_ptok >= COMPACTION_TOKEN_THRESHOLD:
            try:
                out = adk_compact(msgs, summary, model, tid, stats, last_ptok)
            except Exception as e:      # a harness bug here must be visible but must not kill the run
                _trace(task=tid, kind="compaction_error", turn=stats["turns"], error=repr(e)[:300])
                _p(f"  [compaction error: {e!r}]")
                out = None
            if out:
                msgs, summary = out
                compactions += 1
        t_chat = time.time()
        try:
            resp = chat_retry(msgs, model, stats, tid)
        except Exception as e:
            _p(f"  [chat error: {e}]"); stats["end_reason"] = f"chat_error:{type(e).__name__}"; break
        ch0 = resp["choices"][0]
        m = ch0["message"]
        if SERVER_KIND == "vllm":
            # vLLM names the thought field `reasoning` (llama-server: `reasoning_content`) and returns null
            # audio/refusal/function_call fields; normalize so traces and compaction see the same shape.
            m = {k: v for k, v in m.items() if v is not None and k not in ("annotations",)}
            if "reasoning" in m:
                m["reasoning_content"] = m.pop("reasoning")
            ch0["message"] = m
        last_ptok = (resp.get("usage") or {}).get("prompt_tokens") or last_ptok
        msgs.append(m)
        tcs = m.get("tool_calls") or []
        stats["turns"] += 1
        if ch0.get("finish_reason") == "length":
            stats["length_turns"] += 1
        _trace(task=tid, kind="turn", turn=stats["turns"], t=round(time.time() - t0, 1),
               secs=round(time.time() - t_chat, 1), finish=ch0.get("finish_reason"),
               ptok=(resp.get("usage") or {}).get("prompt_tokens"),
               ctok=(resp.get("usage") or {}).get("completion_tokens"),
               reasoning_chars=len(m.get("reasoning_content") or ""),
               content_chars=len(m.get("content") or ""),
               tools=[t["function"]["name"] for t in tcs],
               reasoning_head=(m.get("reasoning_content") or "")[:300],
               content_head=(m.get("content") or "")[:300],
               tmg={k: (round(v, 1) if isinstance(v, float) else v)
                    for k, v in (resp.get("timings") or {}).items()
                    if k in ("prompt_n", "cache_n", "prompt_ms", "predicted_n", "predicted_ms", "predicted_per_second")})
        if not tcs:
            # no tool call this turn -> NUDGE to act (do not stop on empty; that was a bug)
            txt = (m.get("content") or "").strip()
            fr = ch0.get("finish_reason")
            _p(f"  [text/{fr}] {txt[:150]!r}")
            if TRACE_FILE and stats["no_tool_turns"] == 0:
                # keep the exact conversation that preceded the first stall so it can be replayed under other settings
                with open(f"{TRACE_FILE}.stall.{tid}.json", "w", encoding="utf-8") as sf:
                    json.dump({"task": tid, "finish": fr, "messages_before": msgs[:-1], "stalled_message": m}, sf, ensure_ascii=False)
            stats["no_tool_turns"] += 1
            if NUDGE_MODE == "kaggle":
                consecutive_nudges = 0 if turn_had_tool else consecutive_nudges + 1
                if consecutive_nudges > KAGGLE_MAX_NUDGES:
                    _p(f"  [stopping: continuation nudges exhausted]"); stats["end_reason"] = "nudges_exhausted"; break
                both = txt + (m.get("reasoning_content") or "")
                if "<|tool_call>" in both and "<tool_call|>" not in both:
                    kind = "unclosed"
                elif fr == "length":
                    kind = "length"
                else:
                    kind = "stop"
                stats["nudges"] += 1
                stats["max_consecutive_nudges"] = max(stats["max_consecutive_nudges"], consecutive_nudges)
                _trace(task=tid, kind="nudge", turn=stats["turns"], consecutive=consecutive_nudges, nudge_kind=kind,
                       had_tool_in_turn=turn_had_tool)
                msgs.append({"role": "user", "content": KAGGLE_NUDGE_TEXT[kind]})
                turn_had_tool = False
                continue
            no_tool_strikes += 1
            if no_tool_strikes >= MAX_NO_TOOL:
                _p(f"  [stopping: {MAX_NO_TOOL} no-tool turns]"); stats["end_reason"] = "no_tool_strikes"; break
            msgs.append({"role": "user", "content": "You have NOT made a tool call. Do NOT reply with prose. Call edit_file now to apply the fix, or submit_patch if already edited. You MUST call a tool."})
            continue
        no_tool_strikes = 0  # reset: the model acted
        turn_had_tool = True
        for tc in tcs:
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            if not isinstance(args, dict):
                args = {}
            missing = _missing_required(fn, args) if PARITY else None
            # scorer parity: get_status is FREE; so are calls ADK rejects at validation (missing mandatory params or an
            # unknown tool name) -- armA/rich_3882 logged 43 such edit_file calls and never hit the 28-call budget.
            is_free = (fn == "get_status") or (PARITY and (missing is None or bool(missing)))
            if fn == "get_status":
                free_status_used += 1
            elif not is_free:
                calls += 1
            _p(f"  [{calls}{'(free)' if is_free else ''}] {fn}({', '.join(f'{k}={str(v)[:40]!r}' for k,v in args.items())})")
            try:
                if PARITY and missing:
                    result = _adk_missing_msg(fn, missing)
                elif fn == "get_status":
                    if PARITY:
                        elapsed = (time.time() - t0) if capped else stats["turns"] * VCLOCK_S_PER_TURN
                        limit = float(max_time_s) if capped else REAL_MAX_TIME_S
                        result = {"status": "ok", "tool_calls_used": calls, "patch_submitted": submitted,
                                  "patch_size": submitted_size, "tool_calls_remaining": max(0, max_tool_calls - calls),
                                  "max_tool_calls": max_tool_calls, "time_seconds_remaining": max(0.0, limit - elapsed),
                                  "max_time_minutes": limit / 60.0, "agent_elapsed_seconds": elapsed,
                                  "max_turns": MAX_TURNS, "command_timeout_seconds": CMD_TIMEOUT}
                    else:
                        result = {"status": "ok", "tool_calls_used": calls,
                                  "tool_calls_remaining": max(0, max_tool_calls - calls),
                                  "max_tool_calls": max_tool_calls,
                                  "time_seconds_remaining": max(0.0, float(max_time_s) - (time.time() - t0)) if capped else 99999.0,
                                  "agent_elapsed_seconds": round(time.time() - t0, 1),
                                  "max_turns": MAX_TURNS,
                                  "patch_submitted": submitted,
                                  "patch_size": len(git(["diff", task["base_commit"]]).stdout)}
                elif fn == "submit_patch":
                    submitted = True
                    if PARITY:
                        sp = final_patch(task["base_commit"])
                        submitted_size = len(sp)
                        result = {"status": "ok", "patch_size": submitted_size,
                                  "files_changed": len(re.findall(r"^diff --git ", sp, re.M))}
                    else:
                        result = {"status": "ok", "submitted": True}
                
                elif fn == "read_file":
                    result = tool_read_file(**args)
                elif fn == "search_code":
                    result = tool_search_code(**args)
                elif fn == "edit_file":
                    result = tool_edit_file(**args)
                elif fn == "run_command":
                    result = tool_run_command(**args)
                elif fn == "write_file":
                    result = tool_write_file(**args)
                elif fn == "search_similar_code":
                    result = GRAPH.search_similar_code(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                elif fn == "get_code_neighbors":
                    result = GRAPH.get_code_neighbors(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                elif fn == "get_code_subgraph":
                    if ACTIVE_TOOLS is TOOLS:
                        result = GRAPH.get_code_subgraph(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                    else:
                        result = tool_get_code_subgraph(**args)
                else:
                    result = {"status": "error", "error": f"unknown tool {fn}"}
            except (TypeError, AttributeError, ValueError, KeyError) as e:
                # model passed a bad/misnamed/mistyped argument -> tell it, don't crash the run
                result = {"status": "error", "error": f"bad arguments for {fn}: {e}"}
            if PARITY and not is_free and fn not in ("get_status", "submit_patch") and max_tool_calls >= 20:
                rem = max_tool_calls - calls
                if rem <= 10 and isinstance(result, dict):
                    result["budget_warning"] = (f"Only {rem} tool call(s) remaining ({calls}/{max_tool_calls} used). "
                                                "Finalize your edits and call submit_patch soon.")
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", str(calls)),
                         "content": json.dumps(result)[:RESULT_CAP]})
            stats["tool_counts"][fn] = stats["tool_counts"].get(fn, 0) + 1
            if fn == "edit_file":
                if stats["first_edit_call"] is None:
                    stats["first_edit_call"] = calls
                stats["edit_ok" if result.get("status") == "ok" else "edit_err"] += 1
            _trace(task=tid, kind="tool", turn=stats["turns"], call=calls, tool=fn,
                   path=args.get("path") or args.get("filepath"), start=args.get("start_line"), end=args.get("end_line"),
                   query=args.get("query"),
                   args_head=json.dumps(args, ensure_ascii=False)[:200],
                   args_full=(json.dumps(args, ensure_ascii=False)[:3000] if fn in ("edit_file", "write_file") else None),
                   status=result.get("status"),
                   strategy=result.get("strategy"),
                   error=str(result.get("error") or result.get("error_message") or "")[:300])
            if submitted:
                break

    dur = time.time() - t0
    # capture the agent's patch (diff of working tree vs base)
    diff = final_patch(task["base_commit"]) if PARITY else git(["diff", task["base_commit"]]).stdout
    if stats["end_reason"] is None:
        stats["end_reason"] = "submitted" if submitted else "call_cap"
    stats.update(calls=calls, dur=round(dur), patch_chars=len(diff), submitted=submitted, compactions=compactions)
    _trace(task=tid, kind="end", **stats)
    _p(f"  [free get_status calls={free_status_used} compactions={compactions} last_prompt={last_ptok}tok]")
    return diff, calls, dur, submitted


_PYTEST_PY = None


def pytest_python():
    """Interpreter used to run the task tests. The interpreter that launched the gate may not have pytest
    (the .train_env one does not), which silently turned every verified patch into resolved=False."""
    global _PYTEST_PY
    if _PYTEST_PY is None:
        for c in (os.environ.get("GATE_PYTHON"), sys.executable, shutil.which("python3"), shutil.which("python")):
            if c and subprocess.run([c, "-c", "import pytest, rich"], capture_output=True).returncode == 0:
                _PYTEST_PY = c
                break
        else:
            raise RuntimeError("no interpreter with pytest and rich found; set GATE_PYTHON")
    return _PYTEST_PY


def verify(task, agent_diff):
    """Apply a patch to a clean checkout, apply the task's test_patch, run the task's tests.

    CONTRACT (used by batch.py and _gold_verify_rich.py): returns (passed: bool, log: str).
    Ground truth: applying the GOLD patch MUST return passed=True. If it does not, this function is
    broken and no agent result from this harness can be trusted."""
    base = task["base_commit"]
    reset_repo(base)
    repo = REPO
    steps = []
    if agent_diff.strip():
        pf = repo / "_agent.patch"
        ad = agent_diff.replace("\r\n", "\n")
        if not ad.endswith("\n"):
            ad += "\n"
        pf.write_text(ad, encoding="utf-8", newline="\n")
        r = git(["apply", "--whitespace=nowarn", "_agent.patch"])
        steps.append(f"apply agent patch: rc={r.returncode} {r.stderr[-300:]}")
        pf.unlink(missing_ok=True)
    tp = (task.get("test_patch") or "").strip()
    if tp:
        tf = repo / "_test.patch"
        tt = tp.replace("\r\n", "\n")
        if not tt.endswith("\n"):
            tt += "\n"
        tf.write_text(tt, encoding="utf-8", newline="\n")
        r = git(["apply", "--whitespace=nowarn", "_test.patch"])
        steps.append(f"apply test patch: rc={r.returncode} {r.stderr[-300:]}")
        tf.unlink(missing_ok=True)
    # which test files does this task's test_patch touch?
    touched = re.findall(r'\+\+\+ b/(tests/\S+\.py|test_\S+\.py|\S*tests?/\S+\.py)', tp or "")
    targets = sorted(set(touched)) or sorted(
        set(re.findall(r'def (test_\w+)', tp or "")) and
        [f for f in re.findall(r'--- a/(\S+\.py)', tp or "")] or [])
    if not targets:
        steps.append("no test files identified in test_patch")
    py = pytest_python()
    cmd = [py, "-m", "pytest", "-x", "-q"] + targets if targets else [py, "-m", "pytest", "-x", "-q"]
    timed_out = False
    try:
        pr = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=VERIFY_TIMEOUT)
        out = (pr.stdout or "") + (pr.stderr or "")
        steps.append(f"pytest {' '.join(targets) or '(auto)'} rc={pr.returncode}")
    except subprocess.TimeoutExpired:
        timed_out = True
        out = "PYTEST TIMED OUT"
        steps.append("pytest TIMED OUT")
    log = "\n".join(steps) + "\n---- pytest tail ----\n" + out[-4000:]
    return (bool(targets) and not timed_out and pr.returncode == 0), log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="rich_4077")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--max-tool-calls", type=int, default=15)
    ap.add_argument("--no-run-command", action="store_true",
                    help="remove run_command tool (forces edit, no repro rabbit-hole)")
    ap.add_argument("--temp", type=float, default=0.2, help="sampling temperature")
    ap.add_argument("--max-time", type=float, default=480.0,
                    help="per-task wall budget in seconds (scorer uses 480 = 8min); 0 = no cap")
    ap.add_argument("--no-compaction", action="store_true",
                    help="disable context compaction (restores pre-2026-10-13 behaviour for A/B)")
    ap.add_argument("--prompt-file", default=None,
                    help="path to a system.md to use instead of the built-in one")
    ap.add_argument("--thinking", choices=["on", "off"], default="on",
                    help="server-side thinking (chat_template_kwargs.enable_thinking)")
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--freq-penalty", type=float, default=0.0,
                    help="frequency_penalty (0.0 = off, payload unchanged)")
    ap.add_argument("--presence-penalty", type=float, default=0.0,
                    help="presence_penalty (0.0 = off, payload unchanged)")
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--trace", default=None, help="append per-turn JSONL trace to this file")
    args = ap.parse_args()
    global TEMPERATURE, THINKING, TOP_P, TOP_K, MAX_TOKENS, TRACE_FILE
    global FREQUENCY_PENALTY, PRESENCE_PENALTY
    TEMPERATURE = args.temp
    THINKING = args.thinking == "on"
    TOP_P, TOP_K = args.top_p, args.top_k
    FREQUENCY_PENALTY, PRESENCE_PENALTY = args.freq_penalty, args.presence_penalty
    if args.max_tokens:
        MAX_TOKENS = args.max_tokens
    TRACE_FILE = args.trace
    onoff = "off" if args.no_compaction else f"on(thr={COMPACTION_TOKEN_THRESHOLD},keep={EVENT_RETENTION})"
    print(f"[temperature={TEMPERATURE} top_p={TOP_P} top_k={TOP_K} thinking={args.thinking} "
          f"max_tokens={MAX_TOKENS} max_tool_calls={args.max_tool_calls} "
          f"max_time={'uncapped' if args.max_time <= 0 else f'{args.max_time:.0f}s'} compaction={onoff}]")
    if args.no_run_command:
        global TOOLS
        TOOLS = [t for t in TOOLS if t["function"]["name"] != "run_command"]
        print("[run_command REMOVED from tool set]")
    task = load_task(args.task)
    set_repo(task["repo"].split("/")[-1])
    sysprompt = None
    if args.prompt_file:
        sysprompt = Path(args.prompt_file).read_text(encoding="utf-8")
        # ADK injects {problem_description} from session.state (HARNESS_README 5.1). The live branch
        # prompt depends on it; without interpolation the model would see the literal placeholder.
        if "{problem_description}" in sysprompt:
            sysprompt = sysprompt.replace("{problem_description}", task["problem_statement"][:4000])
            print(f"[interpolated {{problem_description}}: {len(sysprompt)} chars]")
        print(f"[system prompt loaded from {args.prompt_file}]")
    print(f"=== LOCAL EVAL: {args.task} ({task['repo']}) model={args.model} ===")
    print(f"problem: {task['problem_statement'][:150].strip()}")
    diff, calls, dur, submitted = run_agent(task, args.model, args.max_tool_calls,
                                           system_prompt=sysprompt,
                                           max_time_s=args.max_time,
                                           use_compaction=not args.no_compaction)
    print(f"\nagent: tool_calls={calls} duration={dur:.0f}s submitted={submitted} patch_chars={len(diff)}")
    if not diff.strip():
        print("RESULT: no patch produced -> NOT RESOLVED")
        return
    passed, log = verify(task, diff)
    print(f"\n=== VERIFY: {'RESOLVED [PASS]' if passed else 'NOT RESOLVED [FAIL]'} ===")
    print(log.encode("ascii", "replace").decode()[-1500:])


if __name__ == "__main__":
    main()
