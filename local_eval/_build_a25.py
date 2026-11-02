"""Build A25 (multi-subagent router) kernel cells + prereg + push notebook from the A23 skeleton.

Changed axis vs v8 (the refuted sub-agent test):
  v8  = ONE code_analyzer agent_tool, skip_summarization TRUE, no directive saying when to use it.
        Failure modes found: sub-agent sessions never compact -> context overflow -> EMPTY PATCH;
        sub-agent shares the main call budget and burns it; weak tools.
  A25 = TWO specialists (code_locator, logic_analyst), skip_summarization FALSE (summarized
        bounded return), explicit classify-then-dispatch directive in workflow step 1,
        specialists NEVER edit (main agent keeps the single edit + submit), hard call caps
        in the specialist instructions (<=6 / <=4), one dispatch per task maximum.
Everything else (model, sampling, eval_config, base prompt text apart from the single
step-1 span, task cohort) is held identical to A3. Prereg: PREREG_A25_2026-10-27.md.
"""
import json, re, sys, os, hashlib
from pathlib import Path

LE = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval')
KS = LE / 'kern_src'

# ---------- cell1_a25.py ----------
c1 = (KS / 'cell1_a23.py').read_text(encoding='utf-8')

ROUTER_TAIL = (KS / '_a25_router_tail.py').read_text(encoding='utf-8')
c1 = c1.rstrip() + '\n' + ROUTER_TAIL
(KS / 'cell1_a25.py').write_text(c1, encoding='utf-8')
print('cell1_a25.py written:', len(c1), 'chars')

# ---------- cell3_a25.py ----------
c3 = (KS / 'cell3_a23.py').read_text(encoding='utf-8')

# 1) header comment block swap
old_hdr = c3[c3.index('# ARM TEST (2026-10-25)'):c3.index("STRAT6 = [")]
new_hdr = (
"# A25 MULTI-SUBAGENT ROUTER ARM TEST (2026-10-27): fresh A3 control vs A3+router+2 specialists.\n"
"# Closest prior: v8 sub-agent = board REGRESSION; mechanism = never-compact overflow + shared-budget\n"
"# sink + no dispatch directive. Changed axis: skip_summarization FALSE, TWO specialists, explicit\n"
"# classify-then-dispatch step-1 span, specialists never edit, call caps <=6/<=4, 1 dispatch max.\n"
"# Cohort: canary 4077 + flips 3471/3777/4079/3278 (STRAT6). REPS=2 -> 20 runs\n"
"# (~1.7h wall = ~6.9 GPU-h on L4x4). Prereg: PREREG_A25_2026-10-27.md. Rows keyed arm|rep|id.\n"
"#\n")
c3 = c3.replace(old_hdr, new_hdr, 1)

# 2) arms + dirs
c3 = c3.replace(
    "ARMS = ['A3', 'A23']   # A3 = prompts/system.md as written by CELL 2; A22 = system_a22.md",
    "ARMS = ['A3CTRL', 'ROUTER']   # A3CTRL = shipped A3 prompt in the plain dir; ROUTER = submission_router\n"
    "ARM_DIR = {'A3CTRL': AGENT_DIR, 'ROUTER': AGENT_DIR_R}", 1)

# 3) per-arm eval config construction
old_eval = """limits, gen_constraints = build_submission_limits()
eval_config = EvalConfig(
    tasks_path=TASKS_PATH, snapshots_dir=DATA_DIR / 'snapshots', results_dir=WORKING_DIR / 'results',
    submission_dir=AGENT_DIR, models=models, sandbox='subprocess',
    timeout_seconds=timeout_seconds, max_time_minutes=max_time_minutes,
    max_tool_calls=max_tool_calls, max_turns=max_turns,
    limits=limits, generation_constraints=gen_constraints, adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
        token_threshold=14336, event_retention_size=5),
    graph_dir=str(DATA_DIR / 'graphs'), embeddings_dir=str(DATA_DIR / 'embeddings'),
    wheels_dir=DATA_DIR / 'wheels', verbose=False,
)"""
new_eval = """limits, gen_constraints = build_submission_limits()
def _mk_eval(sub):
    # Per-arm evaluator: EvalConfig reads prompts/system.md via submission_dir AT CONSTRUCTION,
    # and the ROUTER arm lives in its own dir (different agent.yaml + sub_agents/).
    _raw = yaml.safe_load((sub / 'eval_config.yaml').read_text(encoding='utf-8'))
    _ev = _raw.get('evaluation', _raw)
    return EvalConfig(
        tasks_path=TASKS_PATH, snapshots_dir=DATA_DIR / 'snapshots', results_dir=WORKING_DIR / 'results',
        submission_dir=sub, models=models, sandbox='subprocess',
        timeout_seconds=int(_ev.get('timeout_seconds', 300)),
        max_time_minutes=float(_ev.get('max_time_minutes', 60.0)),
        max_tool_calls=int(_ev.get('max_tool_calls', 100)),
        max_turns=(int(_ev['max_turns']) if _ev.get('max_turns') is not None else None),
        limits=limits, generation_constraints=gen_constraints, adapter_manifest=adapters,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
            token_threshold=14336, event_retention_size=5),
        graph_dir=str(DATA_DIR / 'graphs'), embeddings_dir=str(DATA_DIR / 'embeddings'),
        wheels_dir=DATA_DIR / 'wheels', verbose=False,
    )"""
assert old_eval in c3, 'EvalConfig block anchor not found'
c3 = c3.replace(old_eval, new_eval, 1)

# 4) per-arm prompt install + evaluator rebuild inside the loop
old_blk = """    _sh.copyfile(AGENT_DIR / 'prompts' / PROMPT_SRC[_arm], AGENT_DIR / 'prompts' / 'system.md')
    evaluator = Evaluator(eval_config)"""
new_blk = """    _sub = ARM_DIR[_arm]
    _sh.copyfile(AGENT_DIR / 'prompts' / PROMPT_SRC[_arm], _sub / 'prompts' / 'system.md')
    evaluator = Evaluator(_mk_eval(_sub))"""
assert old_blk in c3, 'loop install anchor not found'
c3 = c3.replace(old_blk, new_blk, 1)

# 5) PROMPT_SRC mapping
c3 = c3.replace(
    "PROMPT_SRC = {'A3': 'system_a3.md', 'A23': 'system_a23.md'}",
    "PROMPT_SRC = {'A3CTRL': 'system_a3.md', 'ROUTER': 'system_router.md'}", 1)

# 6) tool_counts in enrich (needed to see whether/how often specialists were dispatched)
old_en = "    row.update(edit_file_calls=_cnt.get('edit_file', 0),"
new_en = ("    row['tool_counts'] = dict(_cnt)\n"
          "    row.update(edit_file_calls=_cnt.get('edit_file', 0),")
assert old_en in c3, 'enrich anchor not found'
c3 = c3.replace(old_en, new_en, 1)

(KS / 'cell3_a25.py').write_text(c3, encoding='utf-8')
print('cell3_a25.py written:', len(c3), 'chars')

# sanity: python-parse both cells
import ast
for f in ('cell1_a25.py', 'cell3_a25.py'):
    ast.parse((KS / f).read_text(encoding='utf-8'))
    print('parse OK:', f)

# ---------- PREREG ----------
PREREG = """# PREREG_A25 — MULTI-SUBAGENT ROUTER ARM (2026-10-27, written 2026-10-26)

## Question
Does giving the shipped agent a CATEGORIZE-THEN-DISPATCH sub-agent architecture raise
resolve rate on the STRAT6 coin-flip cohort?

## Closest prior test (Gemma Experiment History Gate)
- v8 "contract self-audit sub-agent" (GEMMA_EXPERIMENT_LOG L165): 1/6, REGRESSION vs v6 board.
- v3's code_analyzer sub-agent (L1075-1092, L1324-1342): sub-agent sessions NEVER COMPACT ->
  overflow EMPTIES the patch (3 of 5 losses in one arm); the sub-agent SHARES the main call
  budget (v4 trace: burned all 22 shared calls on rich_4079, garbage return, zero calls left
  for the edit); system.md never said WHEN to dispatch it (L3289).
- Conclusion recorded then: the sub-agent was a NET LIABILITY as configured.

## Changed axis vs v8 (this is the replication purpose, not a re-run)
| knob | v8 (refuted) | A25 router |
|---|---|---|
| specialists | 1 (code_analyzer) | 2 (code_locator, logic_analyst) |
| skip_summarization | TRUE (raw flood) | FALSE (summarized, bounded return) |
| dispatch policy | none in system.md | step-1 span: classify LOCATE/LOGIC/TEST-DRIVEN, <=1 dispatch |
| edit rights | implicit shared | specialists NEVER edit; main agent keeps the single edit+submit |
| specialist call cap | unbounded | <=6 (locator) / <=4 (logic), in instruction |
| prompt diff vs A3 | n/a | ONE substituted span (step 1), reversible, asserted in cell1 |

## Held constant
model gemma-4-31b-it-qat-w4a16-ct; sampling temp 0.2 / thinking 4096 / out 5000;
eval 8 min / 28 calls / 120 turns / 300 s; 9 base tools; A3 prompt text outside the one span;
cohort STRAT6 = canary 4077 + flips 3471/3777/4079/3278; REPS=2.

## Cohort + cost
2 arms x 5 tasks x 2 reps = 20 runs, ~1.7 h wall on L4x4 (~6.9 GPU-h). Quota refreshes 10-31.

## Decision rules (fixed before running)
- ROUTER >= CTRL + 2 net resolves of 10  -> axis is ALIVE; design A26 (widen cohort, 31B board path)
- ROUTER == CTRL +/- 1                   -> NULL; axis closed with the v8 refutation (architecture
  cannot help at this budget even with its mechanics fixed)
- ROUTER < CTRL - 1                      -> REGRESSION; sub-agent architecture permanently closed
- ANY router-arm overflow-emptying of the patch -> the never-compact mechanism survives
  skip_summarization=false; record and close the axis regardless of counts
- Secondary readout (not decision-grade at n=10): tool_counts show dispatch rate; if dispatch
  rate < 20% the directive is inert (measured separately as a directive failure, not an
  architecture failure)

## Known risks accepted
- Sub-agent calls share the 28-call budget (unfixable in schema) -> a dispatch can starve the
  edit; the instruction caps and the commit-by-remaining triggers are the mitigation.
- 20 runs at 5 binary tasks = wide error bars; this is a first-look gate, not a board claim.
"""
(LE / 'PREREG_A25_2026-10-27.md').write_text(PREREG, encoding='utf-8', newline='\r\n')
print('PREREG_A25_2026-10-27.md written')

# ---------- push notebook ----------
src_nb = json.loads((LE / 'push_31b_a23' / 'gemma-sibling-conform-31b-a23-arm.ipynb').read_text(encoding='utf-8'))
c1_txt = (KS / 'cell1_a25.py').read_text(encoding='utf-8')
c3_txt = (KS / 'cell3_a25.py').read_text(encoding='utf-8')
c1_old = (KS / 'cell1_a23.py').read_text(encoding='utf-8')
c3_old = (KS / 'cell3_a23.py').read_text(encoding='utf-8')

def norm(s):
    return re.sub(r'\s+', ' ', s).strip()

replaced = {'cell1': 0, 'cell3': 0}
for cell in src_nb.get('cells', []):
    if cell.get('cell_type') != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if norm(src)[:400] == norm(c1_old)[:400]:
        cell['source'] = c1_txt.splitlines(keepends=True)
        replaced['cell1'] += 1
    elif norm(src)[:400] == norm(c3_old)[:400]:
        cell['source'] = c3_txt.splitlines(keepends=True)
        replaced['cell3'] += 1
print('notebook cells replaced:', replaced)
assert replaced['cell1'] == 1 and replaced['cell3'] == 1, 'expected exactly one cell1 and one cell3 match'

out_nb = LE / 'push_31b_a25'
out_nb.mkdir(exist_ok=True)
# retarget titles inside the notebook (markdown cells may name the arm)
nb_txt = json.dumps(src_nb, indent=1, ensure_ascii=False)
nb_txt = nb_txt.replace('a23-arm', 'a25-sub').replace('A23', 'A25').replace('a22', 'a25')
(out_nb / 'gemma-sibling-conform-31b-a25-sub.ipynb').write_text(nb_txt, encoding='utf-8')
json.loads((out_nb / 'gemma-sibling-conform-31b-a25-sub.ipynb').read_text(encoding='utf-8'))
print('notebook valid JSON:', out_nb / 'gemma-sibling-conform-31b-a25-sub.ipynb')

km = json.loads((LE / 'push_31b_a23' / 'kernel-metadata.json').read_text(encoding='utf-8'))
km['slug'] = 'gemma-sibling-conform-31b-a25-sub'
km['title'] = 'Gemma Sibling-Conform 31b A25 subagent-router'
km['keywords'] = km.get('keywords', []) + ['a25']
(out_nb / 'kernel-metadata.json').write_text(json.dumps(km, indent=2), encoding='utf-8')
print('kernel-metadata.json written; slug =', km['slug'], '| kernel_type =', km.get('kernel_type'),
      '| machine =', km.get('machine_shape'), '| gpu =', km.get('accelerator'))
