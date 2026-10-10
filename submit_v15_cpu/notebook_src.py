# Gemma 4 Developer Agent — v15 CPU-ONLY PACKAGING NOTEBOOK.
# Purpose: produce submission.zip (the v15 agent dir) with NO GPU, so it can be committed + submitted via
# the Notebook tab (Kaggle re-runs THIS notebook on the hidden set and extracts the submission.zip it emits).
# The scored WORK happens on Kaggle's compute during the hidden re-run using the agent config inside the zip;
# building the zip itself needs only file writes + shutil.make_archive = CPU, seconds, zero GPU quota.
#
# This is the v15 SHORT-TRAJECTORY agent (anti-word-trap localization + NO sub-agent + thinking 256 +
# budget 12), identical config to submit_v15/, but WITHOUT the vLLM-start and eval cells (those are
# GPU-only and only MEASURE resolves locally; they produce nothing that goes into the scored zip).

# ===== CELL 1: write the v15 agent directory (CPU only - pure file writes) =====
import shutil
from pathlib import Path
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

# v15 agent.yaml = SINGLE LlmAgent, NO sub-agent (sub-agent pushed runs long -> compaction). NO adapter.
(AGENT_DIR / 'agent.yaml').write_text('''name: sibling_conform_agent
model: gemma-4-31b-it-qat-w4a16-ct
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')

# v15 sampling: LOW thinking_budget 256 (in-window planning; long reasoning gets compacted = wasted).
# include_thoughts TRUE (false would DISABLE generation entirely in adk_submission 0.2.12). temp 0.2.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 4096
thinking_config:
  thinking_budget: 256
  include_thoughts: true
''', encoding='utf-8')

# v15 eval_config: TIGHT. 12 tool calls / 20 turns (turns>calls) / 5-min failsafe. Keeps the whole run near
# the ~5-event compaction retention window AND dodges the B1 edit-guillotine off-by-one (never edit at the
# budget boundary when the task finishes in ~6 of 12 calls).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 12
  max_turns: 20
  timeout_seconds: 120
''', encoding='utf-8')

# v15 system.md = anti-word-trap localization (validated on 31b) + HARD finish-short framing.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~12 tool calls and 5 minutes. BE DECISIVE AND FAST. Your reasoning is NOT retained across many turns, so a SHORT run is a COHERENT run: FINISH THE WHOLE TASK IN UNDER ~6-8 TOOL CALLS. Long runs lose their own context and fail.

## The one rule that matters: LOCATE in <=3 calls, EDIT by call ~4, VERIFY once, SUBMIT.
Do NOT keep exploring. The moment you know the FILE and FUNCTION, edit. Re-reading a file already in your context is a BANNED, wasted call. A plausible edit submitted beats endless searching that loses coherence.

## LOCALIZE BY BEHAVIOR, NOT BY THE SYMPTOM WORD (the #1 cause of wrong fixes)
The problem is usually a 2-5 word SYMPTOM. The fix file is OFTEN NOT the file whose NAME matches that word; it is the code that PRODUCES the behavior.
- Do NOT assume "table"->table.py, "panel"->panel.py, "space"/"newline"->the obvious renderable. The word names the SYMPTOM; the fix is in whatever RENDERS or DECODES that output.
- Patterns: a spacing/alignment/"superfluous" symptom in rendered output is usually in the code that EMITS segments/lines (the markdown/console render path or cell-width math), not the high-level container. A "newline"/ANSI/escape symptom is usually in the DECODER that parses the text. A "proxy"/wrapper symptom is in the wrapper class that forwards calls.
- PROCEDURE: (1) name the exact OBSERVABLE behavior. (2) grep for the MECHANISM that emits it (the function building the line/segment/string, the decoder, the forwarding method), not the symptom noun. (3) confirm the behavior flows through the file before editing. (4) if the obvious file lacks the emitting code, follow the import/call to the module that does — the fix is frequently in a SMALLER, more specific module than the word suggests. If a test is named, trace the exact symbol/class it constructs to its DEFINING module and fix THERE.
- Cap localization at ~3 calls, then EDIT.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or a similar function in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Workflow (tight — target: whole task done in under ~6-8 calls)
1. Read the problem. Name the observable behavior. Localize by BEHAVIOR (above). MAX ~3 locate calls.
2. edit_file the minimal fix. Match existing conventions/strings/types exactly. Keep old_string SMALL and unique (one line or a tight anchor) so it matches on the first try.
3. Verify with ONE targeted test (the test the problem names, or an obvious one). NEVER run bare pytest. Put any scratch in /tmp via run_command heredoc, NOT the repo.
4. submit_patch ONCE. The moment it returns "ok", STOP - one-line summary, no more tool calls.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them AND they poison your diff.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing source files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')
print('v15 agent dir written (CPU-only):', AGENT_DIR)
for p in sorted(AGENT_DIR.rglob('*')):
    print('  ', p.relative_to(AGENT_DIR))

# ===== CELL 2: package submission.zip (CPU only) =====
import zipfile
zip_path = Path(shutil.make_archive(str(WORKING_DIR / 'submission'), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    names = zf.namelist()
    total = sum(i.file_size for i in zf.infolist())
# sanity: required agent files present, size sane
need = {'agent.yaml', 'prompts/system.md', 'configs/sampling.yaml', 'eval_config.yaml'}
have = {n for n in names if not n.endswith('/')}
missing = need - have
assert not missing, f'MISSING required files: {missing}'
assert total < 3 * 1024**3, f'too big: {total}'
print(f'Created {zip_path} ({zip_path.stat().st_size/1024:.1f} KiB)')
print('contents:', names)
print('MISSING:', missing if missing else 'none - OK')
