"""Gemma-4 native tool-call parser (torch-free, unit-testable).
Dialect (from E2B output + g4kit intel):
  call:name("positional")             e.g. call:search_code("isatty")
  call:name{key:value, key2:"value"}  e.g. call:edit_file{path:..., old_string:"...", new_string:"..."}
  call:name()                         e.g. call:submit_patch()
Brace form has UNQUOTED keys and values with quotes/commas -> not valid JSON; parse tolerantly.
Returns OpenAI-shaped tool_calls: [{"id","type":"function","function":{"name","arguments":json}}]."""
import re, json

TOOL_NAMES = ("read_file","search_code","edit_file","run_command","submit_patch",
              "write_file","get_status","get_code_neighbors","search_similar_code","get_code_subgraph")
_ARG_KEYS = ("path","start_line","end_line","query","old_string","new_string","command","content",
             "filepath","node","edge_type","max_neighbors","nodes","k","allow_multiple")

def _split_top_level(s, sep=","):
    out, depth, i, start, q = [], 0, 0, 0, None
    while i < len(s):
        c = s[i]
        if q:
            if c == q and (i == 0 or s[i-1] != "\\"): q = None
        elif c in "\"'": q = c
        elif c in "{[(": depth += 1
        elif c in ")]}": depth -= 1
        elif c == sep and depth == 0:
            out.append(s[start:i]); start = i+1
        i += 1
    out.append(s[start:])
    return [x for x in out if x.strip()]

def _coerce(v):
    v = v.strip()
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        inner = v[1:-1]
        if "\\" in inner:
            try: return inner.encode().decode("unicode_escape")
            except Exception: return inner
        return inner
    if re.fullmatch(r"-?\d+", v): return int(v)
    if v in ("true","True"): return True
    if v in ("false","False"): return False
    return v

# primary positional arg per tool (for when the model mislabels the first key, e.g. uses the tool name)
_PRIMARY = {"search_code":"query","read_file":"path","run_command":"command","edit_file":"path",
            "write_file":"filepath","get_code_neighbors":"node","search_similar_code":"query"}

def _parse_brace_args(body, name=None):
    args = {}
    for part in _split_top_level(body):
        if ":" not in part: continue
        k, _, v = part.partition(":")
        k = k.strip().strip("\"'")
        # E2B sometimes labels the first arg with the TOOL NAME instead of 'path' -> remap to primary.
        if name and k == name and _PRIMARY.get(name):
            k = _PRIMARY[name]
        if k in _ARG_KEYS or re.fullmatch(r"[a-z_]+", k):
            args[k] = _coerce(v)
    # drop any stray key that equals the tool name (unmappable)
    args.pop(name, None) if name else None
    return args

_RE_BRACE  = re.compile(r'call:\s*(?P<name>[a-z_]+)\s*\{(?P<body>.*?)\}', re.S)
_RE_PAREN  = re.compile(r'call:\s*(?P<name>[a-z_]+)\s*\((?P<body>.*?)\)', re.S)
_RE_OPENAI = re.compile(r'\{\s*"name"\s*:\s*"(?P<name>[a-z_]+)"\s*,\s*"arguments"\s*:\s*(?P<args>\{.*?\})\s*\}', re.S)

def parse_tool_calls(text):
    calls = []
    def add(name, args):
        if name in TOOL_NAMES:
            calls.append({"id": f"c{len(calls)}", "type": "function",
                          "function": {"name": name, "arguments": json.dumps(args)}})
    for m in _RE_BRACE.finditer(text):
        add(m.group("name"), _parse_brace_args(m.group("body"), m.group("name")))
    for m in _RE_PAREN.finditer(text):
        name, body = m.group("name"), m.group("body").strip()
        if any(c["function"]["name"] == name for c in calls): continue
        if not body:
            add(name, {})
        else:
            prim = {"search_code":"query","read_file":"path","run_command":"command"}.get(name)
            val = _coerce(_split_top_level(body)[0]) if body else ""
            add(name, {prim: val} if prim else {})
    if not calls:
        for m in _RE_OPENAI.finditer(text):
            try: add(m.group("name"), json.loads(m.group("args")))
            except Exception: pass
    seen, uniq = set(), []
    for c in calls:
        key = (c["function"]["name"], c["function"]["arguments"])
        if key not in seen:
            seen.add(key); uniq.append(c)
    return uniq


if __name__ == "__main__":
    # unit tests on the EXACT strings E2B emitted + the kwarg-brace edit form
    cases = [
        'call:search_code("isatty")',
        'call:read_file{path:textualize/rich/utils.py,start_line:1,end_line:100}',
        'call:edit_file{path:rich/file_proxy.py,old_string:"def isatty(self):",new_string:"def isatty(self):\\n    return self.__file.isatty()"}',
        'call:submit_patch()',
        'I will now call:run_command{command:grep -n isatty rich/console.py} to find it.',
    ]
    for c in cases:
        r = parse_tool_calls(c)
        print(f"IN : {c[:70]}")
        print(f"OUT: {r}\n")
    # assertions
    assert parse_tool_calls(cases[0])[0]["function"]["name"] == "search_code"
    assert json.loads(parse_tool_calls(cases[0])[0]["function"]["arguments"])["query"] == "isatty"
    a = json.loads(parse_tool_calls(cases[1])[0]["function"]["arguments"])
    assert a["path"].endswith("utils.py") and a["start_line"] == 1 and a["end_line"] == 100
    e = json.loads(parse_tool_calls(cases[2])[0]["function"]["arguments"])
    assert e["old_string"] == "def isatty(self):" and "return self.__file.isatty()" in e["new_string"]
    assert parse_tool_calls(cases[3])[0]["function"]["name"] == "submit_patch"
    assert json.loads(parse_tool_calls(cases[4])[0]["function"]["arguments"])["command"].startswith("grep")
    print("ALL PARSER TESTS PASS")
