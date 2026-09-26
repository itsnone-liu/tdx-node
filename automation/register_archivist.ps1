# register_archivist.ps1 — (re)create the tdx-archivist scheduled task. ASCII only.
# Idempotent: safe to re-run on this machine or after cloning the repo elsewhere
# (adjust $repoRoot below if the repo lives at a different path).
$repoRoot = 'D:\tdx-node'
$task = 'tdx-archivist'
$wrapper = Join-Path $repoRoot 'archivist\run_daily.ps1'
if (-not (Test-Path $wrapper)) { Write-Error "wrapper missing: $wrapper"; exit 1 }
schtasks /Create /TN $task /TR "powershell -NoProfile -ExecutionPolicy Bypass -File $wrapper" /SC DAILY /ST 20:30 /IT /F
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
schtasks /Query /TN $task /FO LIST
