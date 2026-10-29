[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{40}$')]
    [string]$ExpectedHead,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Distribution,

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
if ($LASTEXITCODE -ne 0 -or $headOutput -cne $ExpectedHead) {
    throw "Canonical checkout HEAD does not equal requested revision $ExpectedHead."
}
$committedHostScript = & $git -C $repoRoot rev-parse --verify "${ExpectedHead}:tools/qa/install_wsl_runtime.ps1" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Host handoff script is not present at the requested committed revision.' }
$workingHostScript = & $git -C $repoRoot hash-object --path=tools/qa/install_wsl_runtime.ps1 -- tools/qa/install_wsl_runtime.ps1 2>&1
if ($LASTEXITCODE -ne 0 -or $workingHostScript -cne $committedHostScript) {
    throw 'Host handoff script differs from the requested committed revision.'
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
    'tools/qa/install_wsl_worker_helper.sh', 'tools/qa/worker_exec.c',
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
$transferId = [Guid]::NewGuid().ToString('N')

$bootstrap = @'
import atexit, configparser, hashlib, io, json, os, platform, re, stat, subprocess, sys, tarfile

head, expected_digest, transfer_id = sys.argv[1:4]
stage_only = sys.argv[4] == "1"
if (not re.fullmatch(r"[0-9a-f]{40}", head)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or not re.fullmatch(r"[0-9a-f]{32}", transfer_id)
        or sys.argv[4] not in ("0", "1")):
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
    # Stage-only is restricted to the reviewed unconfigured bootstrap host. This
    # preflight is observational; it does not create directories or change units.
    for path in ("/etc/vst-runner", "/run/vst-supervisor", "/run/vst-runner"):
        if os.path.lexists(path):
            raise SystemExit("stage-only requires absent runtime configuration/socket paths: " + path)
    units = (
        "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
        "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
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
payload = sys.stdin.buffer.read(maximum_archive + 1)
if not payload or len(payload) > maximum_archive:
    raise SystemExit("source bundle is empty or exceeds the 64 MiB limit")
digest = hashlib.sha256(payload).hexdigest()
if digest != expected_digest:
    raise SystemExit("source bundle digest does not match the host-provided digest")
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
    "tools/qa/worker_exec.c",
    "docs/SANDBOX_SPEC.md",
}
seen = set()
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
            if member.isreg():
                if member.size < 0:
                    raise SystemExit("source bundle contains a negative file size")
                total_size += member.size
                if total_size > maximum_archive:
                    raise SystemExit("expanded source bundle exceeds its size limit")
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
        archive.extractall(path=stage, filter="data")
except BaseException:
    # Keep the new root-private staging directory for diagnosis; never replace or delete state.
    raise

manifest_path = os.path.join(stage, ".vst-source-manifest.json")
fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
with os.fdopen(fd, "w", encoding="ascii") as stream:
    json.dump({"archive_sha256": digest, "head": head, "schema": 1}, stream, sort_keys=True, separators=(",", ":"))
    stream.flush()
    os.fsync(stream.fileno())

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
    if installed_manifest != {"archive_sha256": digest, "head": head, "schema": 1}:
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

worker = ["/bin/sh", os.path.join(stage, "tools/qa/install_wsl_worker_helper.sh"), head, stage, digest]
runtime = ["/bin/sh", os.path.join(stage, "tools/qa/install_wsl_runner_runtime.sh"), head, stage, digest]
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
    '-I', '-S', '-c', $bootstrap, $ExpectedHead, $archiveSha256, $transferId,
    $(if ($StageOnly.IsPresent) { '1' } else { '0' })
)) {
    [void]$wslStart.ArgumentList.Add($argument)
}

$wslProcess = New-Object System.Diagnostics.Process
$wslProcess.StartInfo = $wslStart
if (-not $wslProcess.Start()) { throw 'wsl.exe could not be started.' }
$stdoutTask = $wslProcess.StandardOutput.ReadToEndAsync()
$stderrTask = $wslProcess.StandardError.ReadToEndAsync()
$wslProcess.StandardInput.BaseStream.Write($archiveBytes, 0, $archiveBytes.Length)
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
Write-Output 'source_transfer=stdin; no Windows-drive mount or second checkout used'
if ($StageOnly.IsPresent) {
    Write-Output 'runtime_stage_only=true; selector_unchanged=true; systemd_units_installed=0'
}
