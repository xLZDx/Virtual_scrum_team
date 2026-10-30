[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedHead,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Distribution,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedPlanSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$ExpectedInventorySha256,

    [switch]$StageOnly
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$canonicalRoot = [System.IO.Path]::GetFullPath('D:\Repo\Virtual_scrum_team')
if (-not [string]::Equals($repoRoot, $canonicalRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Run this script from the canonical checkout at $canonicalRoot."
}

$git = (Get-Command git.exe -ErrorAction Stop).Source
$headOutput = & $git -C $repoRoot --no-replace-objects rev-parse --verify HEAD 2>&1
if ($LASTEXITCODE -ne 0) {
    throw 'Canonical checkout HEAD cannot be established.'
}
$ancestorCheck = & $git -C $repoRoot --no-replace-objects merge-base --is-ancestor $ExpectedHead $headOutput 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Requested source revision $ExpectedHead is not an ancestor of the checked-out revision."
}
$committedHostScript = & $git -C $repoRoot rev-parse --verify "${ExpectedHead}:tools/qa/install_wsl_runtime.ps1" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Host handoff script is not present at the requested committed revision.' }
$workingHostScript = & $git -C $repoRoot hash-object --path=tools/qa/install_wsl_runtime.ps1 -- tools/qa/install_wsl_runtime.ps1 2>&1
if ($LASTEXITCODE -ne 0 -or $workingHostScript -cne $committedHostScript) {
    throw 'Host handoff script differs from the requested committed revision.'
}
$planRelativePath = "docs/sdlc/evidence/s2-runtime-source-plan-$ExpectedHead.json"
$planPath = Join-Path $repoRoot $planRelativePath
if (-not (Test-Path -LiteralPath $planPath -PathType Leaf)) {
    throw "Exact reviewed source plan is missing: $planRelativePath"
}
$committedPlanBlob = & $git -C $repoRoot rev-parse --verify "HEAD:$planRelativePath" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Reviewed source plan is not committed in the current checkout.' }
$workingPlanBlob = & $git -C $repoRoot hash-object --no-filters -- $planPath 2>&1
if ($LASTEXITCODE -ne 0 -or $workingPlanBlob -cne $committedPlanBlob) {
    throw 'Working source plan differs from its committed Git blob.'
}
$planBytes = [System.IO.File]::ReadAllBytes($planPath)
$planSha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($planBytes)).ToLowerInvariant()
if ($planSha256 -cne $ExpectedPlanSha256) {
    throw "Source plan SHA-256 differs from the exact reviewed value $ExpectedPlanSha256."
}
$sourcePlan = [System.Text.Encoding]::UTF8.GetString($planBytes) | ConvertFrom-Json
if ($sourcePlan.schema -cne 'VST_S2_RUNTIME_SOURCE_PLAN_V2' -or
    $sourcePlan.status -cne 'UNSIGNED_REVIEW_CANDIDATE' -or
    $sourcePlan.source_head -cne $ExpectedHead -or
    $sourcePlan.archive_members -isnot [System.Management.Automation.PSCustomObject]) {
    throw 'Source plan schema, head, status, or exact member map is invalid.'
}
$inventoryRelativePath = [string]$sourcePlan.target_inventory.path
if ($sourcePlan.target_inventory -isnot [System.Management.Automation.PSCustomObject] -or
    $inventoryRelativePath -notmatch '^docs/sdlc/evidence/[A-Za-z0-9._-]+\.json$' -or
    $inventoryRelativePath -match '(^|/)\.\.?(/|$)' -or
    $sourcePlan.target_inventory.sha256 -notmatch '^[0-9a-f]{64}$' -or
    $sourcePlan.target_inventory.sha256 -cne $ExpectedInventorySha256) {
    throw 'Source plan target-inventory path or digest is invalid or differs from the reviewed value.'
}
$inventoryPath = Join-Path $repoRoot $inventoryRelativePath
if (-not (Test-Path -LiteralPath $inventoryPath -PathType Leaf)) {
    throw "Exact reviewed target inventory is missing: $inventoryRelativePath"
}
$committedInventoryBlob = & $git -C $repoRoot rev-parse --verify "HEAD:$inventoryRelativePath" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Reviewed target inventory is not committed in the current checkout.' }
$workingInventoryBlob = & $git -C $repoRoot hash-object --no-filters -- $inventoryPath 2>&1
if ($LASTEXITCODE -ne 0 -or $workingInventoryBlob -cne $committedInventoryBlob) {
    throw 'Working target inventory differs from its committed Git blob.'
}
$inventoryBytes = [System.IO.File]::ReadAllBytes($inventoryPath)
$inventorySha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($inventoryBytes)).ToLowerInvariant()
if ($inventorySha256 -cne $ExpectedInventorySha256) {
    throw "Target inventory SHA-256 differs from the exact reviewed value $ExpectedInventorySha256."
}
$targetInventory = [System.Text.Encoding]::UTF8.GetString($inventoryBytes) | ConvertFrom-Json
if ([string]$targetInventory.observed_utc -cne [string]$sourcePlan.target_inventory.observed_utc) {
    throw 'Target inventory capture time differs from the source plan binding.'
}
try {
    $inventoryObserved = [DateTimeOffset]::Parse(
        [string]$targetInventory.observed_utc,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [System.Globalization.DateTimeStyles]::None
    ).ToUniversalTime()
} catch {
    throw 'Target inventory observation time is invalid.'
}
$inventoryAgeSeconds = ([DateTimeOffset]::UtcNow - $inventoryObserved).TotalSeconds
if ($targetInventory.source_head -cne $ExpectedHead -or
    $inventoryAgeSeconds -lt -30 -or $inventoryAgeSeconds -gt 300 -or
    $targetInventory.compiler.sha256 -notmatch '^[0-9a-f]{64}$' -or
    $targetInventory.compiler.uid -ne 0 -or $targetInventory.compiler.gid -ne 0 -or
    $targetInventory.compiler.mode -cne '0755' -or
    $targetInventory.compiler.path -cne '/usr/bin/cc' -or
    $targetInventory.compiler.symlink_target -cne '/etc/alternatives/cc' -or
    $targetInventory.compiler.resolved_path -notmatch '^/usr/bin/[A-Za-z0-9._+-]+$') {
    throw 'Target inventory source revision, age, or compiler identity is invalid.'
}

function Read-BoundedProcessOutput {
    param([System.Diagnostics.Process]$Process, [int]$MaximumBytes)
    $buffer = New-Object byte[] 65536
    $memory = New-Object System.IO.MemoryStream
    while (($count = $Process.StandardOutput.BaseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
        if (($memory.Length + $count) -gt $MaximumBytes) {
            try { $Process.Kill() } catch { }
            throw "Source archive exceeds the $MaximumBytes-byte transfer limit."
        }
        $memory.Write($buffer, 0, $count)
    }
    return ,$memory.ToArray()
}

$archiveStart = New-Object System.Diagnostics.ProcessStartInfo
$archiveStart.FileName = $git
$archiveStart.UseShellExecute = $false
$archiveStart.RedirectStandardOutput = $true
$archiveStart.RedirectStandardError = $true
foreach ($argument in @(
    # Do not apply the caller's Windows checkout conversion to POSIX source
    # blobs embedded in the WSL deployment archive.
    '-c', 'core.autocrlf=false', '-c', 'core.eol=lf',
    '-C', $repoRoot, '--no-replace-objects', 'archive', '--format=tar',
    $ExpectedHead, '--', 'tools/vst', 'tools/qa/install_wsl_runner_runtime.sh',
    'tools/qa/install_wsl_worker_helper.sh', 'tools/qa/verify_wsl_source_bundle.py',
    'tools/qa/verify_wsl_runtime_stage.py',
    'tools/qa/worker_exec.c',
    'docs/SANDBOX_SPEC.md'
)) {
    [void]$archiveStart.ArgumentList.Add($argument)
}

$archiveProcess = New-Object System.Diagnostics.Process
$archiveProcess.StartInfo = $archiveStart
if (-not $archiveProcess.Start()) { throw 'git archive could not be started.' }
$archiveErrorTask = $archiveProcess.StandardError.ReadToEndAsync()
$archiveBytes = Read-BoundedProcessOutput -Process $archiveProcess -MaximumBytes (64 * 1024 * 1024)
$archiveProcess.WaitForExit()
$archiveError = $archiveErrorTask.GetAwaiter().GetResult()
if ($archiveProcess.ExitCode -ne 0) {
    throw "git archive failed with exit code $($archiveProcess.ExitCode): $archiveError"
}
if ($archiveBytes.Length -eq 0) { throw 'git archive returned an empty source bundle.' }
$archiveSha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($archiveBytes)).ToLowerInvariant()
if ($archiveSha256 -cne $sourcePlan.archive_sha256) {
    throw 'Exact committed Git archive differs from the GPT-PM-reviewed source plan.'
}
$envelopeHeader = [System.Text.Encoding]::ASCII.GetBytes("VST-S2-BUNDLE-V3`n$($planBytes.Length)`n$($inventoryBytes.Length)`n")
$envelopeStream = New-Object System.IO.MemoryStream
$envelopeStream.Write($envelopeHeader, 0, $envelopeHeader.Length)
$envelopeStream.Write($planBytes, 0, $planBytes.Length)
$envelopeStream.Write($inventoryBytes, 0, $inventoryBytes.Length)
$envelopeStream.Write($archiveBytes, 0, $archiveBytes.Length)
$transferBytes = $envelopeStream.ToArray()
$envelopeStream.Dispose()
$transferId = [Guid]::NewGuid().ToString('N')

$bootstrap = @'
import atexit, configparser, hashlib, io, json, os, platform, re, stat, subprocess, sys, tarfile
from datetime import datetime, timezone

head, expected_plan_sha256, expected_inventory_sha256, transfer_id = sys.argv[1:5]
stage_only = sys.argv[5] == "1"
if (not re.fullmatch(r"[0-9a-f]{40}", head)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_plan_sha256)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_inventory_sha256)
        or not re.fullmatch(r"[0-9a-f]{32}", transfer_id)
        or sys.argv[5] not in ("0", "1")):
    raise SystemExit("invalid source revision or archive digest")
if os.geteuid() != 0 or platform.system() != "Linux":
    raise SystemExit("WSL runtime installer requires root on Linux")
release = {}
with open("/etc/os-release", encoding="ascii") as stream:
    for line in stream:
        key, sep, value = line.rstrip("\n").partition("=")
        if sep:
            release[key] = value.strip('"')
if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
    raise SystemExit("runtime installer requires Ubuntu 24.04")
with open("/proc/sys/kernel/osrelease", encoding="ascii") as stream:
    if "microsoft" not in stream.read().lower():
        raise SystemExit("runtime installer requires WSL")
settings = configparser.ConfigParser()
settings.read("/etc/wsl.conf")
if (settings.getboolean("automount", "enabled", fallback=True)
        or settings.getboolean("interop", "enabled", fallback=True)
        or settings.getboolean("interop", "appendWindowsPath", fallback=True)):
    raise SystemExit("Windows drive automount and interop must be disabled")
with open("/proc/self/mountinfo", encoding="ascii") as stream:
    for line in stream:
        fields = line.rstrip("\n").split(" - ", 1)
        if len(fields) != 2:
            raise SystemExit("cannot parse the complete WSL mount inventory")
        mount = fields[1].split()
        if len(mount) < 3:
            raise SystemExit("cannot parse a WSL mount entry")
        fs_type, source, super_options = mount[:3]
        drive_source = bool(re.match(r"^[A-Za-z]:[\\/]?$", source))
        if fs_type == "drvfs" or (fs_type == "9p" and (drive_source or "aname=drvfs" in super_options)):
            raise SystemExit("Windows-drive mount is visible; refusing source deployment")

if stage_only:
    # This early check is observational. The existing configuration directory is
    # validated from the exact source bundle before any helper/runtime is published.
    for path in ("/run/vst-supervisor", "/run/vst-runner"):
        if os.path.lexists(path):
            raise SystemExit("stage-only requires absent runtime socket paths: " + path)
    units = (
        "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
        "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
        "vst-dispatcher.service", "vst-runner.service",
        "vst-sandbox-probe.service", "vst-signer.service", "vst-supervisor.service",
    )
    for unit in units:
        load_state = subprocess.run(
            ["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, text=True,
        )
        active_state = subprocess.run(
            ["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", unit],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, text=True,
        )
        if (load_state.returncode == 0 and load_state.stdout.strip() == "not-found"
                and active_state.returncode in (0, 1)
                and active_state.stdout.strip() in ("", "inactive")):
            continue
        if (load_state.returncode != 0 or load_state.stdout.strip() != "loaded"
                or active_state.returncode != 0 or active_state.stdout.strip() != "inactive"):
            raise SystemExit("stage-only requires each S2 unit to be loaded-inactive or not-found: " + unit)
    jobs = subprocess.run(
        ["/usr/bin/systemctl", "list-jobs", "--no-legend", "--plain"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, text=True,
    )
    if jobs.returncode != 0:
        raise SystemExit("cannot establish systemd job inventory")
    affected = set(units)
    for line in jobs.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or not fields[0].isdigit():
            raise SystemExit("cannot parse complete systemd job inventory")
        if fields[1] in affected:
            raise SystemExit("stage-only requires no systemd job for S2 unit: " + fields[1])
    for unit in units:
        control_group = subprocess.run(
            ["/usr/bin/systemctl", "show", "--property=ControlGroup", "--value", unit],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, text=True,
        )
        if control_group.returncode == 1 and not control_group.stdout.strip():
            continue  # not loaded: no unit cgroup exists
        if control_group.returncode != 0:
            raise SystemExit("cannot establish S2 unit cgroup: " + unit)
        relative = control_group.stdout.strip().lstrip("/")
        if not relative:
            continue
        cgroup = os.path.join("/sys/fs/cgroup", relative)
        if not os.path.isdir(cgroup):
            raise SystemExit("cannot inspect S2 unit cgroup: " + unit)
        for current, directories, _files in os.walk(cgroup, followlinks=False):
            if os.path.islink(current):
                raise SystemExit("S2 cgroup inventory contains a symlink")
            try:
                with open(os.path.join(current, "cgroup.events"), encoding="ascii") as stream:
                    events = dict(line.split() for line in stream if line.strip())
            except (OSError, ValueError) as exc:
                raise SystemExit("cannot read S2 cgroup population state: " + unit) from exc
            if events.get("populated") != "0":
                raise SystemExit("stage-only requires empty S2 service cgroups: " + unit)
            for directory in directories:
                if os.path.islink(os.path.join(current, directory)):
                    raise SystemExit("S2 cgroup inventory contains a symlink")

maximum_archive = 64 * 1024 * 1024
maximum_plan = 8 * 1024 * 1024
maximum_inventory = 8 * 1024 * 1024
maximum_envelope = maximum_archive + maximum_plan + maximum_inventory + 160
envelope = sys.stdin.buffer.read(maximum_envelope + 1)
if not envelope or len(envelope) > maximum_envelope:
    raise SystemExit("source bundle envelope is empty or exceeds its size limit")
prefix = b"VST-S2-BUNDLE-V3\n"
if not envelope.startswith(prefix):
    raise SystemExit("source bundle envelope header is invalid")
lengths = []
offset = len(prefix)
for label, maximum in (("source plan", maximum_plan), ("target inventory", maximum_inventory)):
    length_end = envelope.find(b"\n", offset)
    if length_end < 0 or length_end - offset > 10:
        raise SystemExit(label + " length header is invalid")
    length_text = envelope[offset:length_end]
    if not length_text.isdigit() or (len(length_text) > 1 and length_text.startswith(b"0")):
        raise SystemExit(label + " length header is noncanonical")
    length = int(length_text)
    if not 0 < length <= maximum:
        raise SystemExit(label + " length exceeds its bound")
    lengths.append(length)
    offset = length_end + 1
plan_length, inventory_length = lengths
plan_end = offset + plan_length
inventory_end = plan_end + inventory_length
if inventory_end > len(envelope):
    raise SystemExit("source plan or target inventory is truncated")
plan_bytes = envelope[offset:plan_end]
inventory_bytes = envelope[plan_end:inventory_end]
payload = envelope[inventory_end:]
if not payload or len(payload) > maximum_archive:
    raise SystemExit("source archive is empty or exceeds the 64 MiB limit")
if hashlib.sha256(plan_bytes).hexdigest() != expected_plan_sha256:
    raise SystemExit("source plan differs from the exact reviewed SHA-256")
def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise SystemExit("source plan contains duplicate JSON fields")
        result[key] = value
    return result
try:
    source_plan = json.loads(plan_bytes, object_pairs_hook=unique_pairs,
                             parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
    raise SystemExit("source plan is not valid finite UTF-8 JSON") from exc
if (not isinstance(source_plan, dict)
        or source_plan.get("schema") != "VST_S2_RUNTIME_SOURCE_PLAN_V2"
        or source_plan.get("status") != "UNSIGNED_REVIEW_CANDIDATE"
        or source_plan.get("source_head") != head):
    raise SystemExit("source plan schema or revision differs from the request")
if hashlib.sha256(inventory_bytes).hexdigest() != expected_inventory_sha256:
    raise SystemExit("target inventory differs from the exact reviewed SHA-256")
try:
    target_inventory = json.loads(inventory_bytes, object_pairs_hook=unique_pairs,
                                  parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite JSON")))
except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
    raise SystemExit("target inventory is not valid finite UTF-8 JSON") from exc
compiler = target_inventory.get("compiler") if isinstance(target_inventory, dict) else None
try:
    observed = datetime.fromisoformat(target_inventory["observed_utc"].replace("Z", "+00:00"))
    if observed.tzinfo is None:
        raise ValueError("inventory timestamp must include a timezone")
    inventory_age = (datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
except (KeyError, TypeError, ValueError) as exc:
    raise SystemExit("target inventory timestamp is invalid") from exc
if (not isinstance(compiler, dict) or target_inventory.get("source_head") != head
        or inventory_age < -30 or inventory_age > 300
        or compiler.get("path") != "/usr/bin/cc"
        or not isinstance(compiler.get("resolved_path"), str)
        or not re.fullmatch(r"/usr/bin/[A-Za-z0-9._+-]+", compiler["resolved_path"])
        or compiler.get("uid") != 0 or compiler.get("gid") != 0
        or compiler.get("mode") != "0755"
        or compiler.get("symlink_target") != "/etc/alternatives/cc"
        or not isinstance(compiler.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", compiler["sha256"])):
    raise SystemExit("target inventory compiler identity is invalid or not source-bound")
compiler_sha256 = compiler["sha256"]
compiler_resolved_path = compiler["resolved_path"]
compiler_symlink_target = compiler["symlink_target"]
digest = source_plan.get("archive_sha256")
if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
    raise SystemExit("source plan archive digest is invalid")
if hashlib.sha256(payload).hexdigest() != digest:
    raise SystemExit("source archive differs from the exact reviewed source plan")
expected_members = source_plan.get("archive_members")
if not isinstance(expected_members, dict) or not 0 < len(expected_members) <= 50000:
    raise SystemExit("source plan has no bounded archive member map")
for name, entry in expected_members.items():
    if (not isinstance(name, str) or not name or name.startswith("/") or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))
            or not isinstance(entry, dict)):
        raise SystemExit("source plan contains an unsafe member path or record")
    if entry == {"kind": "dir"}:
        continue
    if (set(entry) != {"kind", "sha256", "size"} or entry.get("kind") != "file"
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
            or type(entry.get("size")) is not int or entry["size"] < 0):
        raise SystemExit("source plan contains an invalid file record")
stage = "/run/vst-deploy-" + head + "-" + transfer_id
if os.path.lexists(stage):
    raise SystemExit("refusing an existing distro-local source bundle path")
stage_owned = False
deployment_complete = False
def report_retained_stage():
    if stage_owned and not deployment_complete:
        print("source bundle retained at " + stage + "; preserve it, do not delete host state; retry uses a fresh transfer ID", file=sys.stderr)
atexit.register(report_retained_stage)
os.mkdir(stage, 0o700)
stage_owned = True

allowed_files = {
    "tools/qa/install_wsl_runner_runtime.sh",
    "tools/qa/install_wsl_worker_helper.sh",
    "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py",
    "tools/qa/worker_exec.c",
    "docs/SANDBOX_SPEC.md",
}
seen = set()
actual_members = {}
try:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        members = archive.getmembers()
        if len(members) > 50000:
            raise SystemExit("source bundle contains too many archive entries")
        total_size = 0
        for member in members:
            name = member.name.rstrip("/")
            if (not name or name.startswith("/") or "\\" in name
                    or any(part in ("", ".", "..") for part in name.split("/"))):
                raise SystemExit("source bundle contains an unsafe member path")
            if name in seen:
                raise SystemExit("source bundle contains a duplicate member")
            seen.add(name)
            if not (name in ("tools", "tools/vst", "tools/qa", "docs")
                    or name.startswith("tools/vst/") or name in allowed_files):
                raise SystemExit("source bundle contains a path outside the S2 runtime allowlist")
            if not (member.isdir() or member.isreg()):
                raise SystemExit("source bundle contains a special file")
            if member.isdir():
                actual_members[name] = {"kind": "dir"}
            else:
                if member.size < 0:
                    raise SystemExit("source bundle contains a negative file size")
                total_size += member.size
                if total_size > maximum_archive:
                    raise SystemExit("expanded source bundle exceeds its size limit")
                content = archive.extractfile(member)
                if content is None:
                    raise SystemExit("source bundle member cannot be read")
                data = content.read(member.size + 1)
                if len(data) != member.size:
                    raise SystemExit("source bundle member size changed or was truncated")
                actual_members[name] = {
                    "kind": "file", "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                }
            if expected_members.get(name) != actual_members[name]:
                raise SystemExit("source bundle member differs from reviewed manifest: " + name)
        required = allowed_files | {
            "tools/vst/runner.py", "tools/vst/signer.py", "tools/vst/store.py",
            "tools/vst/supervisor.py", "tools/vst/runner_service.py",
            "tools/vst/supervisor_service.py", "tools/vst/execution_grant.py",
            "tools/vst/runner_fence.py", "tools/vst/dispatcher_service.py",
            "tools/vst/dispatch_instruction.py", "tools/vst/dispatch_owner_client.py",
            "tools/vst/dispatch_owner_service.py",
            "tools/vst/dispatch_owner_latch.py",
            "tools/vst/systemd/vst-runner.service", "tools/vst/systemd/vst-signer.service",
            "tools/vst/systemd/vst-supervisor.service", "tools/vst/systemd/vst-dispatcher.service",
            "tools/vst/systemd/vst-dispatch-owner.service",
            "tools/vst/systemd/vst-dispatch-owner.socket",
            "docs/SANDBOX_SPEC.md",
        }
        if not required.issubset(seen):
            raise SystemExit("source bundle is missing a required S2 runtime file")
        if seen != set(expected_members):
            missing = sorted(set(expected_members) - seen)
            extra = sorted(seen - set(expected_members))
            raise SystemExit("source bundle member set differs (missing=%r extra=%r)" %
                             (missing[:5], extra[:5]))
        archive.extractall(path=stage, filter="data")
except BaseException:
    # Keep the new root-private staging directory for diagnosis; never replace or delete state.
    raise

manifest_path = os.path.join(stage, ".vst-source-manifest.json")
fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
with os.fdopen(fd, "w", encoding="ascii") as stream:
    json.dump({"archive_members": expected_members, "archive_sha256": digest,
               "compiler_path": "/usr/bin/cc", "compiler_resolved_path": compiler_resolved_path,
               "compiler_sha256": compiler_sha256, "compiler_symlink_target": compiler_symlink_target,
               "head": head,
               "inventory_sha256": expected_inventory_sha256,
               "plan_sha256": expected_plan_sha256, "schema": 3},
              stream, sort_keys=True, separators=(",", ":"))
    stream.flush()
    os.fsync(stream.fileno())
os.chmod(manifest_path, 0o600)
verified = subprocess.run(
    ["/usr/bin/python3.12", "-I", "-S", os.path.join(stage, "tools/qa/verify_wsl_source_bundle.py"),
     "--root", stage, "--expected-head", head, "--archive-sha256", digest,
     "--plan-sha256", expected_plan_sha256,
     "--inventory-sha256", expected_inventory_sha256],
    stdin=subprocess.DEVNULL, check=False,
)
if verified.returncode != 0:
    raise SystemExit("extracted source bundle failed exact member-map verification")

def require_root_file(path, expected, expected_mode=0o644):
    if not os.path.lexists(path):
        return
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != expected_mode:
        raise SystemExit("existing fixed destination has an unexpected type, owner, or mode: " + path)
    with open(path, "rb") as stream:
        if stream.read(len(expected) + 1) != expected:
            raise SystemExit("existing fixed destination differs from the requested source: " + path)

def source_tree(root, installed=False):
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode):
        raise SystemExit("runtime tree root is not a directory: " + root)
    if installed and (root_info.st_uid != 0 or stat.S_IMODE(root_info.st_mode) != 0o755):
        raise SystemExit("installed runtime tree root has unexpected owner/mode: " + root)
    result = {}
    for current, directories, files in os.walk(root, followlinks=False):
        directories.sort()
        files.sort()
        for name in directories + files:
            path = os.path.join(current, name)
            info = os.lstat(path)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if stat.S_ISDIR(info.st_mode):
                if installed and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o755):
                    raise SystemExit("installed runtime directory has unexpected owner/mode: " + path)
                result[relative] = ("dir", None)
            elif stat.S_ISREG(info.st_mode):
                if installed and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o644):
                    raise SystemExit("installed runtime file has unexpected owner/mode: " + path)
                with open(path, "rb") as stream:
                    result[relative] = ("file", hashlib.sha256(stream.read()).hexdigest())
            else:
                raise SystemExit("runtime package contains a non-regular object: " + path)
    return result

runtime_dir = "/opt/vst-runtime-" + head
runtime_link = "/opt/vst-runtime"
unit_dir = "/etc/systemd/system"
source_units = os.path.join(stage, "tools/vst/systemd")
if os.path.lexists(runtime_dir):
    info = os.lstat(runtime_dir)
    marker = os.path.join(runtime_dir, ".vst-runtime-manifest.json")
    marker_info = os.lstat(marker) if os.path.lexists(marker) else None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o755
            or marker_info is None or not stat.S_ISREG(marker_info.st_mode)
            or marker_info.st_uid != 0 or stat.S_IMODE(marker_info.st_mode) != 0o644):
        raise SystemExit("existing runtime path is not an exact prior deployment; no state changed")
    with open(marker, "r", encoding="ascii") as stream:
        installed_manifest = json.load(stream)
    expected_runtime_marker = {
        "archive_sha256": digest,
        "compiler_path": "/usr/bin/cc",
        "compiler_resolved_path": compiler_resolved_path,
        "compiler_sha256": compiler_sha256,
        "compiler_symlink_target": compiler_symlink_target,
        "head": head, "inventory_sha256": expected_inventory_sha256,
        "plan_sha256": expected_plan_sha256, "schema": 3,
    }
    if installed_manifest != expected_runtime_marker:
        raise SystemExit("existing runtime manifest differs from requested head/digest; no state changed")
    if sorted(os.listdir(runtime_dir)) != [".vst-runtime-manifest.json", "docs", "tools"]:
        raise SystemExit("existing runtime has unexpected entries; no state changed")
    expected_tree = source_tree(os.path.join(stage, "tools/vst"))
    installed_tree = source_tree(os.path.join(runtime_dir, "tools/vst"), installed=True)
    if expected_tree != installed_tree:
        raise SystemExit("existing runtime source differs from requested archive; no state changed")
    expected_docs = source_tree(os.path.join(stage, "docs"))
    installed_docs = source_tree(os.path.join(runtime_dir, "docs"), installed=True)
    if expected_docs != installed_docs:
        raise SystemExit("existing runtime specification differs from requested archive; no state changed")
if not stage_only:
    if os.path.lexists(runtime_link):
        link_info = os.lstat(runtime_link)
        if (not stat.S_ISLNK(link_info.st_mode) or link_info.st_uid != 0
                or os.readlink(runtime_link) != runtime_dir):
            raise SystemExit("existing runtime selector differs from the requested deployment; no state changed")
    for unit in ("vst-supervisor.service", "vst-signer.service", "vst-runner.service",
                 "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket"):
        with open(os.path.join(source_units, unit), "rb") as stream:
            require_root_file(os.path.join(unit_dir, unit), stream.read())
helper_path = "/usr/local/libexec/vst-s4-worker-exec-" + head
for directory in ("/opt", unit_dir, "/usr/local/libexec"):
    info = os.lstat(directory)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) & 0o022):
        raise SystemExit("fixed installation parent has an unsafe owner/mode: " + directory)
if os.path.lexists(helper_path):
    info = os.lstat(helper_path)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 988
            or stat.S_IMODE(info.st_mode) != 0o4750 or info.st_nlink != 1):
        raise SystemExit("existing exact-version worker helper has unexpected identity; no state changed")

if stage_only:
    sys.path.insert(0, stage)
    from tools.vst.runtime_bundle import validate_root_config_directory
    validate_root_config_directory("/etc/vst-runner")

worker = ["/bin/sh", os.path.join(stage, "tools/qa/install_wsl_worker_helper.sh"),
          head, stage, digest, expected_plan_sha256, expected_inventory_sha256]
runtime = ["/bin/sh", os.path.join(stage, "tools/qa/install_wsl_runner_runtime.sh"),
           head, stage, digest, expected_plan_sha256, expected_inventory_sha256]
if stage_only:
    runtime.append("--stage-only")
for command in (worker, runtime):
    completed = subprocess.run(command, stdin=subprocess.DEVNULL, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
deployment_complete = True
print("source_bundle_path=" + stage)
'@

$wsl = (Get-Command wsl.exe -ErrorAction Stop).Source
$wslStart = New-Object System.Diagnostics.ProcessStartInfo
$wslStart.FileName = $wsl
$wslStart.UseShellExecute = $false
$wslStart.RedirectStandardInput = $true
$wslStart.RedirectStandardOutput = $true
$wslStart.RedirectStandardError = $true
foreach ($argument in @(
    '--distribution', $Distribution, '--user', 'root', '--exec', '/usr/bin/python3.12',
    '-I', '-B', '-S', '-c', $bootstrap, $ExpectedHead, $ExpectedPlanSha256,
    $ExpectedInventorySha256, $transferId,
    $(if ($StageOnly.IsPresent) { '1' } else { '0' })
)) {
    [void]$wslStart.ArgumentList.Add($argument)
}

$wslProcess = New-Object System.Diagnostics.Process
$wslProcess.StartInfo = $wslStart
if (-not $wslProcess.Start()) { throw 'wsl.exe could not be started.' }
$stdoutTask = $wslProcess.StandardOutput.ReadToEndAsync()
$stderrTask = $wslProcess.StandardError.ReadToEndAsync()
$wslProcess.StandardInput.BaseStream.Write($transferBytes, 0, $transferBytes.Length)
$wslProcess.StandardInput.Close()
$wslProcess.WaitForExit()
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()
if ($stdout) { Write-Output $stdout.TrimEnd() }
if ($wslProcess.ExitCode -ne 0) {
    throw "WSL source deployment failed with exit code $($wslProcess.ExitCode): $stderr. No pre-existing destination was removed or overwritten; rerun with the same head for exact artifacts, and preserve mismatched paths for read-only inspection."
}
if ($stderr) { Write-Warning $stderr.TrimEnd() }
Write-Output "source_head=$ExpectedHead"
Write-Output "source_archive_sha256=$archiveSha256"
Write-Output "source_plan_sha256=$ExpectedPlanSha256"
Write-Output "target_inventory_sha256=$ExpectedInventorySha256"
Write-Output 'source_transfer=stdin; no Windows-drive mount or second checkout used'
if ($StageOnly.IsPresent) {
    Write-Output 'runtime_stage_only=true; selector_unchanged=true; systemd_units_installed=0'
}
