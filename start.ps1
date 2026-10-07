$ErrorActionPreference = 'Stop'
$taskDir = $PSScriptRoot
$pythonPath = Join-Path $taskDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $candidate -or $candidate.Source -like '*\WindowsApps\*') {
        throw 'Install Python 3.10+ from python.org, then run setup.ps1. Or create .venv with your existing Python.'
    }
    & $candidate.Source -X utf8 (Join-Path $taskDir 'setup_check.py')
    if ($LASTEXITCODE -ne 0) { throw 'Python or Pillow is unavailable. Run setup.ps1 first.' }
    $pythonPath = $candidate.Source
}
$pythonwPath = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'pythonw.exe was not found next to python.exe.' }
Start-Process -FilePath $pythonwPath -ArgumentList @('-X', 'utf8', ('"' + (Join-Path $taskDir 'token_quota.py') + '"')) -WorkingDirectory $taskDir -WindowStyle Hidden
