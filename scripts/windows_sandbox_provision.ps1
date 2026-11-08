<#
.SYNOPSIS
  One-time OPERATOR provisioning for the Windows-local worker sandbox (S3-D). Run as Administrator.

.DESCRIPTION
  Creates (idempotently):
    1. local non-admin account  vst-worker  (random password, never printed)
    2. a run directory the worker may modify
    3. DENY ACEs for the worker on every -ProtectedPath (signer / key / store paths)
    4. a Windows Firewall outbound Block rule bound to the worker account that blocks all
       non-loopback addresses (loopback stays reachable)
  Prints the plan first. -WhatIf prints the plan and changes nothing.
  This is Windows-local isolation, weaker than the S2 WSL/VM sandbox specification.

.EXAMPLE
  .\windows_sandbox_provision.ps1 -ProtectedPath D:\vst\keys,D:\vst\store -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidatePattern('^[A-Za-z0-9._-]{1,20}$')]
    [string]$WorkerName = 'vst-worker',
    [string]$RunRoot = (Join-Path $env:ProgramData 'vst-runs'),
    [Parameter(Mandatory = $true)]
    [string[]]$ProtectedPath,
    # Optional: DPAPI-protected (current user only) copy of the generated password for the runner launcher.
    [string]$PasswordOutFile,
    [switch]$ResetPassword,
    # Create missing protected directories (empty); without it a missing path is an error.
    [switch]$CreateProtectedPath
)

$ErrorActionPreference = 'Stop'
# powershell -File passes "a,b" as ONE string; split it so comma lists work from any launcher.
$ProtectedPath = @($ProtectedPath | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$RuleName = "vst-worker-egress-block-$WorkerName"
# Everything except 127.0.0.0/8 and ::1 (and ::).
$RemoteAddresses = @('0.0.0.0-126.255.255.255', '128.0.0.0-255.255.255.255',
                     '::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff')

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

$existing = Get-LocalUser -Name $WorkerName -ErrorAction SilentlyContinue

Write-Host '=== vst Windows sandbox provisioning plan ==='
Write-Host ("Worker account : {0} ({1})" -f $WorkerName, $(if ($existing) { 'exists - will be kept' } else { 'will be created, non-admin' }))
Write-Host ("Run directory  : {0} (worker gets Modify)" -f $RunRoot)
foreach ($p in $ProtectedPath) { Write-Host ("Protected path : {0} (worker gets DENY full control)" -f $p) }
Write-Host ("Firewall rule  : {0} (outbound Block for the worker, all non-loopback addresses)" -f $RuleName)
Write-Host 'Known limit    : RunRoot siblings are SHARED between runs (the worker has Modify on the whole RunRoot); per-run isolation is not provided by this script.'
Write-Host '=============================================='

if (-not $WhatIfPreference -and -not (Test-IsAdmin)) {
    throw 'Run this script from an elevated (Administrator) PowerShell, or use -WhatIf.'
}
if ($CreateProtectedPath -and -not $WhatIfPreference) {
    foreach ($p in $ProtectedPath) { if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }
}
# An existing RunRoot must be a real directory owned by SYSTEM or Administrators (no reparse point, no foreign owner).
if (Test-Path -LiteralPath $RunRoot) {
    $rr = Get-Item -LiteralPath $RunRoot -Force
    if ($rr.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "RunRoot is a reparse point; refusing: $RunRoot" }
    $owner = (Get-Acl -LiteralPath $RunRoot).GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($owner -ne 'S-1-5-18' -and $owner -ne 'S-1-5-32-544') { throw "RunRoot owner is $owner, not SYSTEM/Administrators; refusing: $RunRoot" }
}
foreach ($p in $ProtectedPath) {
    if (-not (Test-Path -LiteralPath $p) -and -not ($WhatIfPreference -and $CreateProtectedPath)) { throw "Protected path does not exist: $p (use -CreateProtectedPath to create it)" }
}

function New-RandomPassword {
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ([Convert]::ToBase64String($bytes) + 'aA1!')
}

# 1. account ---------------------------------------------------------------
$sid = $null
if (-not $existing) {
    if ($PSCmdlet.ShouldProcess($WorkerName, 'Create local non-admin user')) {
        $plain = New-RandomPassword
        $secure = ConvertTo-SecureString $plain -AsPlainText -Force
        $existing = New-LocalUser -Name $WorkerName -Password $secure -PasswordNeverExpires `
            -UserMayNotChangePassword -Description 'VST sandbox worker (non-admin)'
        if ($PasswordOutFile) {
            $secure | ConvertFrom-SecureString | Set-Content -LiteralPath $PasswordOutFile -Encoding ASCII
            Write-Host "Password saved (DPAPI, current user only): $PasswordOutFile"
        }
    }
} elseif ($ResetPassword -and $PSCmdlet.ShouldProcess($WorkerName, 'Reset password')) {
    $plain = New-RandomPassword
    $secure = ConvertTo-SecureString $plain -AsPlainText -Force
    Set-LocalUser -Name $WorkerName -Password $secure
    if ($PasswordOutFile) { $secure | ConvertFrom-SecureString | Set-Content -LiteralPath $PasswordOutFile -Encoding ASCII }
}
if ($existing) {
    $sid = $existing.SID.Value
    # Never leave the worker in Administrators.
    $admins = @(Get-LocalGroupMember -SID 'S-1-5-32-544' | Where-Object { $_.SID.Value -eq $sid })
    if ($admins.Count -gt 0) { throw "Account $WorkerName is in Administrators; refusing to continue. Remove it manually." }
}

# 2. run directory ---------------------------------------------------------
if ($PSCmdlet.ShouldProcess($RunRoot, 'Create run directory and grant worker Modify')) {
    New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
    & icacls.exe $RunRoot /grant "${WorkerName}:(OI)(CI)M" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls grant failed for $RunRoot" }
}

# 3. deny ACEs on protected paths (re-applying an identical ACE is a no-op) --
foreach ($p in $ProtectedPath) {
    if ($PSCmdlet.ShouldProcess($p, "Deny $WorkerName full control")) {
        & icacls.exe $p /deny "${WorkerName}:(OI)(CI)(F)" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "icacls deny failed for $p" }
    }
}

# 4. firewall rule (create, or enforce properties if it already exists) ------
$sddl = if ($sid) { "D:(A;;CC;;;$sid)" } else { 'D:(A;;CC;;;<worker-sid-after-creation>)' }
if ($PSCmdlet.ShouldProcess($RuleName, 'Create or update outbound Block firewall rule for the worker')) {
    if (Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue) {
        # Remove and recreate: a partial Set-NetFirewallRule could keep stale restrictions (ports, program, ...).
        Remove-NetFirewallRule -Name $RuleName
    }
    New-NetFirewallRule -Name $RuleName -DisplayName $RuleName -Direction Outbound -Action Block `
        -Enabled True -Profile Any -LocalUser $sddl -RemoteAddress $RemoteAddresses | Out-Null
}

Write-Host 'Done. Verify with tools/vst/windows_sandbox_proof.py (read-only collectors); this script does not prove isolation.'
