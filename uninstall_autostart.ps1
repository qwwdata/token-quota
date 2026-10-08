$ErrorActionPreference = 'Stop'
$taskName = 'TokenQuota-Codex'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
Write-Host 'Disabled: Codex will no longer open the battery automatically.'
