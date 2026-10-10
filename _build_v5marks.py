"""Generate v5m1/v5m2/v5m3 from v5's notebook_src.py: each = v5 + ONE lever inserted into system.md.
Also builds the .ipynb and kernel-metadata.json for each. Single-lever, clean A/B off the known-good v5."""
import os, re, json, nbformat
from pathlib import Path

ROOT = Path(r'c:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma')
V5 = (ROOT / 'submit_v5' / 'notebook_src.py').read_text(encoding='utf-8')

# The anchor: insert each lever section immediately AFTER the "conform to the pattern" block,
# i.e. right before the "## Workflow (tight)" heading in system.md.
WORKFLOW_ANCHOR = "## Workflow (tight)"
assert V5.count(WORKFLOW_ANCHOR) == 1, "anchor not unique"

# ---- the three levers (each a self-contained markdown section ending with a blank line) ----
LEVER_A = """## Make SURGICAL edits (smallest unique anchor)
When you call edit_file, do NOT paste a big multi-line block as old_string - large blocks frequently fail to match (whitespace, quotes, escaped chars like \\n or \\0) and waste your budget on retries. Instead: pick the SMALLEST UNIQUE snippet that identifies the spot (often a single line, or a signature/field-name anchor), and make the change around it. If a change spans several lines, do it as SEVERAL small edit_file calls, each with a tiny unique old_string, rather than one large replacement. Copy old_string VERBATIM from what read_file showed, exactly as-is.

"""

LEVER_B = """## Falsify your fix before you submit (one existing test)
Your own reasoning is not proof the patch is correct. After you make the edit and BEFORE submit_patch, run the SINGLE most relevant EXISTING test with run_command (e.g. `python3 -m pytest path/to/test_file.py::test_name -q` for the one test that exercises the changed behavior - never the whole suite, it times out). If it passes, submit. If it fails, read the failure, make ONE corrective edit, and submit. Prefer an existing repo test over a self-written one. submit_patch and get_status do NOT cost budget, so this check is nearly free - spend the call to catch a wrong patch.

"""

LEVER_C = """## Localize to the DEFINITION - distrust the problem's topic words
The problem statement's wording often points at the WRONG place. A problem titled about one concept is frequently fixed in a DIFFERENT file (e.g. a "table" issue fixed in markdown.py, a "newlines" issue fixed in ansi.py). Do NOT grep for the topic word and edit the first match. Instead: identify the concrete SYMBOL or the failing behavior, then follow it to the file that DEFINES that symbol (use get_code_neighbors to jump symbol->definition, or grep for `def <name>` / `class <name>`). Confirm you are at the DEFINING site, not a caller or a same-named-but-unrelated spot, before editing.

"""

MARKS = {
    "v5m1": dict(letter="A", name="surgical edits",
                 header="# v5m1 (A: SURGICAL EDITS) = v5 + smallest-unique old_string anchoring. Kills the edit-retry\n"
                        "# thrash (fastapi_15588 burned 4+ calls on 'old_string not found'). Helps ALL repos. One lever vs v5.\n",
                 lever=LEVER_A),
    "v5m2": dict(letter="B", name="falsifier-before-final",
                 header="# v5m2 (B: FALSIFIER-BEFORE-FINAL) = v5 + run ONE existing test before submit. Budget-shaped\n"
                        "# generate-and-validate (NOT Agentless N-sample). Attacks Type-B contract misses. One lever vs v5.\n",
                 lever=LEVER_B),
    "v5m3": dict(letter="C", name="symbol-following localization",
                 header="# v5m3 (C: SYMBOL-FOLLOWING LOCALIZATION) = v5 + follow symbol/test to DEFINING file, distrust\n"
                        "# topic words. Targets rich localization traps (rich_4079->markdown.py, rich_4076->ansi.py). One lever vs v5.\n",
                 lever=LEVER_C),
}

def make(markid, spec):
    src = V5
    # 1) replace the v5 header line (first comment line) with the mark's header
    src = re.sub(r"^# Gemma 4 Developer Agent — v5 .*\n", spec["header"], src, count=1)
    # 2) insert the lever section just before "## Workflow (tight)"
    src = src.replace(WORKFLOW_ANCHOR, spec["lever"] + WORKFLOW_ANCHOR, 1)
    # 3) retitle the printed agent-dir line + the SUMMARY banner
    src = src.replace("v5 = v3 prompt + tool_calls 22", f"{markid} ({spec['letter']}: {spec['name']})")
    src = src.replace("===== v5 A/B SUMMARY", f"===== {markid} ({spec['letter']}) A/B SUMMARY")
    outdir = ROOT / f"submit_{markid}"
    outdir.mkdir(exist_ok=True)
    (outdir / "notebook_src.py").write_text(src, encoding="utf-8")
    # kernel-metadata.json
    meta = json.loads((ROOT / 'submit_v5' / 'kernel-metadata.json').read_text(encoding='utf-8'))
    meta["id"] = f"comfyops/gemma-sibling-conform-{markid}"
    meta["title"] = f"Gemma Sibling-Conform {markid}"
    meta["code_file"] = f"gemma-sibling-conform-{markid}.ipynb"
    (outdir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # build ipynb
    parts, cur = [], []
    for line in src.splitlines(keepends=True):
        if line.startswith('# ===== CELL') and cur:
            parts.append(''.join(cur)); cur=[line]
        else:
            cur.append(line)
    if cur: parts.append(''.join(cur))
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(p.rstrip()+'\n') for p in parts]
    nb.metadata = {'kernelspec': {'name':'python3','display_name':'Python 3','language':'python'}, 'language_info': {'name':'python'}}
    nbformat.write(nb, str(outdir / f"gemma-sibling-conform-{markid}.ipynb"))
    # sanity: the lever must appear exactly once in the written source
    assert src.count(spec["lever"].splitlines()[0]) == 1, f"{markid} lever insert failed"
    print(f"{markid}: wrote notebook_src.py + ipynb ({len(nb.cells)} cells) + metadata; lever '{spec['letter']}' inserted")

for mid, spec in MARKS.items():
    make(mid, spec)
print("done")
