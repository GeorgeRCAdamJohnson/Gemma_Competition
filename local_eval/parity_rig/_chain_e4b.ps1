# Chain: wait for the 12B run to finish, swap the model server to E4B, then run the
# 37-task locate-prize experiment on E4B. Safe ordering: the 12B server is only stopped
# AFTER the docker run exits, so it cannot break an in-flight evaluation.

$ErrorActionPreference = 'Continue'
$RIG   = 'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\parity_rig'
$LOG   = Join-Path $RIG 'm1_locate\chain.log'
$EXE   = 'C:\Users\Biges\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe'
$MODEL = 'C:\Users\Biges\models\gemma4-e4b-qat\gemma-4-E4B_q4_0-it.gguf'

function Log($m) { $t = Get-Date -Format 'HH:mm:ss'; "$t $m" | Tee-Object -FilePath $LOG -Append }

Log 'chain start: waiting for the 12B docker run to exit'

# 1. wait for the rig container to disappear (it runs with --rm)
$waited = 0
while ($waited -lt 150) {
    $up = docker ps --format '{{.Image}}' 2>$null | Select-String 'gemma-parity-rig'
    if (-not $up) { break }
    Start-Sleep 20; $waited += 20
    if ($waited % 120 -eq 0) { Log "still running ($waited s)" }
}
Log "12B container finished after $waited s"

$f = Join-Path $RIG 'm1_locate\agent_ctrl_12b_locate_r0\task_results.jsonl'
if (Test-Path $f) { Log ("12B rows: " + (Get-Content $f | Measure-Object -Line).Lines + ' / 46') }

# 2. free VRAM: stop whatever listens on 8082 (vLLM inside WSL)
Log 'stopping the 8082 model server'
$killed = wsl -e bash -lc "pid=`$(ss -lptnH 'sport = :8082' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1); if [ -n \"`$pid\" ]; then kill -9 `$pid && echo killed:`$pid; else echo none; fi" 2>&1
Log ("8082: " + ($killed -join ' '))
Start-Sleep 10

# 3. start E4B llama-server on 8081
Log 'starting llama-server E4B on 8081'
$null = Start-Process -FilePath $EXE `
    -ArgumentList @('-m', $MODEL, '--jinja', '-ngl', '99', '-c', '90112', '-np', '3', '--port', '8081') `
    -RedirectStandardOutput (Join-Path $RIG 'runs\llama_e4b_out.log') `
    -RedirectStandardError  (Join-Path $RIG 'runs\llama_e4b_err.log') `
    -WindowStyle Hidden -PassThru

$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep 10
    try {
        $h = Invoke-WebRequest 'http://127.0.0.1:8081/health' -UseBasicParsing -TimeoutSec 5
        if ($h.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { Log 'E4B SERVER FAILED TO COME UP - aborting chain'; exit 1 }
Log 'E4B health OK'
try { $m = Invoke-RestMethod 'http://127.0.0.1:8081/v1/models' -TimeoutSec 8; Log ('served: ' + (($m.data | ForEach-Object { $_.id }) -join ',')) } catch { Log 'model list unavailable' }

# 4. run the 37-task locate experiment on E4B
Log 'running 37-task E4B locate experiment'
$env:PYTHONIOENCODING = 'utf-8'
$env:ARM     = 'agent_ctrl_e4b_locate'
$env:COHORT  = 'cohort_e4b.json'
$env:M1_URL  = 'http://host.docker.internal:8081/v1'
$env:CONC    = '3'
$env:REP     = '0'
Set-Location $RIG
python -u _m1_locate.py *>&1 | Tee-Object -FilePath (Join-Path $RIG 'm1_locate\e4b_run.log')
Log 'chain complete'
