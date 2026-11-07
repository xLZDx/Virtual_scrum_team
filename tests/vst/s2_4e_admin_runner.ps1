# Operator-started elevated helper for the S2-4E Windows E2E (test-only).
#
# The operator runs this once in an elevated PowerShell window. It then executes
# ONLY the fixed actions below when a request file appears in the queue folder,
# so the coding agent (which runs without elevation) can repeat the install and
# the E2E without typing into the elevated window. Stop it with Ctrl+C.
#
# Request: write a file <id>.req into the queue folder whose content is one
# action name. Result: <id>.out (full output) and then <id>.done (exit code).
#   reinstall  -> provisioner -Action Cleanup, then provisioner install
#   cleanup    -> provisioner -Action Cleanup
#   e2e        -> start the registered E2E scheduled task once, wait, report
#   status     -> services, scheduled task state, recent VST events
[CmdletBinding()]
param(
    [string]$Queue = 'D:\tmp\s2_4e_admin_runner',
    [string]$RepoRoot = 'D:\Repo\Virtual_scrum_team'
)

$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this helper from an elevated PowerShell window.'
}
$provisioner = Join-Path $RepoRoot 'tests\vst\provision_s2_4e_windows.ps1'
New-Item -ItemType Directory -Path $Queue -Force | Out-Null

function Get-E2eTaskName {
    # The provisioner registers exactly one task named VST-S2E-<run id>.
    $found = @(Get-ScheduledTask -TaskName 'VST-S2E-*' -ErrorAction SilentlyContinue)
    if ($found.Count -ne 1) { throw "Expected exactly one VST-S2E-* scheduled task, found $($found.Count)." }
    return $found[0].TaskName
}

function Get-VstEvents([int]$Minutes) {
    Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-$Minutes)} -ErrorAction SilentlyContinue |
        Where-Object { $_.ProviderName -like 'VST*' } | Sort-Object TimeCreated |
        ForEach-Object { "VST_EVENT {0:HH:mm:ss} {1}: {2}" -f $_.TimeCreated, $_.ProviderName, (($_.Properties | ForEach-Object { $_.Value }) -join ' | ') }
}

function Invoke-Action([string]$Action) {
    switch ($Action) {
        'cleanup' {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $provisioner -Action Cleanup 2>&1
            "EXIT=$LASTEXITCODE"
        }
        'reinstall' {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $provisioner -Action Cleanup 2>&1
            "CLEANUP_EXIT=$LASTEXITCODE"
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $provisioner 2>&1
            "EXIT=$LASTEXITCODE"
            Get-VstEvents 10
            Get-Service VST* -ErrorAction SilentlyContinue | ForEach-Object { "SERVICE {0} {1}" -f $_.Name, $_.Status }
        }
        'e2e' {
            $taskName = Get-E2eTaskName
            Start-ScheduledTask -TaskName $taskName
            Start-Sleep -Seconds 2
            $deadline = (Get-Date).AddMinutes(25)
            while ((Get-ScheduledTask -TaskName $taskName).State -eq 'Running' -and (Get-Date) -lt $deadline) {
                Start-Sleep -Seconds 5
            }
            $info = Get-ScheduledTaskInfo -TaskName $taskName
            "TASK_STATE=$((Get-ScheduledTask -TaskName $taskName).State)"
            "LAST_TASK_RESULT=$($info.LastTaskResult)"
            "LAST_RUN_TIME=$($info.LastRunTime)"
            $log = 'C:\ProgramData\VST\e2e-output.log'
            if (Test-Path -LiteralPath $log) { '--- e2e-output.log ---'; Get-Content -LiteralPath $log -Tail 200 }
            else { 'E2E_LOG_MISSING' }
            Get-VstEvents 30
            Get-Service VST* -ErrorAction SilentlyContinue | ForEach-Object { "SERVICE {0} {1}" -f $_.Name, $_.Status }
        }
        'status' {
            Get-Service VST* -ErrorAction SilentlyContinue | ForEach-Object { "SERVICE {0} {1}" -f $_.Name, $_.Status }
            $found = @(Get-ScheduledTask -TaskName 'VST-S2E-*' -ErrorAction SilentlyContinue)
            foreach ($t in $found) { "TASK $($t.TaskName) STATE=$($t.State) LAST_TASK_RESULT=$((Get-ScheduledTaskInfo -TaskName $t.TaskName).LastTaskResult)" }
            Get-VstEvents 30
        }
        default { "UNKNOWN_ACTION=$Action (allowed: reinstall, cleanup, e2e, status)" }
    }
}

Write-Host "S2-4E admin runner is waiting for requests in $Queue (Ctrl+C to stop)."
while ($true) {
    foreach ($request in @(Get-ChildItem -LiteralPath $Queue -Filter '*.req' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)) {
        $id = [IO.Path]::GetFileNameWithoutExtension($request.Name)
        $action = (Get-Content -LiteralPath $request.FullName -Raw).Trim().ToLowerInvariant()
        Remove-Item -LiteralPath $request.FullName -Force
        $out = Join-Path $Queue "$id.out"
        Write-Host ("{0:HH:mm:ss} running '{1}' ({2})" -f (Get-Date), $action, $id)
        $code = 0
        try {
            Invoke-Action $action *>&1 | ForEach-Object { "$_" } | Set-Content -LiteralPath $out -Encoding UTF8
        } catch {
            $code = 1
            Add-Content -LiteralPath $out -Value ("RUNNER_ERROR: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message) -Encoding UTF8
        }
        Set-Content -LiteralPath (Join-Path $Queue "$id.done") -Value $code -Encoding ASCII
        Write-Host ("{0:HH:mm:ss} finished '{1}' ({2})" -f (Get-Date), $action, $id)
    }
    Start-Sleep -Seconds 2
}
