param([string]$Python = '')
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $candidate = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $candidate -or $candidate.Source -like '*\WindowsApps\*') {
        throw 'Install Python 3.10+ from python.org, or pass -Python with the path to an existing interpreter.'
    }
    $Python = $candidate.Source
}
& $Python -X utf8 -m venv (Join-Path $PSScriptRoot '.venv')
if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv.' }
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $venvPython -X utf8 -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Failed to install dependencies.' }
Write-Host 'Ready. Double-click start.cmd.'
