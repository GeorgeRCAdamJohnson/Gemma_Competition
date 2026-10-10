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
import argparse, json, subprocess, re, os, sys, time, urllib.request
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
]

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


def resolve_path(p):
    p = str(p).strip().lstrip("/")
    if p.startswith("workspace/"):
        p = p[len("workspace/"):]
    return REPO / p


def tool_read_file(path, start_line=None, end_line=None):
    fp = resolve_path(path)
    if not fp.exists():
        return {"status": "error", "error": f"not found: {path}"}
    lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    s = max(1, int(start_line)) if start_line else 1
    e = min(total, int(end_line)) if end_line else min(total, s + 149)
    if e - s + 1 > 150:
        e = s + 149
    # Return RAW content exactly like the real swegemma read_file (no 'N: ' prefix in the body).
    # Line numbers are metadata only (start_line/end_line), NOT embedded in content. Injecting
    # 'N: ' prefixes trained the model to echo prefixed lines into edit_file old/new_string, which
    # then never matched the real file -> no-op / mangled edits. This was a HARNESS bug, not the model.
    body = "\n".join(lines[s-1:e])
    return {"status": "ok", "path": path, "start_line": s, "end_line": e,
            "total_lines": total, "content": body[:10000],
            "is_truncated": e < total}


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


def tool_edit_file(path, old_string, new_string):
    fp = resolve_path(path)
    if not fp.exists():
        return {"status": "error", "error": f"not found: {path}"}
    txt = fp.read_text(encoding="utf-8", errors="replace")
    if old_string not in txt:
        # retry after stripping any echoed line-number prefixes
        old_string = _strip_line_numbers(old_string)
        new_string = _strip_line_numbers(new_string)
    if old_string not in txt:
        return {"status": "error", "error": "old_string not found (after line-number strip). Provide the EXACT code text WITHOUT any leading line numbers."}
    if old_string == new_string:
        return {"status": "error", "error": "old_string and new_string are identical - no change. Provide the corrected code in new_string."}
    if txt.count(old_string) > 1:
        return {"status": "error", "error": f"old_string matches {txt.count(old_string)}x; make it unique"}
    fp.write_text(txt.replace(old_string, new_string, 1), encoding="utf-8")
    return {"status": "ok", "path": path}


def tool_run_command(command):
    try:
        r = subprocess.run(command, cwd=REPO, shell=True, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "command timed out (120s)"}
    out = ((r.stdout or "") + (r.stderr or ""))[:5000]
    return {"status": "ok" if r.returncode == 0 else "error", "exit_code": r.returncode, "output": out}


TEMPERATURE = 0.2
# Per-turn generation cap. 1536 was TOO LOW: it truncated longer multiline edit_file new_string
# arguments mid-token (observed '...bo' cut-offs), producing mangled/no-op edits that looked like
# model failures but were our cap clipping the tool-call JSON. Raise so a full multiline edit fits;
# runaway-thinking is handled by the system prompt ("1-2 sentences then a tool call"), not this cap.
MAX_TOKENS = 4096
QUIET = False  # batch mode sets True to suppress noisy per-call prints (avoid console encoding crashes)

def _p(*a):
    if not QUIET:
        try: print(*a)
        except Exception: pass

def chat(messages, model):
    payload = {"model": model, "messages": messages, "tools": TOOLS,
               "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "stream": False}
    req = urllib.request.Request(OLLAMA, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def run_agent(task, model, max_tool_calls, system_prompt=None):
    reset_repo(task["base_commit"])
    load_graph_for_task(task["repo"].split("/")[-1], task["base_commit"])
    msgs = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
        {"role": "user", "content": f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."},
    ]
    calls = 0
    t0 = time.time()
    submitted = False
    no_tool_strikes = 0
    while calls < max_tool_calls and not submitted:
        try:
            resp = chat(msgs, model)
        except Exception as e:
            _p(f"  [chat error: {e}]"); break
        m = resp["choices"][0]["message"]
        msgs.append(m)
        tcs = m.get("tool_calls") or []
        if not tcs:
            # no tool call this turn -> NUDGE to act (do not stop on empty; that was a bug)
            txt = (m.get("content") or "").strip()
            fr = resp["choices"][0].get("finish_reason")
            _p(f"  [text/{fr}] {txt[:150]!r}")
            no_tool_strikes += 1
            if no_tool_strikes >= 4:
                _p("  [stopping: 4 no-tool turns]"); break
            msgs.append({"role": "user", "content": "You have NOT made a tool call. Do NOT reply with prose. Call edit_file now to apply the fix, or submit_patch if already edited. You MUST call a tool."})
            continue
        no_tool_strikes = 0  # reset: the model acted
        for tc in tcs:
            calls += 1
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            _p(f"  [{calls}] {fn}({', '.join(f'{k}={str(v)[:40]!r}' for k,v in args.items())})")
            try:
                if fn == "submit_patch":
                    submitted = True
                    result = {"status": "ok", "submitted": True}
                elif fn == "read_file":
                    result = tool_read_file(**args)
                elif fn == "search_code":
                    result = tool_search_code(**args)
                elif fn == "edit_file":
                    result = tool_edit_file(**args)
                elif fn == "run_command":
                    result = tool_run_command(**args)
                elif fn == "search_similar_code":
                    result = GRAPH.search_similar_code(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                elif fn == "get_code_neighbors":
                    result = GRAPH.get_code_neighbors(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                elif fn == "get_code_subgraph":
                    result = GRAPH.get_code_subgraph(**args) if GRAPH else {"status": "error", "error": "no code graph available for this task"}
                else:
                    result = {"status": "error", "error": f"unknown tool {fn}"}
            except (TypeError, AttributeError, ValueError, KeyError) as e:
                # model passed a bad/misnamed/mistyped argument -> tell it, don't crash the run
                result = {"status": "error", "error": f"bad arguments for {fn}: {e}"}
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", str(calls)),
                         "content": json.dumps(result)[:3000]})
            if submitted:
                break
    dur = time.time() - t0
    # capture the agent's patch (diff of working tree vs base)
    diff = git(["diff", task["base_commit"]]).stdout
    return diff, calls, dur, submitted


def verify(task, agent_diff):
    """Apply agent diff to a fresh checkout, apply test_patch, run the target tests."""
    reset_repo(task["base_commit"])
    # apply agent patch
    if agent_diff.strip():
        p = REPO / "_agent.patch"
        ad = agent_diff.replace("\r\n", "\n")
        if not ad.endswith("\n"):
            ad += "\n"
        p.write_text(ad, encoding="utf-8", newline="\n")
        a = git(["apply", "--whitespace=fix", "_agent.patch"])
        if a.returncode != 0:
            a = git(["apply", "--3way", "_agent.patch"])
        if a.returncode != 0:
            git(["apply", "--reject", "--whitespace=fix", "_agent.patch"])
        p.unlink(missing_ok=True)
    # reset any test files the agent touched, then apply the official test_patch (LF-normalized)
    tp = REPO / "_test.patch"
    data = task["test_patch"].replace("\r\n", "\n")
    if not data.endswith("\n"):
        data += "\n"
    tp.write_text(data, encoding="utf-8", newline="\n")
    ap = git(["apply", "--whitespace=fix", "_test.patch"])
    if ap.returncode != 0:
        ap = git(["apply", "--3way", "_test.patch"])
    if ap.returncode != 0:
        ap = git(["apply", "--recount", "--whitespace=fix", "_test.patch"])
    tp.unlink(missing_ok=True)
    if ap.returncode != 0:
        return False, "test_patch failed to apply:\n" + ap.stderr[:1000]
    # find test files from test_patch and run them
    test_files = re.findall(r'\+\+\+ b/(\S+)', task["test_patch"])
    test_files = [f for f in test_files if f.endswith(".py")]
    if not test_files:
        return False, "no test files found in test_patch"
    try:
        r = subprocess.run([sys.executable, "-m", "pytest"] + test_files + ["-q", "--no-header", "-p", "no:cacheprovider"],
                           cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return False, "pytest timed out"
    passed = r.returncode == 0
    return passed, ((r.stdout or "") + (r.stderr or ""))[-2000:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="rich_4077")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--max-tool-calls", type=int, default=15)
    ap.add_argument("--no-run-command", action="store_true", help="remove run_command tool (forces edit, no repro rabbit-hole)")
    ap.add_argument("--temp", type=float, default=0.2, help="sampling temperature")
    args = ap.parse_args()
    global TEMPERATURE
    TEMPERATURE = args.temp
    print(f"[temperature={TEMPERATURE}]")
    if args.no_run_command:
        global TOOLS
        TOOLS = [t for t in TOOLS if t["function"]["name"] != "run_command"]
        print("[run_command REMOVED from tool set]")
    task = load_task(args.task)
    print(f"=== LOCAL EVAL: {args.task} ({task['repo']}) model={args.model} ===")
    print(f"problem: {task['problem_statement'][:150].strip()}")
    diff, calls, dur, submitted = run_agent(task, args.model, args.max_tool_calls)
    print(f"\nagent: tool_calls={calls} duration={dur:.0f}s submitted={submitted} patch_chars={len(diff)}")
    if not diff.strip():
        print("RESULT: no patch produced -> NOT RESOLVED"); return
    passed, log = verify(task, diff)
    print(f"\n=== VERIFY: {'RESOLVED [PASS]' if passed else 'NOT RESOLVED [FAIL]'} ===")
    print(log.encode('ascii', 'replace').decode()[-1200:])


if __name__ == "__main__":
    main()
