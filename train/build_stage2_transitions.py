"""Stage-2 data: FastAPI failure-pattern transitions (buggy->fixed) from gold patches.
Teaches the REPAIR MOVE: given a problem + the buggy hunk, emit the correct edit in FastAPI's idiom.
Enforces the pre-registered held-out split + a function-overlap guard (no train task may touch a
function that a held-out test task touches), so a specialist win = generalization, not memorization.

Output: JSONL {"text": <instruction + buggy context -> fixed edit>}. Short decision-window format.
Also emits a GENERALIST mix (rich+fastapi+requests) at the same example budget for the baseline arm."""
import json, re, os, random
from pathlib import Path

TASKS = Path(__file__).parent.parent / "comp_files" / "tasks.jsonl"
OUTDIR = Path(__file__).parent / "data"; OUTDIR.mkdir(parents=True, exist_ok=True)

HELD_OUT = {"fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"}

def load():
    return [json.loads(l) for l in open(TASKS, encoding="utf-8")]

# ubiquitous names that are NOT distinctive -> excluding them prevents false-positive overlap drops
# (e.g. every class has __init__; many tasks touch read_users in docs examples).
_GENERIC = {"__init__","__call__","__repr__","__eq__","__str__","__enter__","__exit__",
            "read_users","read_item","read_items","main","app","get","post","root","index"}

def funcs_in_patch(patch):
    """DISTINCTIVE function/method names a patch touches (for the leakage overlap guard).
    Only names defined/edited (def/class lines) count; generic dunders/example names excluded."""
    names = set()
    for m in re.finditer(r'^[+\- ]\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', patch, re.M):
        names.add(m.group(1))
    # also the symbol named in a hunk header, if it's a def/class context
    for m in re.finditer(r'@@[^@]*@@\s*(?:async def|def|class)\s+([A-Za-z_]\w*)', patch):
        names.add(m.group(1))
    return {n for n in names if n and not n.isdigit() and n not in _GENERIC}

def hunks(patch):
    """yield (file, hunk_text) for each @@ hunk."""
    cur_file = None; buf = []; fname = None
    for ln in patch.splitlines():
        if ln.startswith('+++ b/'):
            fname = ln[6:]
        elif ln.startswith('@@'):
            if buf: yield (cur_file, "\n".join(buf)); buf=[]
            cur_file = fname; buf=[ln]
        elif cur_file is not None:
            buf.append(ln)
    if buf and cur_file: yield (cur_file, "\n".join(buf))

# LONG mode (set by --long): raise the edit-size caps so the training argument-length distribution
# matches eval (real locates/edits are long). Short mode keeps the original tight caps.
LONG_MODE = False
OLD_CAP = 600; NEW_CAP = 700
LONG_OLD_CAP = 2000; LONG_NEW_CAP = 2200

def hunk_old_new(hunk):
    """From a unified-diff hunk, reconstruct the old_string (context+removed) and new_string
    (context+added) blocks as the agent's edit_file would need them. Returns (old, new) or None."""
    old_lines, new_lines = [], []
    for ln in hunk.splitlines():
        if ln.startswith("@@") or ln.startswith("+++") or ln.startswith("---"):
            continue
        if ln.startswith("+"):
            new_lines.append(ln[1:])
        elif ln.startswith("-"):
            old_lines.append(ln[1:])
        elif ln.startswith(" "):
            old_lines.append(ln[1:]); new_lines.append(ln[1:])
    old = "\n".join(old_lines).strip("\n"); new = "\n".join(new_lines).strip("\n")
    if not old or old == new:
        return None
    oc, nc = (LONG_OLD_CAP, LONG_NEW_CAP) if LONG_MODE else (OLD_CAP, NEW_CAP)
    if len(old) > oc or len(new) > nc:
        return None
    return old, new

def _esc(s):  # render a value for the gemma4 call:name{...} brace form the model must emit
    return s.replace("\\", "\\\\").replace("\n", "\\n")

def transition_text(task):
    """Build a TERSE AGENT TRAJECTORY (fix #1): the exact tool-call sequence the model should emit to
    resolve this issue - locate -> read -> edit (real gold old/new) -> submit. Minimal thought, ONE
    tool call per turn, NO narration/apology. This matches what the eval harness parses and scores,
    teaching LOOP DISCIPLINE + the fix, not essay-writing."""
    patch = task["patch"]
    added = sum(1 for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++'))
    if added > 60:
        return None
    ps = task["problem_statement"].strip()
    for marker in ["## Pull Request","<!--","## Checklist","## AI Disclaimer"]:
        i = ps.find(marker)
        if i != -1: ps = ps[:i].strip()
    ps = ps[:500]
    hs = list(hunks(patch))
    if not hs: return None
    # SHORT mode: first clean small hunk (single decision point).
    # LONG mode: ALL clean hunks (up to 4) -> a multi-edit trajectory, so training arg-length
    # distribution + multi-edit discipline match real tasks.
    edits = []  # list of (efile, old, new)
    for f, h in hs:
        on = hunk_old_new(h)
        if on:
            edits.append((f, on[0], on[1]))
            if not LONG_MODE:
                break
    if not edits:
        return None
    edits = edits[:4]
    # locate symbol from the first edit's old block
    first_old = edits[0][1]
    sym = None
    for tok in first_old.replace("("," ").replace(":"," ").split():
        if tok.isidentifier() and len(tok) > 3:
            sym = tok; break
    sym = sym or "def"
    efile = edits[0][0]
    # Emit STRUCTURED MESSAGES (fix #1b): one user turn (problem) + one assistant turn whose content is
    # the terse tool-call sequence the model must produce. The trainer renders these via the model's
    # chat template and masks loss to the assistant turn - so the model learns
    # "<start_of_turn>model -> call:...", exactly matching eval. No raw USER:/ASSISTANT: text.
    user = (f"Repository: fastapi/fastapi\n\nProblem:\n{ps}\n\nFix the bug. Locate fast, edit, submit_patch.")
    edit_calls = "\n".join(
        f"call:edit_file{{path:{ef},old_string:\"{_esc(o)}\",new_string:\"{_esc(n)}\"}}"
        for ef, o, n in edits
    )
    assistant = (
        f"call:search_code{{query:{_esc(sym)}}}\n"
        f"call:read_file{{path:{efile}}}\n"
        f"{edit_calls}\n"
        f"call:submit_patch{{}}"
    )
    return {"messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": assistant}]}

def repo_of(t): return t["repo"].split("/")[-1]

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", action="store_true", help="long-arg mode: raise edit caps + multi-hunk")
    cli = ap.parse_args()
    global LONG_MODE
    LONG_MODE = cli.long
    suffix = "_long" if LONG_MODE else ""
    print(f"[mode] LONG={LONG_MODE} caps old/new = "
          f"{(LONG_OLD_CAP,LONG_NEW_CAP) if LONG_MODE else (OLD_CAP,NEW_CAP)}")
    random.seed(0)
    tasks = load()
    # held-out function names (overlap guard)
    held_funcs = set()
    for t in tasks:
        if t["instance_id"] in HELD_OUT:
            held_funcs |= funcs_in_patch(t["patch"])
    print("held-out function names (overlap guard):", sorted(held_funcs)[:20], "...total", len(held_funcs))

    fa_train, dropped_overlap = [], []
    for t in tasks:
        if not repo_of(t) == "fastapi": continue
        if t["instance_id"] in HELD_OUT: continue
        tf = funcs_in_patch(t["patch"])
        if tf & held_funcs:  # shares a touched function with a held-out task -> drop (leakage guard)
            dropped_overlap.append((t["instance_id"], sorted(tf & held_funcs)))
            continue
        ex = transition_text(t)
        if ex: fa_train.append(ex)
    print(f"FastAPI Stage-2 train transitions: {len(fa_train)} (dropped {len(dropped_overlap)} for function overlap)")
    for i,ov in dropped_overlap[:8]: print(f"  dropped {i}: shares {ov}")

    # write specialist Stage-2 (structured messages)
    sp = OUTDIR / f"stage2_fastapi_transitions{suffix}.jsonl"
    with open(sp, "w", encoding="utf-8") as f:
        for r in fa_train: f.write(json.dumps(r) + "\n")
    print(f"wrote {sp} ({len(fa_train)} examples)")

    if LONG_MODE:
        tok = sum(len(json.dumps(r['messages'])) for r in fa_train) // 4
        print(f"specialist Stage-2 LONG ~{tok} model-tokens est. (generalist mix skipped in long mode)")
        return
    # GENERALIST mix: other-repo transitions (correct repo in the user turn)
    others = []
    for t in tasks:
        r = repo_of(t)
        if r == "fastapi": continue
        if r not in ("rich","requests","httpx"): continue
        ex = transition_text(t)
        if ex:
            # fix the repo label in the user turn (transition_text hardcodes fastapi)
            ex["messages"][0]["content"] = ex["messages"][0]["content"].replace(
                "Repository: fastapi/fastapi", f"Repository: {t['repo']}")
            others.append(ex)
    random.shuffle(others)
    n = len(fa_train); half = n // 2
    gen = fa_train[:half] + others[:n-half]
    random.shuffle(gen)
    gp = OUTDIR / "stage2_generalist_mix.jsonl"
    with open(gp, "w", encoding="utf-8") as f:
        for r in gen: f.write(json.dumps(r) + "\n")
    print(f"wrote {gp} ({len(gen)} examples: {half} fastapi + {n-half} other-repo)")
    tok = sum(len(json.dumps(r['messages'])) for r in fa_train) // 4
    print(f"specialist Stage-2 ~{tok} model-tokens est.")

if __name__ == "__main__":
    main()
