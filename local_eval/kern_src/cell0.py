# Gemma 4 Developer Agent - v6w = v6t with thinking_budget QUARTERED 4096 -> 1024. ONE variable.
#
# THIRD POINT ON THE THINKING LADDER (user call 2026-10-11; runs alongside v6v/2048 on the second GPU slot):
#   256  : OUR v6 @ 0.12 - only board score we have. Everything finished inside the wall.
#   1024 : THIS ARM - untested.
#   2048 : v6v, queued in parallel.
#   4096 : what v6b/v6c/v6t ship. NEVER SCORED (36h lag + 1/day). Put rich_3471 on the wall twice.
#   OFF  : v6u - FASTER (rich_3471 481.9s -> 406.2s, off the wall) BUT LOST rich_4079 by committing
#          early and wrong at 150.7s. Same shape as the v11 LoRA failure.
#
# The open question is whether the "commit early, get it wrong" behaviour of thinking-OFF is a
# BUDGET problem (too little deliberation) or an on/off problem (thinking itself). v6u says thinking-OFF
# costs quality. v6v/2048 and v6w/1024 bracket the middle. If 1024 also degrades toward the OFF result,
# the ladder is steep and 2048-4096 is the working range. If 1024 holds 4/6 with no wall task, we may not
# need 4096 at all - which matters because 4096 is the one setting we have never scored on the board.
#
# MEASUREMENT CAVEAT (honest, pre-registered): running two arms in parallel is fine - they are separate
# Kaggle kernels on separate GPUs, so they do not contend for hardware. But it does NOT double the evidence:
# the free gate can only separate configs differing by a 3+ point swing (v6c vs v6t tied 4/6 on a
# wall-boundary coin flip). Three arms on a 6-task set means most outcomes will be indistinguishable from
# noise. Treat any single-arm move of 1 task as NOT evidence.
#
# v6w = v6t EXACTLY, except thinking_budget 4096 -> 1024. Held identical: 9-tool list with edit_file
# primary, budget 28/8/80/240, temperature 0.2, top_p 0.95, max_output_tokens 8192, include_thoughts TRUE,
# the Budget Oracle + Commit-by-Remaining + Bank-as-you-Go sections, and the SAME 6 tasks.
#
# PRE-REGISTERED BAR (vs v6t's 4/6):
#   - >= 5/6                       -> adopt 1024.
#   - == 4/6 AND no task on a wall -> equal quality, materially cheaper in time; prefer it.
#   - == 4/6 with a boundary loss   -> indistinguishable from v6t; keep the higher budget.
#   - <= 3/6                       -> 1024 is below the useful deliberation floor.
# SECONDARY, transfers even on a null: mean seconds/task vs v6t's ~266s and v6u's (faster but wrong).
#
# NEW kernel (comfyops/gemma-sibling-conform-v6w). v6/0.12 SACRED; v6b/c/s/t/u/v all untouched.

# ===== CELL 1: environment + wheelhouse =====
import glob, importlib, os, shutil, subprocess, sys
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TRANSFORMERS_NO_TF'] = '1'
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'
os.environ['VLLM_ENGINE_READY_TIMEOUT_S'] = '1200'
os.environ['VLLM_NO_USAGE_STATS'] = '1'
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

# REVERTED 2026-10-17 to the PROVEN v6 cell, verbatim. History, so it is not repeated:
#  * The cover-rich v1 failure ("Installing 0 wheels") was NOT a code bug. This exact block
#    produced "Installing 41 wheels..." on the v6 and v6w runs and the 0.15 board score.
#  * I "fixed" it with a resolver that misread its own log line and preferred
#    /kaggle/input/gemma-4-developer-agent/wheels. That dir is the competition WEB APP's
#    dependency set -- 45 starlette versions, 3 pytest versions, cp313 wheels on a py3.12 kernel,
#    no swegemma/vllm/torch/adk -- so it tried to install 124 wrong wheels and died.
#  * The ABI filter I then added was itself buggy: cp3(\d+) captures "312" from cp312, so
#    int("312") == 12 is False; it rejected VALID cp312 wheels and kept cp313 ones.
#  Three self-inflicted bugs in code that never needed changing. The only addition kept is a
#  diagnostic that fires ONLY when the wheel list is empty, so a real mount failure is legible.
# CORRECTED 2026-10-17 by direct evidence, not inference. The DIAG block printed
#   /kaggle/input contains: ['gemma-4-developer-agent', 'gemma-4-developer-agent-wheelhouse', 'models']
# so Kaggle mounts datasets FLAT at /kaggle/input/<dataset-name>. The long-standing path
# '/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse' has a '/datasets/metric/'
# prefix that does NOT exist in the current mount layout, so WHEELHOUSE_DIR.is_dir() was False.
# That path DID work on 2026-10-14 (v6/v6w logs show 'Installing 41 wheels...'), so the platform
# mount layout changed between 10-14 and 10-17. Kept as a fallback in case it comes back.
WHEELHOUSE_DIR = Path('/kaggle/input/gemma-4-developer-agent-wheelhouse')
if not WHEELHOUSE_DIR.is_dir():
    _alt = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
    if _alt.is_dir():
        WHEELHOUSE_DIR = _alt
for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth',
                    '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
    for pth in glob.glob(pth_pattern):
        try: os.unlink(pth)
        except OSError: pass
tmp_whl = Path('/tmp/wheelhouse')
# Never reuse stale symlinks: the pip list below is built by globbing /tmp/wheelhouse, NOT
# WHEELHOUSE_DIR, so anything left there from an earlier in-session run gets installed. That is
# how 124 leftover app-dependency wheels were pip-installed on 2026-10-17.
if tmp_whl.exists(): shutil.rmtree(tmp_whl)
tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob('*.whl'):
    if 'cutlass' in w.name.lower(): continue
    target_name = (w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name)
    target = tmp_whl / target_name
    if not target.exists(): os.symlink(w, target)
wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
_names = [w.rsplit('/', 1)[-1] for w in wheels]
print(f'WHEELHOUSE: {WHEELHOUSE_DIR} exists={WHEELHOUSE_DIR.is_dir()} '
      f'globbed={len(list(WHEELHOUSE_DIR.glob("*.whl"))) if WHEELHOUSE_DIR.is_dir() else 0} '
      f'installing={len(wheels)} swegemma={any("swegemma" in n for n in _names)}')
# The harness wheelhouse is ~41 wheels and MUST contain swegemma. A set without it is the
# competition WEB APP dependency set (124 wheels, 45 starlette versions, cp313 tags, no
# swegemma/vllm/torch/adk) and must never be pip-installed here.
if wheels and not any('swegemma' in n for n in _names):
    raise RuntimeError(
        f'WRONG WHEELHOUSE: {len(wheels)} wheels at {WHEELHOUSE_DIR} but no swegemma wheel. '
        f'First names: {_names[:8]}. This is the competition app dependency set, not the harness '
        'wheelhouse.')
if not wheels:  # diagnostic only -- the proven path and glob above are unchanged
    _root = Path('/kaggle/input')
    print('WHEELHOUSE EMPTY. exists(WHEELHOUSE_DIR) =', WHEELHOUSE_DIR.is_dir())
    print('/kaggle/input contains:',
          sorted(p.name for p in _root.iterdir()) if _root.is_dir() else '<none>')
    raise RuntimeError('wheelhouse dataset not mounted -- see listing printed above')
print(f'Installing {len(wheels)} wheels...')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
importlib.invalidate_caches()
print('Wheelhouse installation complete.')
