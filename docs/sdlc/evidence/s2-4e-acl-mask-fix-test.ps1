# Focused functional test for Assert-TrustedRuntimeTree (S2-4E ACL write-mask fix).
# Runs in Windows PowerShell 5.1, non-elevated, read-only against C:\Python314, temp fixtures only.
# Does NOT run the installer. Usage: powershell.exe -NoProfile -ExecutionPolicy Bypass -File <this> -OutJson <path>
param([string]$OutJson)
$ErrorActionPreference = 'Stop'
$repo = 'D:\Repo\Virtual_scrum_team'
$target = Join-Path $repo 'tests\vst\provision_s2_4e_windows.ps1'
$results = New-Object System.Collections.ArrayList
function Add-Result([string]$Id, [string]$Desc, [bool]$Pass, [string]$Detail) {
    [void]$results.Add([ordered]@{ case = $Id; description = $Desc; result = $(if ($Pass) { 'PASS' } else { 'FAIL' }); detail = $Detail })
    Write-Host ("[{0}] {1} - {2}" -f $(if ($Pass) { 'PASS' } else { 'FAIL' }), $Id, $Detail)
}

# --- Case 1: parser check ---
$tokens = $null; $errs = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($target, [ref]$tokens, [ref]$errs)
Add-Result 'T1_parse_ps51' 'powershell.exe parses edited file with no errors' ($errs.Count -eq 0) ("PSVersion=$($PSVersionTable.PSVersion) parseErrors=$($errs.Count)")

# --- Extract function and the SID definitions exactly as the script defines them ---
$fn = $ast.Find({ param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-TrustedRuntimeTree' }, $true)
$fnText = $fn.Extent.Text
$srcText = [IO.File]::ReadAllText($target)
$m1 = [regex]::Match($srcText, "(?m)^\`$adminSid = '(S-1-5-32-544)'")
$m2 = [regex]::Match($srcText, "(?m)^\`$systemSid = '(S-1-5-18)'")
if (-not ($m1.Success -and $m2.Success)) { throw 'SID definitions not found in script' }
$adminSid = $m1.Groups[1].Value
$systemSid = $m2.Groups[1].Value
$extraSid = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)   # harness-only, used by modified copy
# Harness-only: AppData\Local carries AppContainer SIDs (S-1-15-3-*) with FullControl; ancestor noise, not the logic under test.
foreach ($ace in (Get-Acl (Join-Path $env:USERPROFILE 'AppData\Local')).Access) {
    try { $sv = $ace.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { $sv = $null }
    if ($sv -and $sv -like 'S-1-15-3-*') { $extraSid += $sv }
}
Write-Host "adminSid=$adminSid systemSid=$systemSid currentUserSid=$extraSid"

function Run-Fn([string]$Text, [string]$Path) {
    . ([scriptblock]::Create($Text))   # defines the function in this call's scope
    try { Assert-TrustedRuntimeTree $Path; return @{ threw = $false; msg = '' } }
    catch { return @{ threw = $true; msg = $_.Exception.Message } }
}

# --- Case 2a: positive against real C:\Python314, unmodified function ---
$r = Run-Fn $fnText 'C:\Python314'
Add-Result 'T2a_python314_no_throw' 'unmodified function does not throw on C:\Python314' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")

# --- Case 2a (S2-4E second defect): real trees whose ACLs carry S-1-15-2-1 / S-1-15-2-2 ReadAndExecute ACEs ---
$gitTrees = @('C:\Program Files\Git\usr\bin', 'C:\Program Files\Git')
foreach ($gt in $gitTrees) {
    if (-not (Test-Path -LiteralPath $gt)) { Add-Result ('T2a_real_tree_' + ($gt -replace '[^A-Za-z0-9]', '_')) 'real tree present' $false "missing: $gt"; continue }
    $r = Run-Fn $fnText $gt
    Add-Result ('T2a_real_tree_no_throw_' + ($gt -replace '[^A-Za-z0-9]', '_')) "unmodified function does not throw on $gt" (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")
}

# --- Case 2c: mutant restoring the old .Access + IdentityReference.Translate lines (owner + item rules + ancestor rules) ---
$newOwner = '$ownerSid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value'
$oldOwner = '$ownerSid = (New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value'
$newRules = '$acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])'
$newTrustee = '$trusteeSid = $rule.IdentityReference.Value'
$oldTrustee = '$trusteeSid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value'
foreach ($n in @($newOwner, $newRules, $newTrustee)) { if (-not $fnText.Contains($n)) { throw "mutant needle not found: $n" } }
function Make-TranslateMutant([string]$Text, [bool]$OwnerToo) {
    $t = $Text.Replace($newRules, '$acl.Access').Replace($newTrustee, $oldTrustee)
    if ($OwnerToo) { $t = $t.Replace($newOwner, $oldOwner) }
    return $t
}
$mutTranslate = Make-TranslateMutant $fnText $true
foreach ($gt in $gitTrees) {
    $r = Run-Fn $mutTranslate $gt
    Add-Result ('T2c_mutant_translate_throws_' + ($gt -replace '[^A-Za-z0-9]', '_')) "mutant (old .Access + Translate): $gt throws Translate error" ($r.threw -and $r.msg -like '*could not be translated*') ("threw=$($r.threw) msg=$($r.msg)")
}
$r = Run-Fn $mutTranslate 'C:\Python314'
Add-Result 'T2c_mutant_translate_python314_still_ok' 'mutant: C:\Python314 still passes (confirms only package-SID trees expose the defect)' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")

# --- Harness variant: identical function, but current user added to trusted list so that the
# non-elevated owner / %TEMP% ancestor chain does not mask the write-mask logic under test. ---
$trustedLine = '$trusted = @($systemSid, $adminSid)'
if (-not $fnText.Contains($trustedLine)) { throw 'trusted line not found' }
$harnessText = $fnText.Replace($trustedLine, '$trusted = @($systemSid, $adminSid) + @($extraSid)')

$base = Join-Path $env:TEMP ('s24e_acl_test_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $base | Out-Null
$usersSid = '*S-1-5-32-545'
function New-Fixture([string]$Name, [string]$Grant, [switch]$DirGrant) {
    $d = Join-Path $base $Name
    New-Item -ItemType Directory -Path $d | Out-Null
    $f = Join-Path $d 'runtime.py'
    Set-Content -LiteralPath $f -Value 'x'
    if ($Grant) {
        $t = if ($DirGrant) { $d } else { $f }
        $o = & icacls $t /grant "${usersSid}:$Grant" 2>&1
        if ($LASTEXITCODE -ne 0) { throw "icacls failed: $o" }
    }
    return $d
}
try {
    $dCtl = New-Fixture 'ctl' ''
    $r = Run-Fn $harnessText $dCtl
    Add-Result 'T2b0_control_no_users_grant' 'harness variant: file without Users grant does not throw' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")

    $dM = New-Fixture 'modify' '(M)'
    $r = Run-Fn $harnessText $dM
    Add-Result 'T2b1_users_modify_throws' 'Users:(M) on file -> throws can-modify' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")
    $rM_mut = $null

    $dW = New-Fixture 'write' '(W)'
    $r = Run-Fn $harnessText $dW
    Add-Result 'T2b2_users_write_only_throws' 'Users:(W) on file -> throws can-modify' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")

    $dRX = New-Fixture 'rx' '(RX)'
    $r = Run-Fn $harnessText $dRX
    Add-Result 'T2b3_users_rx_no_throw' 'Users:(RX) on file -> no throw' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")

    # Mutant A: put FileSystemRights.Modify back into the mask
    $needle = '[int64]0x40000000 -bor [int64]0x10000000 -bor'
    if (-not $harnessText.Contains($needle)) { throw 'mask needle not found' }
    $mutA = $harnessText.Replace($needle, '[int64][Security.AccessControl.FileSystemRights]::Modify -bor')
    $mutAreal = $fnText.Replace($needle, '[int64][Security.AccessControl.FileSystemRights]::Modify -bor')
    $r = Run-Fn $mutAreal 'C:\Python314'
    Add-Result 'T2c_mutant_modify_in_mask_python314_throws' 'mutant (Modify re-added): C:\Python314 now throws (positive test is sensitive)' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")
    $r = Run-Fn $mutA $dRX
    Add-Result 'T2c_mutant_modify_in_mask_rx_throws' 'mutant: Users:(RX) fixture wrongly throws (reproduces original defect)' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")

    # InheritOnly guard: empty dir with inherit-only Users Modify must not throw; mutant without guard must.
    $dIO = Join-Path $base 'inheritonly'
    New-Item -ItemType Directory -Path $dIO | Out-Null
    $o = & icacls $dIO /grant "${usersSid}:(OI)(CI)(IO)(M)" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "icacls failed: $o" }
    $r = Run-Fn $harnessText $dIO
    Add-Result 'T3_inheritonly_skipped' 'inherit-only Users:(M) on empty dir -> no throw' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")
    $guard = 'if ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) { continue }'
    $idx = $harnessText.IndexOf($guard)
    if ($idx -lt 0) { throw 'guard not found' }
    $mutB = $harnessText.Remove($idx, $guard.Length)
    $r = Run-Fn $mutB $dIO
    Add-Result 'T3_mutant_no_inheritonly_guard_throws' 'mutant without InheritOnly guard -> throws on same fixture' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")

    # --- Case 2b: S-1-15-2-1 (ALL APPLICATION PACKAGES) grants on a temp file ---
    function New-PkgFixture([string]$Name, [string]$Grant) {
        $d = Join-Path $base $Name
        New-Item -ItemType Directory -Path $d | Out-Null
        $f = Join-Path $d 'runtime.py'
        Set-Content -LiteralPath $f -Value 'x'
        $o = & icacls $f /grant "*S-1-15-2-1:$Grant" 2>&1
        if ($LASTEXITCODE -ne 0) { throw "icacls failed: $o" }
        return $d
    }
    $dPkgRX = New-PkgFixture 'pkgrx' '(RX)'
    $dPkgM = New-PkgFixture 'pkgm' '(M)'
    $pkgAces = (Get-Acl -LiteralPath (Join-Path $dPkgRX 'runtime.py')).GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]) | Where-Object { $_.IdentityReference.Value -eq 'S-1-15-2-1' }
    Add-Result 'T2b_pkg_fixture_has_ace' 'fixture really carries an S-1-15-2-1 ACE' (@($pkgAces).Count -ge 1) ("aceCount=$(@($pkgAces).Count) rights=$(@($pkgAces | ForEach-Object { $_.FileSystemRights }) -join ',')")
    $r = Run-Fn $harnessText $dPkgRX
    Add-Result 'T2b_pkg_rx_no_throw' 'S-1-15-2-1:(RX) on file -> no throw' (-not $r.threw) ("threw=$($r.threw) msg=$($r.msg)")
    $r = Run-Fn $harnessText $dPkgM
    Add-Result 'T2b_pkg_modify_throws' 'S-1-15-2-1:(M) on file -> throws can-modify' ($r.threw -and $r.msg -like '*can modify service runtime code*') ("threw=$($r.threw) msg=$($r.msg)")
    # Sensitivity: the translate-mutant of the harness variant must fail on the (RX) package fixture.
    $mutH = Make-TranslateMutant $harnessText $true
    $r = Run-Fn $mutH $dPkgRX
    Add-Result 'T2c_mutant_translate_pkg_rx_throws' 'mutant (old Translate): S-1-15-2-1:(RX) fixture throws Translate error' ($r.threw -and $r.msg -like '*could not be translated*') ("threw=$($r.threw) msg=$($r.msg)")
}
finally {
    Remove-Item -LiteralPath $base -Recurse -Force -ErrorAction SilentlyContinue
}
Add-Result 'T_cleanup' 'temp fixture dir removed' (-not (Test-Path -LiteralPath $base)) $base

$head = (& git -C $repo rev-parse HEAD).Trim()
$sha = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower()
$out = [ordered]@{
    task = 'S2-4E'; date = '2026-11-07'
    head = $head
    subject = 'uncommitted diff of tests/vst/provision_s2_4e_windows.ps1 (working-copy sha256 below)'
    working_copy_sha256 = $sha
    runtime = "powershell.exe $($PSVersionTable.PSVersion), non-elevated"
    command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File docs\sdlc\evidence\s2-4e-acl-mask-fix-test.ps1 -OutJson docs\sdlc\evidence\s2-4e-acl-mask-fix-20261107.json'
    harness_note = 'T2b/T3 use a copy of the function with ONE line changed: current user SID added to $trusted, so non-elevated file ownership and the user-owned %TEMP% ancestor chain do not mask the write-mask logic. T2a (Python314, Git trees) and the real-tree mutants use the unmodified function text; the real-tree mutants only swap the owner/rules/trustee lines back to the old Translate form.'
    not_run = @('raw GENERIC_WRITE/GENERIC_ALL unmapped ACE (cannot be created via icacls/Set-Acl without elevation)', 'installer itself', 'elevated run', 'S-1-15-2-2 (ALL RESTRICTED APPLICATION PACKAGES) covered only indirectly via the real Git trees, no dedicated fixture')
    results = $results
}
if ($OutJson) { ($out | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $OutJson -Encoding UTF8 }
$fails = @($results | Where-Object { $_.result -ne 'PASS' }).Count
Write-Host "TOTAL=$($results.Count) FAIL=$fails"
if ($fails -gt 0) { exit 1 }
