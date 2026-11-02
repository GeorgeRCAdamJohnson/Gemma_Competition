# DOCKER TRAIL — parity rig command reference (2026-10-27)

Everything used to run the REAL harness (adk_submission + swegemma + adk_eval_core) locally
against the E4B llama-server. Copy-pasteable; scripts live beside this file.

## 0. One-time prerequisites

```powershell
# Model server (detached background; llama-server, E4B QAT, port 8081, -np 3 -c 90112)
$exe   = 'C:\Users\Biges\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe'
$model = 'C:\Users\Biges\models\gemma4-e4b-qat\gemma-4-E4B_q4_0-it.gguf'
& $exe -m $model --jinja -ngl 99 -c 90112 -np 3 --port 8081 *> runs\llama_server_e4b_qat.log

# Health check (must return 200 before any run)
(Invoke-WebRequest 'http://127.0.0.1:8081/health' -UseBasicParsing).StatusCode
```

## 1. Build the image

```powershell
cd C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\parity_rig
docker build -t gemma-parity-rig .
# If buildkit throws "parent snapshot ... does not exist":
docker builder prune -f   # then rebuild
```

- Dockerfile: python:3.13-slim + `google-adk[extensions]==1.36.1` (LiteLLM extra is REQUIRED;
  plain google-adk raises ImportError at swegemma.cli import) + google-genai, pyyaml,
  python-dotenv, docker (python SDK — adk_eval_core.sandbox imports it), pytest,
  pytest-timeout==2.1.0, typer, pygments, packaging, git/patch/pigz/protobuf-compiler
  (mirrors comp_files/Dockerfile.public).
- Harness packages come from `-v .../harness_src/x:/x` with `PYTHONPATH=/x`
  (adk_submission 0.2.13, adk_eval_core 0.1.0, swegemma 0.2.11).

## 2. Materialize agent dirs (once)

```powershell
python make_agent_dirs.py   # -> parity_rig/agent_ctrl (shipped v10) + agent_router (A25)
```

## 3. Compile-only check (no model, ~5s) — pre-flight for ANY submission

```powershell
docker run --rm `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/local_eval/parity_rig:/rig' `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/harness_src/x:/x' `
  -w /rig gemma-parity-rig:latest `
  python compile_check.py /rig/agent_ctrl /rig/agent_router
# Also run it on a downloaded artifact: -v '<pull_dir>/submission:/sub' ... python compile_check.py /sub
```

## 4. Snapshot builder (per task, LF-exact!)

```powershell
python _m1_snapshots.py      # builds snapshots/<task>.tgz for the cohort (skip if exists)
```

- CRITICAL: clone with `-c core.autocrlf=false -c core.eol=lf` + `checkout --detach <base_commit>`,
  verify `git status --porcelain` EMPTY, tar the CONTENTS (files at tar root, .git included).
  A Windows-CRLF checkout makes the Linux harness' `git diff` explode (8.5MB "agent patch").

## 5. Single end-to-end task (the M1 pattern)

```powershell
docker run --rm --add-host=host.docker.internal:host-gateway `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/local_eval/parity_rig:/rig' `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/harness_src/x:/x' `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/comp_files:/data' `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/local_eval/snapshots:/snaps' `
  -v 'C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/local_eval/parity_rig/m1_results:/out' `
  -e PYTHONPATH=/x `
  -e OPENAI_BASE_URL=http://host.docker.internal:8081/v1 `
  -e OPENAI_API_KEY=EMPTY `
  -w /rig gemma-parity-rig:latest `
  python -m swegemma eval `
    --tasks /data/tasks.jsonl --snapshots-dir /snaps --results-dir /out `
    --submission-dir /rig/agent_ctrl --sandbox subprocess `
    --task-id rich_4077 `
    --max-tool-calls 28 --max-turns 120 --timeout-seconds 300 --max-time-minutes 8 `
    --display quiet --verbose
```

- Endpoint comes from env (`MODEL_PROXY_URL`/`LITELLM_API_BASE`/`LOCAL_INFERENCE_URL`/
  `OPENAI_BASE_URL`, default localhost:8000/v1) — swegemma builds LiteLlm clients per model
  discovered from the submission dir (`discover_declared_models`).
- Swap `--submission-dir /rig/agent_router` for the A25 arm; add more `--task-id` flags per task.
- Results: `<out>/summary.json`, `task_results.jsonl`, `patches/`, `traces/`, `test_outputs/`, `logs/`.

## 6. Batch runner (cohort x reps x both arms)

```powershell
python -u _m1_batch.py    # resume-safe; skips (arm,rep) dirs that already have summary.json
```

- Cohort + reps + arms are constants at the top of `_m1_batch.py` (currently 7 known-E4B tasks
  x 3 reps x {ctrl, router} = 42 runs, ~50 min).
- Aggregate table (resolved per arm per task vs E4B history) prints at the end.

## 7. Useful one-liners

```powershell
# Results of a run
Get-Content parity_rig\m1_batch\ctrl\r0\summary.json
Get-Content parity_rig\m1_batch\ctrl\r0\task_results.jsonl | % { ($_ | ConvertFrom-Json) }

# Did the router dispatch sub-agents? USE THE TRACE, not the log:
# (the agent log's tool lines don't match reliably across runs; the trace's function_name is authoritative.
#  Do NOT count plain 'code_locator' matches in traces either - the prompt text is repeated per turn.)
$t = Get-Content parity_rig\m1_batch\router\r0\traces\trace_rich_3905.json -Raw
[regex]::Matches($t, '"function_name":\s*"(code_locator|logic_analyst)"').Count   # real dispatches only

# Quick dispatch scan across a whole arm/rep:
Get-ChildItem parity_rig\m1_batch\router -Recurse -Filter 'trace_*.json' | % {
  $n = ([regex]::Matches((Get-Content $_.FullName -Raw), '"function_name":\s*"(code_locator|logic_analyst)"')).Count
  '{0}: {1}' -f $_.Name, $n }

# Tool-call mix + dispatch counts in a trace
$t = Get-Content parity_rig\m1_batch\router\r0\traces\trace_rich_3006.json -Raw
[regex]::Matches($t, '"function_name":\s*"([^"]+)"') | % { $_.Groups[1].Value } | Group-Object
```

## Gotchas learned the hard way (kept so nobody re-learns them)

1. **BASE path double-up**: a driver `BASE` that already ends in `\Gemma` + f-strings that add
   `/Gemma/` again -> Docker silently CREATES the nonexistent dirs and mounts emptiness
   (`No module named swegemma`). Verify printed mount paths; clean up any `Gemma\Gemma\` junk.
2. **CRLF snapshots** -> fake multi-MB agent patches (see §4).
3. `google-adk` needs the `[extensions]` extra for LiteLLM.
4. `adk_eval_core` imports the `docker` python package even in subprocess-sandbox mode.
5. Builder-cache corruption after an interrupted build -> `docker builder prune -f`.
6. Kaggle CLI `kernels push` also RUNS the kernel; slug derives from the TITLE, not the id.
7. Router runs are ~2x wall of ctrl (dispatch overhead); budget-starvation signature =
   zero-patch at 27-28 calls.
8. Known open bug (found by this rig): sub-agent returns `{"raw": ""}` when
   `skip_summarization: false` — summarizer lives one layer above AgentTool
   (`tool_context.actions.skip_summarization` flag); next place to look:
   adk_eval_core response processing / ADK runner.


## 8. Trail a LIVE batch (paste in any PowerShell; Ctrl+C to stop)

```powershell
$b = 'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\parity_rig\m1_batch_v2'
while ($true) {
  Clear-Host
  '=== m1_batch_v2 progress ==='
  foreach ($r in 0..2) {
    $p = Join-Path $b "router_v2\r$r\task_results.jsonl"
    if (Test-Path $p) {
      $rows = Get-Content $p | ForEach-Object { $_ | ConvertFrom-Json }
      $k = ($rows | Where-Object resolved).Count
      $cap = ($rows | Where-Object { $_.tool_calls -ge 28 }).Count
      "r$r : $($rows.Count)/7 tasks | resolved=$k | cap28=$cap"
    } else { "r$r : (not started)" }
  }
  ''
  '=== containers ==='
  docker ps --format '{{.ID}}  {{.Status}}  {{.Image}}'
  Start-Sleep 10
}
```

Truth lives on DISK (task_results.jsonl), not in the driver's stdout - the driver prints
only after each 7-task block. Cross-check dispatch in finished reps:

```powershell
Get-ChildItem $b -Recurse -Filter 'trace_*.json' | ForEach-Object {
  $n = ([regex]::Matches((Get-Content $_.FullName -Raw), '"function_name":\s*"(code_locator|logic_analyst)"')).Count
  '{0}: {1} dispatches' -f ($_.Directory.Parent.Name + '/' + $_.Name), $n }
```
