# Operator-started elevated helper for the S2-4E Windows E2E (test-only).
#
# The operator runs this once in an elevated PowerShell window. It then executes
# ONLY the fixed actions below when a request file appears in its protected queue,
# so the coding agent (which runs without elevation, as the same user) can repeat
# the install and the E2E without typing into the elevated window. Stop: Ctrl+C.
#
# Trust model:
#  * The provisioner is NOT run from the mutable repository. At start it is copied to
#    a protected administrator-only folder and its SHA-256 must equal the value the
#    operator passes in -ProvisionerSha256 (the operator takes it from the agent's
#    message). It is re-verified before every run.
#  * The queue lives in a protected folder whose ACL admits only SYSTEM,
#    Administrators and the operator's own user. The ACL, the owner and every request
#    file's owner and name are verified before each request; anything else is refused.
#  * Requests go in <queue>\in (the operator's user may write there); results are written
#    only by this elevated process into <queue>\out (the operator's user may only read).
#    Items that are reparse points (links) are refused, and result files are created
#    with CreateNew, so nothing is ever written through a pre-planted link.
#  * AdminRoot must not pre-exist unless it is administrator-owned and free of links;
#    otherwise the helper aborts and asks the operator to delete it.
#  * Residual risk (accepted, test-only harness): the provisioner installs code from the
#    operator's repository checkout (task manifest, seed script, E2E test) and runs
#    it elevated BY DESIGN, exactly as the operator-run installer did. The SHA-256 pin
#    protects the installer script, not those inputs. A process running as the SAME user
#    as the operator can therefore influence what an elevated run installs.
#
# Request: write <id>.req (id: letters, digits, dashes) into <queue>\in with one action
# name. Result: <id>.out (output), then <id>.done (exit code) in <queue>\out.
#   reinstall  -> provisioner -Action Cleanup, then provisioner install
#   cleanup    -> provisioner -Action Cleanup
#   e2e        -> start the registered E2E scheduled task once, wait, report
#   status     -> services, scheduled task state, recent VST events
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ProvisionerSha256,
    [string]$RepoRoot = 'D:\Repo\Virtual_scrum_team',
    [string]$AdminRoot = 'C:\ProgramData\VST-admin'
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]$identity
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this helper from an elevated PowerShell window.'
}
$userSid = $identity.User.Value
$adminSid = 'S-1-5-32-544'
$systemSid = 'S-1-5-18'
$Queue = Join-Path $AdminRoot 'queue'
$InDir = Join-Path $Queue 'in'
$OutDir = Join-Path $Queue 'out'
$binDir = Join-Path $AdminRoot 'bin'
$provisioner = Join-Path $binDir 'provision_s2_4e_windows.ps1'
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$sourceProvisioner = Join-Path $RepoRoot 'tests\vst\provision_s2_4e_windows.ps1'

function New-ProtectedDirectory([string]$Path, [hashtable]$Grants) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier($adminSid)))
    $inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($entry in $Grants.GetEnumerator()) {
        $sid = New-Object Security.Principal.SecurityIdentifier($entry.Key)
        $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($sid, [Security.AccessControl.FileSystemRights]$entry.Value, $inherit, [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Assert-ProtectedDirectory([string]$Path, [string[]]$AllowedSids) {
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) { throw "Directory ACL is not protected: $Path" }
    $owner = (New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
    if ($owner -ne $adminSid -and $owner -ne $systemSid) { throw "Directory owner is not an administrator principal: $Path" }
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        if ($AllowedSids -notcontains $rule.IdentityReference.Value) { throw "Unexpected principal $($rule.IdentityReference.Value) on $Path" }
    }
}

function Assert-ProvisionerIntegrity {
    $hash = (Get-FileHash -LiteralPath $provisioner -Algorithm SHA256).Hash
    if ($hash -ne $ProvisionerSha256.ToUpperInvariant()) { throw 'Protected provisioner copy failed its SHA-256 check.' }
}

function Assert-NoLinksAndAdminOwned([string]$Path) {
    foreach ($item in @(Get-Item -LiteralPath $Path -Force) + @(Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction Stop)) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing: reparse point under ${Path}: $($item.FullName)" }
        $owner = (New-Object Security.Principal.NTAccount((Get-Acl -LiteralPath $item.FullName).Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
        if ($owner -ne $adminSid -and $owner -ne $systemSid) { throw "Refusing: $($item.FullName) is not owned by an administrator principal. Delete $Path and start again." }
    }
}

# A pre-existing AdminRoot is trusted only if it is already administrator-owned and link-free.
if (Test-Path -LiteralPath $AdminRoot) {
    Assert-NoLinksAndAdminOwned $AdminRoot
    Assert-ProtectedDirectory $AdminRoot @($systemSid, $adminSid, $userSid)
}
# Protected administrator-only copy of the provisioner (verified against the supplied hash).
New-ProtectedDirectory $AdminRoot @{$systemSid='FullControl'; $adminSid='FullControl'}
New-ProtectedDirectory $binDir @{$systemSid='FullControl'; $adminSid='FullControl'}
$sourceHash = (Get-FileHash -LiteralPath $sourceProvisioner -Algorithm SHA256).Hash
if ($sourceHash -ne $ProvisionerSha256.ToUpperInvariant()) {
    throw "Repository provisioner hash $sourceHash does not match the supplied -ProvisionerSha256."
}
if (Test-Path -LiteralPath $provisioner) { Remove-Item -LiteralPath $provisioner -Force }
[IO.File]::Copy($sourceProvisioner, $provisioner, $false)   # never overwrites an existing file
Assert-ProvisionerIntegrity
Assert-NoLinksAndAdminOwned $binDir
Assert-ProtectedDirectory $binDir @($systemSid, $adminSid)
# Protected queue: requests in (operator Modify), results out (operator read only).
New-ProtectedDirectory $Queue @{$systemSid='FullControl'; $adminSid='FullControl'; $userSid='ReadAndExecute'}
New-ProtectedDirectory $InDir @{$systemSid='FullControl'; $adminSid='FullControl'; $userSid='Modify'}
New-ProtectedDirectory $OutDir @{$systemSid='FullControl'; $adminSid='FullControl'; $userSid='ReadAndExecute'}
foreach ($dir in @($Queue, $InDir, $OutDir)) { Assert-ProtectedDirectory $dir @($systemSid, $adminSid, $userSid) }

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
    if ($Action -in @('cleanup', 'reinstall')) { Assert-ProvisionerIntegrity }
    switch ($Action) {
        'cleanup' {
            & $psExe -NoProfile -ExecutionPolicy Bypass -File $provisioner -Action Cleanup -RepoRoot $RepoRoot 2>&1
            "EXIT=$LASTEXITCODE"
        }
        'reinstall' {
            & $psExe -NoProfile -ExecutionPolicy Bypass -File $provisioner -Action Cleanup -RepoRoot $RepoRoot 2>&1
            "CLEANUP_EXIT=$LASTEXITCODE"
            & $psExe -NoProfile -ExecutionPolicy Bypass -File $provisioner -RepoRoot $RepoRoot 2>&1
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

function Write-NewResult([string]$Path, [string[]]$Lines) {
    # CreateNew: fails if anything (including a planted link) already exists at the path.
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($Lines -join "`r`n") + "`r`n")
        $stream.Write($bytes, 0, $bytes.Length)
    } finally { $stream.Dispose() }
}

Write-Host "S2-4E admin runner is waiting for requests in $InDir (Ctrl+C to stop)."
while ($true) {
    foreach ($request in @(Get-ChildItem -LiteralPath $InDir -Filter '*.req' -File -Force -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)) {
        $id = [IO.Path]::GetFileNameWithoutExtension($request.Name)
        $outPath = Join-Path $OutDir "$id.out"
        $donePath = Join-Path $OutDir "$id.done"
        $code = 0
        $lines = @()
        try {
            if ($id -notmatch '^[A-Za-z0-9-]{1,40}$') { throw 'Request name is not allowed.' }
            foreach ($dir in @($Queue, $InDir, $OutDir)) { Assert-ProtectedDirectory $dir @($systemSid, $adminSid, $userSid) }
            if ($request.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Request is a reparse point.' }
            $owner = (New-Object Security.Principal.NTAccount((Get-Acl -LiteralPath $request.FullName).Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
            if ($owner -ne $userSid -and $owner -ne $adminSid) { throw 'Request file owner is not the operator.' }
            $stream = [IO.File]::Open($request.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            try {
                if ($stream.Length -gt 64) { throw 'Request file is too large.' }
                $buffer = New-Object byte[] ([int]$stream.Length)
                [void]$stream.Read($buffer, 0, $buffer.Length)
            } finally { $stream.Dispose() }
            $action = ([Text.Encoding]::UTF8.GetString($buffer)).Trim().ToLowerInvariant()
            Write-Host ("{0:HH:mm:ss} running '{1}' ({2})" -f (Get-Date), $action, $id)
            $lines = @(Invoke-Action $action *>&1 | ForEach-Object { "$_" })
        } catch {
            $code = 1
            $lines += ("RUNNER_ERROR: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
        }
        try {
            Remove-Item -LiteralPath $request.FullName -Force -ErrorAction SilentlyContinue
            Write-NewResult $outPath $lines
            Write-NewResult $donePath @("$code")
        } catch {
            Write-Host ("result for {0} not written: {1}" -f $id, $_.Exception.Message)
        }
        Write-Host ("{0:HH:mm:ss} finished ({1}) code {2}" -f (Get-Date), $id, $code)
    }
    Start-Sleep -Seconds 2
}
