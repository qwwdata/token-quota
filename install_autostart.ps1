param([string]$Python = '')
$ErrorActionPreference = 'Stop'
if (-not $Python) { $Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Run setup.ps1 first, or specify -Python.' }
$Python = (Resolve-Path -LiteralPath $Python).Path
& $Python -X utf8 (Join-Path $PSScriptRoot 'setup_check.py')
if ($LASTEXITCODE -ne 0) { throw 'Python or Pillow is unavailable.' }
$pythonwPath = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwPath)) { throw 'pythonw.exe is unavailable.' }
$taskName = 'TokenQuota-Codex'
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonwPath -Argument ('-X utf8 "' + (Join-Path $PSScriptRoot 'codex_monitor.py') + '"') -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Show Token Quota when the Codex desktop app starts; no quota window when Codex is closed.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host 'Enabled: the battery appears within about 2 seconds of starting Codex.'
