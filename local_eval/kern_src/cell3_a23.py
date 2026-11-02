# ===== CELL 4: RICH-ONLY gate. Same recipe as v6b; only the task sample changes. =====
import asyncio, concurrent.futures, yaml
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
def run_sync(coro_or_fn, *args, **kwargs):
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())
raw = yaml.safe_load((AGENT_DIR / 'eval_config.yaml').read_text(encoding='utf-8'))
ev = raw.get('evaluation', raw)
timeout_seconds = int(ev.get('timeout_seconds', 300)); max_tool_calls = int(ev.get('max_tool_calls', 100))
max_time_minutes = float(ev.get('max_time_minutes', 60.0))
turns_raw = ev.get('max_turns', ev.get('max_llm_calls')); max_turns = int(turns_raw) if turns_raw is not None else None

# ============================================================================
# COVERAGE RUN 2026-10-16 -- purpose is WIDENING THE COIN-FLIP POOL, not beating 0.15.
#
# WHY THIS TASK SET (measured 2026-10-16, see GEMMA_EXPERIMENT_LOG "ITEM 2"):
# Gate discrimination is bounded by the COUNT OF COIN-FLIP TASKS in the gate, NOT by
# gate size. Simulated on the observed p_hat mix:
#   - adding p=0 never-resolve tasks changes P(arm>base) by NOTHING
#     (6 coin-flips + 0/6/42/123 dead tasks -> 0.575/0.572/0.578/0.580 at lift x1.5)
#   - adding COIN-FLIP tasks moves it a lot
#     (6/12/24/48 coin-flips -> 0.577/0.725/0.850/0.949 at lift x1.5)
# We have exactly 6 traced coin-flip tasks (rich_3278 .75, rich_3471 .25, rich_3676 .12,
# rich_3882 .92, rich_4077 .82, rich_4079 .18). That pool, not GPU hours, is the ceiling.
#
# So this run spends its budget on the 31 rich tasks that have NEVER been traced, one run
# each. Re-running the 6 known coin-flips is deliberately EXCLUDED: replicates shrink
# within-task noise but cannot add tasks, so they buy nothing here.
#
# The already-traced 17 rich tasks split 10 never-resolve (dead, worth re-confirming at
# zero value) + 7 live. The 31 below are the unknown set; any that resolve at least once
# is a confirmed coin-flip candidate and enters the pool for later repeats.
#
# CONFIG IS HELD AT v6w EXACTLY (28 tool calls / 80 turns / 8 min, thinking_budget 1024,
# temp 0.2, same 9-tool surface, same prompt). This is deliberate: the notebook's
# EvalConfig is driven by the eval_config.yaml it writes, so the gate runs at v6w's budget.
# p_hat is only comparable within one config, and the point is to extend the EXISTING
# v6w pool. (The separate budget-raise arm, scored ref 57276407 at 100/500/60, returned NO
# SCORE -- the scorer threw -- and a 242-run measurement then showed the budget axis is not
# binding anyway. See the eval_config comment below for the full three-revision history.)
# fastapi is excluded: 67 tasks, zero verified resolves ever, so its p_hat is ~0 and by the
# dead-task result above it would add nothing but wall clock.
# ============================================================================
# ARCH-REMAP ARM 2026-10-17 (e4b) -- SINGLE VARIABLE: the model. Nothing else moves.
# Built from submit_cover_rich (the INSTRUMENTED v6w notebook), so it also emits
# RUN_FINGERPRINT and run_rows.jsonl -- unlike the earlier size_e4b/size_e2b arms, which were
# forked before that instrumentation existed.
# Held at the v6w values that produced the 31B baseline: identical system.md, sampling
# (temp 0.2 / thinking 1024 / 8192 out), eval_config (28/80/8/240), 9 tools, no sub-agent.
# Same 6 stratified rich tasks, so the diff against the 31B run is paired and per-task.
# ============================================================================
# ARM TEST (2026-10-25): A3 control vs A23 procedural rewrite, 5 rich tasks x REPS.
# Canary rich_4077 + flips 3471/3777/4079 + solvable 3278. Pre-registered: PREREG_A23_2026-10-25.md
# REPS=2 -> 20 runs total (~1.7h wall = ~6.9 GPU-hours on L4x4; quota has 9h).
STRAT6 = ['rich_4077', 'rich_3471', 'rich_3777', 'rich_4079', 'rich_3278']
SAMPLE_IDS = STRAT6
REPS = 2
ARMS = ['A3', 'A23']   # A3 = prompts/system.md as written by CELL 2; A22 = system_a22.md

by_id = {t.instance_id: t for t in tasks}
SAMPLE_TASKS = []
for _tid in SAMPLE_IDS:
    if _tid in by_id:
        SAMPLE_TASKS.append(by_id[_tid])
    else:
        print(f'  WARNING: {_tid} not found in tasks.jsonl - skipped')
print(f'RICH-ONLY gate ({len(SAMPLE_TASKS)} tasks): {[t.instance_id for t in SAMPLE_TASKS]}')

# tasks_sha / n_tasks are appended HERE, not in the early fingerprint: SAMPLE_IDS lives in
# CELL 4 and SAMPLE_TASKS only after the by_id loop, so referencing either from CELL 2 raised
# 'NameError' and killed the 12b run on 2026-10-17. Both halves are guarded anyway.
try:
    FINGERPRINT['tasks_sha'] = _hl.sha256(','.join(SAMPLE_IDS).encode()).hexdigest()[:12]
    FINGERPRINT['n_tasks'] = len(SAMPLE_TASKS)
    print('RUN_FINGERPRINT ' + _js.dumps(FINGERPRINT, sort_keys=True))
    Path(WORKING_DIR, 'run_fingerprint.json').write_text(_js.dumps(FINGERPRINT, indent=1), encoding='utf-8')
except Exception as _e:
    print('[fingerprint] task fields deferred-failed: %s: %s' % (type(_e).__name__, _e))

limits, gen_constraints = build_submission_limits()
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
)
# evaluator is created PER ARM BLOCK inside the run loop below: EvalConfig reads
# prompts/system.md via submission_dir, so the prompt must be swapped first.
predictions = []; timing = []
# ===== PER-TASK ROWS, FLUSHED PER TASK (2026-10-17) =====
# WHY: until now `predictions` lived only in memory and was NEVER written to disk, and the
# failure classes we care about (never-landed-edit / wrong-file / right-file-wrong-content) had to
# be reconstructed AFTER the fact by a separate classifier -- which was wrong the first time it was
# written today and right the second. Streaming JSONL also survives a crash or an 8h timeout,
# which an in-memory list does not. Gold-path is read best-effort and simply omitted if absent.
ROWS_PATH = WORKING_DIR / 'run_rows.jsonl'
_gold_by_id = {}
try:
    for _l in (TASKS_PATH).read_text(encoding='utf-8', errors='replace').splitlines():
        if _l.strip():
            _r = _js.loads(_l)
            _gold_by_id[_r['instance_id']] = _r.get('patch', '') or ''
except Exception as _e:
    print(f'[rows] gold patch lookup unavailable ({type(_e).__name__}); gold fields omitted')

def _emit(row):
    with open(ROWS_PATH, 'a', encoding='utf-8') as fh:
        fh.write(_js.dumps(row) + '\n'); fh.flush()

# ===== ARM x REP RUN LOOP (2026-10-25) =====
# Blocks alternate (rep, arm); each block installs its prompt, rebuilds the evaluator
# (EvalConfig reads prompts/system.md at construction), then runs all tasks.
# RESUME: rows are keyed arm|rep|id in run_rows.jsonl; done keys are skipped, so a
# crashed/interrupted session continues without repeating runs.
PROMPT_SRC = {'A3': 'system_a3.md', 'A23': 'system_a23.md'}
ROWS = {}
if ROWS_PATH.exists():
    for _l in ROWS_PATH.read_text(encoding='utf-8', errors='replace').splitlines():
        if _l.strip():
            _r = _js.loads(_l)
            if 'arm' in _r and 'rep' in _r:
                ROWS['%s|%s|%s' % (_r['arm'], _r['rep'], _r['id'])] = _r
    print(f'[resume] {len(ROWS)} runs already complete')

def _flush():
    ROWS_PATH.write_text(''.join(_js.dumps(ROWS[k]) + '\n' for k in sorted(ROWS)), encoding='utf-8')

def _enrich(row, task_id):
    """Attach trace-derived compliance fields. Called RIGHT AFTER each run, while the
    per-task trace file still holds THIS run's data (traces are overwritten per task)."""
    import collections as _co
    _tp = WORKING_DIR / 'results' / 'traces' / ('trace_%s.json' % task_id)
    if not _tp.is_file():
        return
    try:
        _tr = _js.loads(_tp.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        return
    _cnt = _co.Counter(); _files = set(); _first_edit = None; _bw = 0; _seen = 0
    for _s in _tr.get('steps', []):
        _c = (_s.get('observation') or {}).get('content')
        if isinstance(_c, str) and 'budget_warning' in _c:
            _bw += _c.count('budget_warning')
        for _tc in (_s.get('tool_calls') or []):
            if not isinstance(_tc, dict):
                continue
            _fn = _tc.get('function_name', '?')
            _cnt[_fn] += 1; _seen += 1
            if _fn == 'edit_file' and _first_edit is None:
                _first_edit = _seen
        if isinstance(_c, str) and '"diff"' in _c:
            try:
                _j = _js.loads(_c)
                if isinstance(_j, dict) and _j.get('filepath'):
                    _files.add(_j['filepath'])
            except Exception:
                pass
    row.update(edit_file_calls=_cnt.get('edit_file', 0),
               submit_calls=_cnt.get('submit_patch', 0),
               get_status_calls=_cnt.get('get_status', 0),
               run_command_calls=_cnt.get('run_command', 0),
               read_file_calls=_cnt.get('read_file', 0),
               files_touched=sorted(_files),
               budget_warnings=_bw,
               first_edit_at_call=_first_edit)
    if row.get('gold_files'):
        row['gold_file_touched'] = bool(set(row['gold_files']) & set(_files))
    if row['resolved']:
        row['failure_class'] = 'RESOLVED'
    elif row['patch_chars'] == 0:
        row['failure_class'] = 'NEVER_LANDED_EDIT'
    elif row.get('gold_file_touched') is False:
        row['failure_class'] = 'WRONG_FILE'
    else:
        row['failure_class'] = 'RIGHT_FILE_WRONG_CONTENT'

import shutil as _sh
_blocks = [(rep, arm) for rep in range(REPS) for arm in ARMS]
_n_done = 0
for _bi, (_rep, _arm) in enumerate(_blocks):
    _todo = [t for t in SAMPLE_TASKS if '%s|%s|%s' % (_arm, _rep, t.instance_id) not in ROWS]
    if not _todo:
        continue
    # install this arm's prompt and rebuild the evaluator
    _sh.copyfile(AGENT_DIR / 'prompts' / PROMPT_SRC[_arm], AGENT_DIR / 'prompts' / 'system.md')
    evaluator = Evaluator(eval_config)
    print(f'\n=== block rep={_rep} arm={_arm} ({len(_todo)} tasks) '
          f'prompt_sha={__import__("hashlib").sha256((AGENT_DIR / "prompts" / "system.md").read_bytes()).hexdigest()[:12]} ===')
    for idx, task in enumerate(SAMPLE_TASKS, start=1):
        _key = '%s|%s|%s' % (_arm, _rep, task.instance_id)
        if _key in ROWS:
            continue
        print(f'[{_arm} r{_rep} {idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...')
        result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
        predictions.append({'id': task.instance_id, 'prediction': result.agent_patch or ''})
        row = {'id': task.instance_id, 'repo': task.repo.split('/')[-1],
               'arm': _arm, 'rep': _rep,
               'resolved': bool(result.resolved),
               'duration_s': round(result.duration_seconds, 1),
               'tool_calls': int(result.tool_calls),
               'patch_chars': len(result.agent_patch or '')}
        timing.append(row)
        _gold = _gold_by_id.get(task.instance_id, '')
        if _gold:
            import re as _re
            row['gold_files'] = _re.findall(r'^--- a/(\S+)', _gold, _re.M)
            row['n_gold_edits'] = len(row['gold_files'])
        _enrich(row, task.instance_id)   # trace still holds THIS run
        ROWS[_key] = row
        _flush()
        _n_done += 1
        print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
              f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")} '
              f'status={row.get("get_status_calls", "?")} submits={row.get("submit_calls", "?")} '
              f'class={row.get("failure_class", "?")}')
    # ===== INCREMENTAL SUMMARY (survives cancel/crash) =====
    # Written after EVERY block so a cancelled session still has the table.
    try:
        _sum = {'updated': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
                'runs_done': len(ROWS), 'blocks_done': _bi + 1, 'arms': {}}
        for _a in ARMS:
            _s = [v for v in ROWS.values() if v['arm'] == _a]
            if not _s: continue
            _flip = [v for v in _s if v['id'] in ('rich_3471', 'rich_3777', 'rich_4079')]
            _can = [v for v in _s if v['id'] == 'rich_4077']
            _sum['arms'][_a] = {
                'overall': '%d/%d' % (sum(v['resolved'] for v in _s), len(_s)),
                'flips': '%d/%d' % (sum(v['resolved'] for v in _flip), len(_flip)),
                'canary': '%d/%d' % (sum(v['resolved'] for v in _can), len(_can)),
                'mean_dur_s': round(sum(v['duration_s'] for v in _s) / len(_s), 1),
                'zero_patch': sum(1 for v in _s if v['patch_chars'] == 0),
                'mean_status': round(sum(v.get('get_status_calls') or 0 for v in _s) / len(_s), 2),
                'per_task': {t: '%d/%d' % (sum(v['resolved'] for v in _s if v['id'] == t),
                                           sum(1 for v in _s if v['id'] == t))
                             for t in sorted(set(v['id'] for v in _s))},
            }
        _sum['failure_classes'] = dict(__import__('collections').Counter(
            v.get('failure_class', '?') for v in ROWS.values()))
        (WORKING_DIR / 'arm_summary.json').write_text(
            _js.dumps(_sum, indent=1), encoding='utf-8')
        print(f'[summary] arm_summary.json updated ({len(ROWS)} runs)')
    except Exception as _se:
        print(f'[summary] incremental write failed: {type(_se).__name__}: {_se}')

print('\nRUN_ROWS written: %s  (%d runs this session)' % (ROWS_PATH, _n_done))
import collections as _co2
print('FAILURE_CLASSES', dict(_co2.Counter(v.get('failure_class', '?') for v in ROWS.values())))

# ===== SUMMARY: per-arm x per-task =====
tdf = pd.DataFrame(list(ROWS.values()))
print('\n===== ARM SUMMARY =====')
if len(tdf):
    piv = tdf.pivot_table(index='id', columns='arm', values='resolved', aggfunc=['sum', 'count'])
    print(piv.to_string())
    print()
    for _a in ARMS:
        _s = tdf[tdf.arm == _a]
        if not len(_s):
            continue
        _flip = _s[_s.id.isin(['rich_3471', 'rich_3777', 'rich_4079'])]
        _canary = _s[_s.id == 'rich_4077']
        print(f'{_a}: overall {_s.resolved.sum()}/{len(_s)} | '
              f'flips(3471/3777/4079) {_flip.resolved.sum()}/{len(_flip)} | '
              f'canary(4077) {_canary.resolved.sum()}/{len(_canary)} | '
              f'mean dur {_s.duration_s.mean():.0f}s | '
              f'zero-patch {int(((_s.patch_chars == 0)).sum())} | '
              f'mean status calls {_s.get_status_calls.mean() if "get_status_calls" in _s else float("nan"):.1f} | '
              f'mean submits {_s.submit_calls.mean() if "submit_calls" in _s else float("nan"):.1f}')
    print('\nCANARY GUARD: rich_4077 should resolve in most A3 runs; if it does not,')
    print('suspect the harness/config before believing any arm difference.')
