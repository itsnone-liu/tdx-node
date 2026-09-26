# tdx-archivist daily wrapper — ASCII only (scheduler-safe)
$ErrorActionPreference = 'Continue'
Set-Location 'D:\tdx-node\tdx-tq-v773\PYPlugins\user'
$env:PYTHONIOENCODING = 'utf-8'
$logDir = 'D:\tdx-node\archive\_logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"=== $stamp run start ===" | Add-Content (Join-Path $logDir 'daily.log')
python 'D:\tdx-node\archivist\daily_archive.py' 2>&1 | Add-Content (Join-Path $logDir 'daily.log')
$code = $LASTEXITCODE
"=== run exit $code ===" | Add-Content (Join-Path $logDir 'daily.log')
exit $code
