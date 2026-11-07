# Poll Kaggle kernels; when one leaves RUNNING/QUEUED, pull its result JSON + log once.
# Usage: powershell -File kaggle_pkg\_poll_pull.ps1
$ErrorActionPreference = 'Continue'
$jobs = @{
  'e4b-cap-ab'   = @{ dir = 'Outputs\e4b_cap_ab';   pat = 'variance_ab.json'; done = $false }
  'e4b-repro-ab' = @{ dir = 'Outputs\e4b_repro_ab'; pat = 'variance_ab.json'; done = $false }
}
while ($true) {
  foreach ($k in @($jobs.Keys)) {
    $j = $jobs[$k]
    if ($j.done) { continue }
    $st = (kaggle kernels status "comfyops/$k" 2>&1 | Where-Object { $_ -match 'status' }) -join ' '
    Write-Output ("{0}  {1}  {2}" -f (Get-Date -Format 'HH:mm:ss'), $k, $st)
    if ($st -match 'RUNNING|QUEUED' -or -not $st) { continue }
    New-Item -ItemType Directory -Force $j.dir | Out-Null
    for ($i = 1; $i -le 5; $i++) {
      $o = kaggle kernels output "comfyops/$k" -p $j.dir --file-pattern $j.pat 2>&1 | Where-Object { $_ -match 'downloaded|429' }
      $o | ForEach-Object { Write-Output "   $_" }
      if ($o -match 'downloaded' -and -not ($o -match '429')) { break }
      Start-Sleep 90
    }
    $j.done = $true
    Write-Output ("{0}  {1}  PULLED -> {2}" -f (Get-Date -Format 'HH:mm:ss'), $k, $j.dir)
  }
  if (-not ($jobs.Values | Where-Object { -not $_.done })) { Write-Output 'ALL DONE'; break }
  Start-Sleep 180
}
