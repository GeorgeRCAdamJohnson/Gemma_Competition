import json, re, sys, os

HERE = os.path.dirname(__file__)
REFS = {
    "verra_0.18": "refs/verra/gemma-4-agent-budget-fit-single-agent.ipynb",
    "honghanh_0.24": "refs/honghanh/gemma-4-baseline-lb-0-24.ipynb",
    "lavinwins": "refs/lavinwins/gemma-4-autonomous-developer-agent-calibrated-sin.ipynb",
    "dmitrii": "refs/dmitrii/gemma-4-measure-before-you-tune.ipynb",
}

def allsrc(path):
    nb = json.load(open(os.path.join(HERE, path), encoding="utf-8"))
    cells = nb.get("cells", nb) if isinstance(nb, dict) else nb
    out = []
    for c in cells:
        if c.get("cell_type") == "code":
            out.append("".join(c.get("source", [])))
    return "\n\n# ===CELL===\n\n".join(out)

def grab(src, patterns, ctx=0):
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, src, re.I):
            s = max(0, m.start()-ctx); e = min(len(src), m.end()+ctx)
            hits.append(src[s:e])
    return hits

for name, path in REFS.items():
    try:
        src = allsrc(path)
    except Exception as e:
        print(f"\n##### {name}: FAILED {e}"); continue
    print(f"\n{'='*80}\n##### {name}  ({len(src)} chars src)\n{'='*80}")
    # model line
    for m in re.findall(r'model:\s*\S+', src):
        print("MODEL:", m)
    # eval budget knobs
    for key in ["max_tool_calls", "max_time_minutes", "max_turns", "timeout_seconds",
                "thinking_budget", "max_output_tokens", "temperature", "top_p", "top_k",
                "include_thoughts", "thinking_level", "frequency_penalty"]:
        vals = re.findall(rf'{key}\s*[:=]\s*[^\n,}}#]+', src)
        if vals:
            print(f"{key}: {sorted(set(v.strip() for v in vals))[:4]}")
    # tools list fingerprint
    for t in ["run_command","read_file","edit_file","write_file","get_status","submit_patch",
              "get_code_neighbors","search_similar_code","get_code_subgraph"]:
        if re.search(rf'[\'"\- ]{t}\b', src):
            print("  tool?:", t)
    # agents / analyzer / sub_agents
    for kw in ["sub_agents","analyzer","ParallelAgent","LoopAgent","reviewer","reconciler","SequentialAgent","adapter"]:
        if re.search(kw, src, re.I):
            print("  structure kw:", kw)
