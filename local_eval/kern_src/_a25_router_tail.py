
# ===== A25 ROUTER ARM: SECOND AGENT DIR WITH TWO agent_tool SPECIALISTS (2026-10-27) =====
# Closest prior test: v8 "contract self-audit sub-agent" = REGRESSION (1/6 vs v6 board); mechanism:
#   (a) sub-agent sessions NEVER COMPACT -> with skip_summarization:true the raw return floods the
#       main context -> overflow -> the patch EMPTIES (3 of 5 losses in one arm were overflows),
#   (b) the sub-agent shares the main call budget (v4 trace: it burned all 22 shared calls and
#       returned garbage on rich_4079), (c) system.md never said when to dispatch it.
# Changed axis vs v8: (1) skip_summarization FALSE (summarized, bounded return); (2) TWO specialists
#   behind an explicit classify-then-dispatch directive in workflow step 1 (the user-requested
#   "subagent for categorizing the requests"); (3) specialists never edit - the main agent keeps
#   the single edit + submit; (4) hard specialist call caps (<=6 locator / <=4 logic), one dispatch
#   per task. Budget/config/model/prompt-text-except-the-one-span held at A3.
# Prereg + decision rules: PREREG_A25_2026-10-27.md
AGENT_DIR_R = WORKING_DIR / 'submission_router'
if AGENT_DIR_R.exists(): shutil.rmtree(AGENT_DIR_R)
(AGENT_DIR_R / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR_R / 'configs').mkdir(parents=True, exist_ok=True)
(AGENT_DIR_R / 'sub_agents').mkdir(parents=True, exist_ok=True)
shutil.copyfile(AGENT_DIR / 'configs' / 'sampling.yaml', AGENT_DIR_R / 'configs' / 'sampling.yaml')
shutil.copyfile(AGENT_DIR / 'eval_config.yaml', AGENT_DIR_R / 'eval_config.yaml')

(AGENT_DIR_R / 'agent.yaml').write_text('''name: sibling_conform_agent
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
  - agent_tool:
      config_path: sub_agents/locator.yaml
      skip_summarization: false
  - agent_tool:
      config_path: sub_agents/logic.yaml
      skip_summarization: false
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')

(AGENT_DIR_R / 'sub_agents' / 'locator.yaml').write_text('''name: code_locator
model: gemma-4-31b-it-qat-w4a16-ct
instruction: |
  You are a code-locator specialist inside a SWE bug-fixing harness. Input: a bug report/problem statement.
  Use at MOST 6 tool calls (run_command grep / read_file / search_similar_code). Find:
  1. the exact file and line of the deviation,
  2. the correct pattern as implemented in a sibling function/file or the repo's own conventions - quote it exactly,
  3. the smallest old->new edit concept in <=3 lines.
  Do NOT edit files. Return <=8 lines; no full file dumps; no code block longer than 4 lines.
tools:
  - run_command
  - read_file
  - search_similar_code
generate_content_config:
  temperature: 0.2
  top_p: 0.95
  max_output_tokens: 1024
  thinking_config:
    thinking_budget: 1024
    include_thoughts: false
''', encoding='utf-8')

(AGENT_DIR_R / 'sub_agents' / 'logic.yaml').write_text('''name: logic_analyst
model: gemma-4-31b-it-qat-w4a16-ct
instruction: |
  You are a fix-design specialist inside a SWE bug-fixing harness. Input: a bug report plus (optionally) the main agent's code span.
  Use at MOST 4 tool calls (read_file / run_command sed / search_similar_code) to confirm the span, then design the MINIMAL fix:
  exact old->new text, matching the surrounding style and EVERY input variant the report implies.
  Do NOT edit files. Return <=8 lines.
tools:
  - read_file
  - run_command
  - search_similar_code
generate_content_config:
  temperature: 0.2
  top_p: 0.95
  max_output_tokens: 1024
  thinking_config:
    thinking_budget: 1024
    include_thoughts: false
''', encoding='utf-8')

# ROUTER PROMPT = A3 with ONE substituted span (workflow step 1), reversible by construction.
_step1_old = """1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Find the code with 1 `run_command` grep, or `read_file` for a whole file. Then call `get_status` (free) to see where you stand."""
_step1_new = """1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Classify the task in one word before acting: LOCATE (a wrong value, constant, pattern, or deviation hidden somewhere in the code), LOGIC (control flow, guard, algorithm, or argument wiring wrong once the site is found), or TEST-DRIVEN (the contract is an exact string/exception/variant set). LOCATE-class: you may call `code_locator` ONCE (ONE dispatch per task, never twice): it returns file, line, the deviation, and the correct sibling/reference pattern in <=8 lines. LOGIC-class: you may call `logic_analyst` ONCE with the problem text and the code span: it returns the minimal fix design in <=8 lines. TEST-DRIVEN or unclear: use no specialist. Specialists never edit files - YOU make the single edit. If the site is not already clear from the specialist (or you used none), find it with 1 `run_command` grep or `read_file`, then call `get_status` (free) to see where you stand."""
_a3txt = (AGENT_DIR / 'prompts' / 'system_a3.md').read_text(encoding='utf-8')
assert _a3txt.count(_step1_old) == 1, 'step-1 anchor matched %d times (want exactly 1)' % _a3txt.count(_step1_old)
_rt = _a3txt.replace(_step1_old, _step1_new, 1)
assert _rt.replace(_step1_new, _step1_old, 1) == _a3txt, 'router prompt is not a reversible single-span substitution of A3'
(AGENT_DIR_R / 'prompts' / 'system_router.md').write_text(_rt, encoding='utf-8')
(AGENT_DIR_R / 'prompts' / 'system.md').write_text(_rt, encoding='utf-8')
print('[router] system_router.md: %d chars sha %s (A3 + one step-1 span)' % (
    len(_rt), _hl.sha256((AGENT_DIR_R / 'prompts' / 'system_router.md').read_bytes()).hexdigest()[:12]))

# ROUTER FINGERPRINT (inverse of the ctrl assert: this arm MUST have the agent_tool entries)
_ragtxt = (AGENT_DIR_R / 'agent.yaml').read_text(encoding='utf-8')
_rtools = [l.strip()[2:].strip() for l in _ragtxt.splitlines() if l.strip().startswith('- ')]
FINGERPRINT_R = {
    'model': _ragtxt.split('model:')[1].split()[0] if 'model:' in _ragtxt else '?',
    'prompt_sha': _sha(AGENT_DIR_R / 'prompts' / 'system.md'),
    'prompt_chars': len((AGENT_DIR_R / 'prompts' / 'system.md').read_text(encoding='utf-8')),
    'sampling_sha': _sha(AGENT_DIR_R / 'configs' / 'sampling.yaml'),
    'eval_sha': _sha(AGENT_DIR_R / 'eval_config.yaml'),
    'locator_sha': _sha(AGENT_DIR_R / 'sub_agents' / 'locator.yaml'),
    'logic_sha': _sha(AGENT_DIR_R / 'sub_agents' / 'logic.yaml'),
    'n_tools': len(_rtools), 'tools': _rtools,
    'has_subagent': any('agent_tool' in t for t in _rtools),
}
print('RUN_FINGERPRINT(router) ' + _js.dumps(FINGERPRINT_R, sort_keys=True))
assert FINGERPRINT_R['has_subagent'], 'router arm is missing its agent_tool entries'
assert FINGERPRINT['sampling_sha'] == FINGERPRINT_R['sampling_sha'], 'sampling drifted between arms'
assert FINGERPRINT['eval_sha'] == FINGERPRINT_R['eval_sha'], 'eval_config drifted between arms'
