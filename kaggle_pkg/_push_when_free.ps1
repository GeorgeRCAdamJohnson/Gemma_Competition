# Push a kernel as soon as a blocking kernel is no longer RUNNING/QUEUED (frees a GPU session).
# usage: powershell -File kaggle_pkg\_push_when_free.ps1 <blocking-slug> <push-dir>
param([string]$Block, [string]$PushDir)
$ErrorActionPreference = 'Continue'
while ($true) {
  $st = (kaggle kernels status "comfyops/$Block" 2>&1 | Where-Object { $_ -match 'status' }) -join ' '
  Write-Output ("{0}  {1}: {2}" -f (Get-Date -Format 'HH:mm:ss'), $Block, $st)
  if ($st -and $st -notmatch 'RUNNING|QUEUED') {
    Start-Sleep 30
    $o = kaggle kernels push -p $PushDir 2>&1 | Where-Object { $_ -match 'push|rror' }
    $o | ForEach-Object { Write-Output "   $_" }
    if ($o -match 'successfully pushed') { Write-Output 'PUSHED'; break }
  }
  Start-Sleep 120
}
