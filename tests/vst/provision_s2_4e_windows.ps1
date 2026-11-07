[CmdletBinding()]
param(
    [ValidateSet('Install', 'Cleanup')]
    [string]$Action = 'Install',
    [string]$RepoRoot = 'D:\Repo\Virtual_scrum_team',
    [string]$Python = 'C:\Python314\python.exe',
    # Native (mingw64) build: the MSYS build in usr\bin fails under a write-restricted
    # service token because the cygwin runtime needs writable shared memory.
    [string]$OpenSSLSource = 'C:\Program Files\Git\mingw64\bin\openssl.exe',
    [string]$Git = 'C:\Program Files\Git\cmd\git.exe'
)

$ErrorActionPreference = 'Stop'
$transcriptPath = Join-Path $RepoRoot 'docs\sdlc\evidence\s2-4e-windows-provision.log'
Start-Transcript -Path $transcriptPath -Append | Out-Null
trap {
    try { Write-Host ("INSTALLER_ERROR: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message) } catch {}
    # Show the services' own sanitized failure/refusal events so one run is enough to diagnose.
    try {
        Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-20)} -ErrorAction Stop |
            Where-Object { $_.ProviderName -like 'VST*' } | Sort-Object TimeCreated | Select-Object -Last 20 |
            ForEach-Object { Write-Host ("VST_EVENT {0:HH:mm:ss} {1}: {2}" -f $_.TimeCreated, $_.ProviderName, (($_.Properties | ForEach-Object { $_.Value }) -join ' | ')) }
    } catch {}
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
$serviceNames = @('VSTOwner', 'VSTSupervisor', 'VSTDispatcher', 'VSTRunner', 'VSTSigner', 'VSTWorker')
$serviceRoles = @{
    VSTOwner = 'owner'; VSTSupervisor = 'supervisor'; VSTDispatcher = 'dispatcher'
    VSTRunner = 'runner'; VSTSigner = 'signer'; VSTWorker = 'worker'
}
$root = Join-Path $env:ProgramData 'VST'
$adminSid = 'S-1-5-32-544'
$systemSid = 'S-1-5-18'

function Invoke-Sc([string[]]$Arguments) {
    & "$env:SystemRoot\System32\sc.exe" @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "SCM operation failed: $($Arguments -join ' ') (exit $LASTEXITCODE)" }
}

function Set-ExplicitAcl([string]$Path, [bool]$Directory, [hashtable]$Grants) {
    $sid = New-Object Security.Principal.SecurityIdentifier($adminSid)
    if ($Directory) { $acl = New-Object Security.AccessControl.DirectorySecurity }
    else { $acl = New-Object Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner($sid)
    foreach ($entry in $Grants.GetEnumerator()) {
        $trustee = New-Object Security.Principal.SecurityIdentifier($entry.Key)
        $rights = [Security.AccessControl.FileSystemRights]$entry.Value
        if ($Directory) {
            $inheritance = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
            $rule = New-Object Security.AccessControl.FileSystemAccessRule($trustee, $rights, $inheritance, [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
        } else {
            $rule = New-Object Security.AccessControl.FileSystemAccessRule($trustee, $rights, [Security.AccessControl.AccessControlType]::Allow)
        }
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Get-ServiceSid([string]$Name) {
    $account = New-Object Security.Principal.NTAccount("NT SERVICE\$Name")
    return $account.Translate([Security.Principal.SecurityIdentifier]).Value
}

function Assert-TrustedRuntimeTree([string]$Path) {
    $trusted = @($systemSid, $adminSid)
    try { $trusted += (New-Object Security.Principal.NTAccount('NT SERVICE\TrustedInstaller')).Translate([Security.Principal.SecurityIdentifier]).Value } catch {}
    # Write-capable bits only. FileSystemRights.Modify must not be used here: it also contains the
    # read/execute bits, so every ordinary ReadAndExecute grant would be misreported as writable.
    # Generic write/all bits are included because raw ACEs may carry them unmapped.
    $writeMask = [int64][Security.AccessControl.FileSystemRights]::Write -bor
        [int64]0x40000000 -bor [int64]0x10000000 -bor
        [Security.AccessControl.FileSystemRights]::Delete -bor
        [Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [Security.AccessControl.FileSystemRights]::TakeOwnership -bor
        [Security.AccessControl.FileSystemRights]::CreateDirectories -bor
        [Security.AccessControl.FileSystemRights]::CreateFiles
    $items = @((Get-Item -LiteralPath $Path -Force))
    if ((Get-Item -LiteralPath $Path -Force).PSIsContainer) {
        $items += Get-ChildItem -LiteralPath $Path -Recurse -Force
    }
    foreach ($item in $items) {
        $acl = Get-Acl -LiteralPath $item.FullName
        # Read the owner and rules as SIDs directly: names such as
        # "APPLICATION PACKAGE AUTHORITY\ALL APPLICATION PACKAGES" cannot be translated back to SIDs.
        $ownerSid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        if ($ownerSid -notin $trusted) { throw "Untrusted owner on service runtime path: $($item.FullName)" }
        foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { continue }
            # An inherit-only ACE grants nothing on this object; every descendant is scanned with its own ACL.
            if ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
            $trusteeSid = $rule.IdentityReference.Value
            if ($trusteeSid -notin $trusted -and (([int64]$rule.FileSystemRights -band [int64]$writeMask) -ne 0)) {
                throw "A non-admin principal can modify service runtime code: $($item.FullName)"
            }
        }
    }
    $pathRoot = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Path))
    $ancestor = Split-Path -Parent ([IO.Path]::GetFullPath($Path))
    while ($ancestor -and $ancestor -ne $pathRoot.TrimEnd('\')) {
        $acl = Get-Acl -LiteralPath $ancestor
        foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
            if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { continue }
            if ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
            $trusteeSid = $rule.IdentityReference.Value
            if ($trusteeSid -notin $trusted -and
                    (([int64]$rule.FileSystemRights -band [int64][Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles) -ne 0)) {
                throw "A non-admin principal can replace the trusted runtime directory: $ancestor"
            }
        }
        $nextAncestor = Split-Path -Parent $ancestor
        if ($nextAncestor -eq $ancestor) { break }
        $ancestor = $nextAncestor
    }
}

function Get-BytesSha256([byte[]]$Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Remove-OwnedSetup {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { return }
    $markerPath = Join-Path $root 'setup-owner.json'
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) { throw 'Refusing cleanup: VST root has no provisioner marker.' }
    $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
    $resolvedRoot = (Resolve-Path -LiteralPath $root).Path
    $expectedRoot = [IO.Path]::GetFullPath((Join-Path $env:ProgramData 'VST'))
    if ($resolvedRoot -ne $expectedRoot -or $marker.test_only -ne $true -or $marker.project_id -ne 'Virtual_scrum_team' -or
            (@($marker.service_names) -join ',') -ne ($serviceNames -join ',')) {
        throw 'Refusing cleanup: path or ownership marker does not match this test setup.'
    }
    $taskName = [string]$marker.task_name
    if ($taskName) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($task -and [string]$task.State -eq 'Running') {
            throw 'Refusing cleanup while the one-shot Owner-to-Runner E2E task is running; wait for its result first.'
        }
        if ($task) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
    }
    foreach ($name in $serviceNames) {
        $service = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($service) {
            $serviceConfig = Get-CimInstance -ClassName Win32_Service -Filter "Name='$name'"
            $expectedLauncher = Join-Path (Join-Path $root 'launchers') ("run-{0}.py" -f $serviceRoles[$name])
            $expectedPython = if ($marker.python_path) { [string]$marker.python_path } else { [IO.Path]::GetFullPath($Python) }
            $expectedImage = '"{0}" "{1}"' -f $expectedPython, $expectedLauncher
            if (-not $serviceConfig -or $serviceConfig.PathName.Trim() -ine $expectedImage) {
                throw "Refusing cleanup: service $name does not point to this setup's launcher."
            }
            if ($service.Status -ne 'Stopped') {
                Stop-Service -Name $name -Force
                $deadline = [DateTime]::UtcNow.AddSeconds(30)
                do {
                    Start-Sleep -Milliseconds 250
                    $service = Get-Service -Name $name
                    if ($service.Status -eq 'Stopped') { break }
                    if ([DateTime]::UtcNow -ge $deadline) { throw "Service $name did not stop; preserving its files." }
                } while ($true)
            }
            Invoke-Sc @('delete', $name)
        }
    }
    Remove-Item -LiteralPath $root -Recurse -Force
    Write-Output '{"cleanup":"removed test-only VST root and services"}'
}

if ($Action -eq 'Cleanup') {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Cleanup requires an elevated Windows token.' }
    Remove-OwnedSetup
    try { Stop-Transcript | Out-Null } catch {}
    exit 0
}

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Install requires an elevated Windows token.' }
$repo = [IO.Path]::GetFullPath($RepoRoot)
$pythonPath = [IO.Path]::GetFullPath($Python)
$opensslSourcePath = [IO.Path]::GetFullPath($OpenSSLSource)
$gitPath = [IO.Path]::GetFullPath($Git)
if (-not (Test-Path -LiteralPath $repo -PathType Container)) { throw 'Project root is unavailable.' }
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Configured Windows Python is unavailable.' }
if (-not (Test-Path -LiteralPath $opensslSourcePath -PathType Leaf)) { throw 'Git for Windows OpenSSL is unavailable.' }
if (-not (Test-Path -LiteralPath $gitPath -PathType Leaf)) { throw 'Configured Git for Windows executable is unavailable.' }
Assert-TrustedRuntimeTree (Split-Path -Parent $pythonPath)
Assert-TrustedRuntimeTree (Split-Path -Parent $opensslSourcePath)
$gitRoot = Split-Path -Parent (Split-Path -Parent $gitPath)
Assert-TrustedRuntimeTree $gitRoot
$sourceManifest = Join-Path $repo 'docs\sdlc\runtime-config\task-manifest.json'
$candidateFiles = @(
    'docs\sdlc\runtime-config\task-manifest.json',
    'tests\vst\test_s2_owner_completed_receipt_contract.py',
    'tests\vst\test_s2_owner_runner_windows_e2e.py',
    'tests\vst\s2_4e_windows_provision.py',
    'tests\vst\provision_s2_4e_windows.ps1'
)
$candidateContents = @{}
$candidateHashes = @{}
foreach ($relativePath in $candidateFiles) {
    $bytes = [IO.File]::ReadAllBytes((Join-Path $repo $relativePath))
    $candidateContents[$relativePath] = $bytes
    $candidateHashes[$relativePath] = Get-BytesSha256 $bytes
}
$candidateManifest = [Text.Encoding]::UTF8.GetString($candidateContents['docs\sdlc\runtime-config\task-manifest.json']).TrimStart([char]0xFEFF) | ConvertFrom-Json
if ($candidateManifest.task_id -ne 'S2-4E-WINDOWS-OWNER-RUNNER' -or @($candidateManifest.acceptance).Count -ne 1 -or $candidateManifest.acceptance[0] -ne 'REQ-003' -or $candidateManifest.retry_cap -ne 0 -or $candidateManifest.base_head -notmatch '^[0-9a-f]{40}$') {
    throw 'Source manifest does not match the approved one-shot REQ-003 contract.'
}
$baseHead = [string]$candidateManifest.base_head
if (Test-Path -LiteralPath $root) { throw 'Refusing to overwrite existing %ProgramData%\VST.' }
foreach ($name in $serviceNames) {
    if (Get-Service -Name $name -ErrorAction SilentlyContinue) { throw "Refusing to replace existing service $name." }
}

$runId = 's2-4e-win-' + [guid]::NewGuid().ToString('N').Substring(0, 16)
$data = $root
$store = Join-Path $root 'store'
$signer = Join-Path $root 'signer'
$issuer = Join-Path $root 'issuer-private'
$bin = Join-Path $root 'bin'
$launchers = Join-Path $root 'launchers'
$app = Join-Path $root 'app'
$appManifest = Join-Path $app 'docs\sdlc\runtime-config\task-manifest.json'
$log = Join-Path $root 'e2e-output.log'
$taskName = 'VST-S2E-' + $runId
$gitHooks = Join-Path $root 'git-hooks'
$emptyGitConfig = Join-Path $root 'empty-gitconfig'
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value

New-Item -ItemType Directory -Path $root -Force | Out-Null
Set-ExplicitAcl $root $true @{$systemSid='FullControl'; $adminSid='FullControl'}
New-Item -ItemType Directory -Path $store, $signer, $issuer, $bin, $launchers, $gitHooks -Force | Out-Null
[IO.File]::WriteAllBytes($emptyGitConfig, [byte[]]@())
$setupMarker = [ordered]@{project_id='Virtual_scrum_team'; run_id=$runId; task_name=$taskName; service_names=$serviceNames; python_path=$pythonPath; test_only=$true}
$setupMarker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $root 'setup-owner.json') -Encoding UTF8
$safeAppPath = $app.Replace('\', '/')
$safeHooksPath = $gitHooks.Replace('\', '/')
[IO.File]::WriteAllText($emptyGitConfig, "[safe]`ndirectory = $safeAppPath`n[core]`nhooksPath = $safeHooksPath`n", [Text.UTF8Encoding]::new($false))

# A separate shallow Git context at the task's exact base HEAD is required by
# the product Runner when it derives the signed candidate_head/diff receipt.
# Fetch the manifest's exact base commit by hash, not the branch tip: later
# commits on the branch must not change the accepted task baseline.
$oldGitConfig = $env:GIT_CONFIG_NOSYSTEM
$oldGlobalGitConfig = $env:GIT_CONFIG_GLOBAL
$oldGitPrompt = $env:GIT_TERMINAL_PROMPT
try {
    $env:GIT_CONFIG_NOSYSTEM = '1'
    $env:GIT_CONFIG_GLOBAL = $emptyGitConfig
    $env:GIT_TERMINAL_PROMPT = '0'
    New-Item -ItemType Directory -Path $app | Out-Null
    Set-ExplicitAcl $app $true @{$systemSid='FullControl'; $adminSid='FullControl'}
    & $gitPath -C $app -c "core.hooksPath=$gitHooks" init --quiet
    if ($LASTEXITCODE -ne 0) { throw "Could not initialize the protected task Git context (exit $LASTEXITCODE)." }
    & $gitPath -C $app remote add origin $repo
    if ($LASTEXITCODE -ne 0) { throw "Could not configure the protected task Git source (exit $LASTEXITCODE)." }
    & $gitPath -C $app -c "core.hooksPath=$gitHooks" fetch --quiet --depth=1 --no-tags origin $baseHead
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch the task base HEAD into the protected context (exit $LASTEXITCODE)." }
    & $gitPath -C $app -c "core.hooksPath=$gitHooks" checkout --quiet --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "Could not check out the task base HEAD (exit $LASTEXITCODE)." }
    $snapshotHead = (& $gitPath -C $app rev-parse --verify HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $snapshotHead -cne $baseHead) { throw 'Protected task Git context does not match manifest base_head.' }
} finally {
    $env:GIT_CONFIG_NOSYSTEM = $oldGitConfig
    $env:GIT_CONFIG_GLOBAL = $oldGlobalGitConfig
    $env:GIT_TERMINAL_PROMPT = $oldGitPrompt
}
foreach ($relativePath in $candidateFiles) {
    $destination = Join-Path $app $relativePath
    [IO.File]::WriteAllBytes($destination, [byte[]]$candidateContents[$relativePath])
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -cne $candidateHashes[$relativePath]) {
        throw "Protected source snapshot hash mismatch: $relativePath"
    }
}
$snapshotManifest = Get-Content -LiteralPath $appManifest -Raw | ConvertFrom-Json
if ($snapshotManifest.base_head -cne $snapshotHead) { throw 'Protected candidate manifest base_head does not match the Git context.' }
# Lock the copied code snapshot to SYSTEM/Administrators before executing its helper elevated.
Set-ExplicitAcl $app $true @{$systemSid='FullControl'; $adminSid='FullControl'}
foreach ($path in (Get-ChildItem -LiteralPath $app -File -Recurse -Force)) {
    Set-ExplicitAcl $path.FullName $false @{$systemSid='FullControl'; $adminSid='FullControl'}
}
foreach ($path in (Get-ChildItem -LiteralPath $app -Directory -Recurse -Force)) {
    Set-ExplicitAcl $path.FullName $true @{$systemSid='FullControl'; $adminSid='FullControl'}
}

$sourceBin = Split-Path -Parent $opensslSourcePath
Copy-Item -LiteralPath $opensslSourcePath -Destination (Join-Path $bin 'openssl.exe')
# Import closure of mingw64 openssl.exe (probe P1b): only these two non-system DLLs.
foreach ($dll in @('libcrypto-3-x64.dll', 'libssl-3-x64.dll')) {
    $dllPath = Join-Path $sourceBin $dll
    if (-not (Test-Path -LiteralPath $dllPath -PathType Leaf)) { throw "Required OpenSSL runtime dependency is missing: $dll" }
    Copy-Item -LiteralPath $dllPath -Destination (Join-Path $bin $dll)
}

$serviceSids = @{}
foreach ($name in $serviceNames) {
    $role = $serviceRoles[$name]
    $launcher = Join-Path $launchers ("run-{0}.py" -f $role)
    # Write-restricted service tokens cannot write to the shared system TEMP, so each
    # role gets its own protected temp directory (created below once its SID exists).
    $roleTemp = Join-Path (Join-Path $root 'tmp') $role
$launcherText = "import os, sys, tempfile`nos.environ['TEMP'] = os.environ['TMP'] = r'$roleTemp'`ntempfile.tempdir = r'$roleTemp'`nos.environ['PATH'] = r'$(Split-Path -Parent $gitPath)' + os.pathsep + r'$env:SystemRoot\System32'`nos.environ['GIT_CONFIG_NOSYSTEM'] = '1'`nos.environ['GIT_CONFIG_GLOBAL'] = r'$emptyGitConfig'`nos.environ['GIT_TERMINAL_PROMPT'] = '0'`nsys.dont_write_bytecode = True`nsys.path.insert(0, r'$app')`nfrom tools.vst.windows_service_host import main`nsys.argv = [__file__, '--role', '$role']`nmain()`n"
    Set-Content -LiteralPath $launcher -Value $launcherText -Encoding Ascii
    $binaryPath = '"{0}" "{1}"' -f $pythonPath, $launcher
    # Windows PowerShell 5.1 strips embedded quotes and drops empty arguments when calling
    # native programs, so `sc.exe create binPath= "<quoted>" password= ''` is corrupted.
    # New-Service passes the image path through the SCM API unchanged; the virtual
    # account is then assigned without a password.
    New-Service -Name $name -BinaryPathName $binaryPath -StartupType Manual | Out-Null
    Invoke-Sc @('config', $name, 'obj=', "NT SERVICE\$name")
    Invoke-Sc @('sidtype', $name, 'restricted')
    $serviceSids[$name] = Get-ServiceSid $name
}

$allRead = @{$systemSid='FullControl'; $adminSid='FullControl'}
foreach ($sid in $serviceSids.Values) { $allRead[$sid] = 'ReadAndExecute' }
Set-ExplicitAcl $root $true $allRead
Set-ExplicitAcl $data $true $allRead
Set-ExplicitAcl $bin $true $allRead
Set-ExplicitAcl $launchers $true $allRead
Set-ExplicitAcl $app $true $allRead
$storeGrants = @{$systemSid='FullControl'; $adminSid='FullControl'; $serviceSids['VSTSupervisor']='FullControl'}
$signerGrants = @{$systemSid='FullControl'; $adminSid='FullControl'; $serviceSids['VSTSigner']='FullControl'}
$issuerGrants = @{$systemSid='FullControl'; $adminSid='FullControl'}
Set-ExplicitAcl $store $true $storeGrants
Set-ExplicitAcl $signer $true $signerGrants
Set-ExplicitAcl $issuer $true $issuerGrants
$tempRoot = Join-Path $root 'tmp'
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
Set-ExplicitAcl $tempRoot $true $allRead
foreach ($name in $serviceNames) {
    $roleTemp = Join-Path $tempRoot $serviceRoles[$name]
    New-Item -ItemType Directory -Path $roleTemp -Force | Out-Null
    Set-ExplicitAcl $roleTemp $true @{$systemSid='FullControl'; $adminSid='FullControl'; $serviceSids[$name]='Modify'}
}

$opensslPath = Join-Path $bin 'openssl.exe'
$pythonArgs = @('-B', '-m', 'tests.vst.s2_4e_windows_provision', '--root', $root, '--repo', $app, '--openssl', $opensslPath, '--owner-sid', $userSid, '--run-id', $runId)
$previousLocation = Get-Location
try {
    Set-Location -LiteralPath $app
    & $pythonPath @pythonArgs
    if ($LASTEXITCODE -ne 0) { throw "Test input preparation failed with exit code $LASTEXITCODE." }
} finally { Set-Location $previousLocation }

$readFileGrants = @{$systemSid='FullControl'; $adminSid='FullControl'}
foreach ($sid in $serviceSids.Values) { $readFileGrants[$sid] = 'ReadAndExecute' }
foreach ($path in (Get-ChildItem -LiteralPath $data -File -Force)) { Set-ExplicitAcl $path.FullName $false $readFileGrants }
foreach ($path in (Get-ChildItem -LiteralPath $bin -File -Force)) { Set-ExplicitAcl $path.FullName $false $readFileGrants }
foreach ($path in (Get-ChildItem -LiteralPath $launchers -File -Force)) { Set-ExplicitAcl $path.FullName $false $readFileGrants }
foreach ($path in (Get-ChildItem -LiteralPath $app -File -Recurse -Force)) { Set-ExplicitAcl $path.FullName $false $allRead }
foreach ($path in (Get-ChildItem -LiteralPath $app -Directory -Recurse -Force)) { Set-ExplicitAcl $path.FullName $true $allRead }
$supervisorRead = @{$systemSid='FullControl'; $adminSid='FullControl'; $serviceSids['VSTSupervisor']='Read'}
foreach ($name in @('event.key', 'startup.key', 'resolution.key', 'grant-private.pem')) {
    Set-ExplicitAcl (Join-Path $store $name) $false $supervisorRead
}
$signerRead = @{$systemSid='FullControl'; $adminSid='FullControl'; $serviceSids['VSTSigner']='Read'}
Set-ExplicitAcl (Join-Path $signer 'receipt.key') $false $signerRead
$ownerPrivateGrant = @{$systemSid='FullControl'; $adminSid='FullControl'}
Set-ExplicitAcl (Join-Path $issuer 'owner-private.pem') $false $ownerPrivateGrant

$testTask = Join-Path $root 'run-e2e.ps1'
$testTaskText = @"
`$env:VST_S2E_INSTRUCTION_INPUT = '$(Join-Path $data 'owner-instruction.json')'
`$env:VST_S2E_MANIFEST_INPUT = '$appManifest'
Set-Location -LiteralPath '$app'
& '$pythonPath' -B -m tests.vst.test_s2_owner_runner_windows_e2e *> '$log'
exit `$LASTEXITCODE
"@
Set-Content -LiteralPath $testTask -Value $testTaskText -Encoding UTF8
Set-ExplicitAcl $testTask $false $readFileGrants
$taskAction = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$testTask`""
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
# The task must outlive the manifest execution timeout plus bounded margins for
# Owner/Dispatcher/Runner IPC, receipt persistence and the E2E poll (manifest
# timeout + 120 s), so Task Scheduler never kills a run the contract still allows.
$manifestTimeoutSec = [int]$snapshotManifest.timeout_sec
if ($manifestTimeoutSec -lt 1 -or $manifestTimeoutSec -gt 3600) { throw 'Snapshot manifest timeout_sec is outside 1..3600.' }
$taskLimitSec = $manifestTimeoutSec + 300
if ($taskLimitSec -le $manifestTimeoutSec + 120) { throw 'Scheduled-task limit does not cover the manifest timeout and E2E poll margin.' }
$taskSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds $taskLimitSec) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Principal $taskPrincipal -Settings $taskSettings | Out-Null

foreach ($name in @('VSTSupervisor', 'VSTWorker', 'VSTSigner', 'VSTRunner', 'VSTDispatcher', 'VSTOwner')) {
    Start-Service -Name $name
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 250
        $service = Get-Service -Name $name
        if ($service.Status -eq 'Running') { break }
        if ([DateTime]::UtcNow -ge $deadline) { throw "Service $name did not enter RUNNING state." }
    } while ($true)
}

Write-Output (ConvertTo-Json -Compress ([ordered]@{setup='READY'; run_id=$runId; task_id='S2-4E-WINDOWS-OWNER-RUNNER'; service_task=$taskName; output_log=$log; test_only=$true}))
Stop-Transcript | Out-Null
