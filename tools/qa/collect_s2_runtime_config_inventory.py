"""Collect one exact, read-only S2 runtime inventory from the authorized WSL target."""
import datetime, hashlib, json, os, stat, subprocess, sys

REPO = "/mnt/d/Repo/Virtual_scrum_team"
RUN_ID = "s2-runtime-20261030-dd4c04c50f4e42d990ac9eeb9a23bc2e"
REQUEST_ID = "ba3faaadb50447b79df509619b6ee010"
NONCE = "1fd3cb4e69e54bc6aa5e63458ae82818"
RUNTIME = "/opt/vst-runtime-ee69f9fbf074a4c73d2d5d1da81c627a57d06071"
CAPTURE_SHA = "befd58be96af1823e0fd9b9f0a75217819bf099b674fc61d590ffaf693008119"
APPLIER_SHA = "d5230e7f247a374c4ce3050824de8fe988e51b5be320f6e0e6ffb2c89f6bee53"
VALIDATOR_SHA = "548058437dba2059f6efc67e4de1a21f9f1bec52d9af0d14211996d03eef97d2"
BUNDLE_SHA = "d03306788fc4e5090527483dc0412f055822d738ce13a08e11245afe2e9368e4"
LAYOUT_SHA = "b34b5dfb9d43c10e24294dc9e89bf890ed6e303a9f9c5cd5e7dec560f727e9b2"
IMPLEMENTATION_HEAD = "16549bb8f10113b2f05f41b3aa390bad80dab97e"
UNITS = [
    "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
    "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
    "vst-dispatcher.service", "vst-runner.service", "vst-sandbox-probe.service",
    "vst-signer.service", "vst-supervisor.service",
]
CONTAINER_SOCKETS = [
    "/run/containerd/containerd.sock", "/run/docker.sock",
    "/run/podman/podman.sock", "/var/run/docker.sock",
]

def complete_readiness(readiness, units, runtime_selector, *, store_present,
                       container_sockets,
                       installed_bootstrap_identity, candidate_identity_collision):
    """Assemble every validator readiness field from one target capture."""
    if not isinstance(units, dict) or set(units) != set(UNITS):
        raise ValueError("systemd observation set does not match the exact nine-unit contract")
    if not isinstance(runtime_selector, dict):
        raise ValueError("runtime selector observation is missing")
    if any(type(value) is not bool for value in
           (store_present, candidate_identity_collision)):
        raise ValueError("runtime state observations must be booleans")
    if (not isinstance(container_sockets, dict)
            or set(container_sockets) != set(CONTAINER_SOCKETS)
            or any(type(value) is not bool for value in container_sockets.values())):
        raise ValueError("container socket observation set is incomplete or malformed")
    if (not isinstance(installed_bootstrap_identity, dict)
            or set(installed_bootstrap_identity) != {"request_id", "run_id"}
            or any(not isinstance(value, str) or not value.strip()
                   for value in installed_bootstrap_identity.values())):
        raise ValueError("installed bootstrap identity observation is incomplete")
    selector = runtime_selector.get("link_target", "")
    if runtime_selector.get("kind") != "symlink" or runtime_selector.get("state") != "PRESENT":
        selector = ""
    result = dict(readiness)
    result["units"] = units
    result["runtime_selector"] = selector
    result.update({
        "store_present": store_present,
        "container_sockets": container_sockets,
        "candidate_identity_collision": candidate_identity_collision,
        "installed_bootstrap_identity": installed_bootstrap_identity,
    })
    return result


def assemble_inventory(fields, readiness, units, runtime_selector, *, store_present,
                       container_sockets,
                       installed_bootstrap_identity, candidate_identity_collision):
    """Build the persisted inventory and its readiness duplicate from one capture."""
    complete = complete_readiness(
        readiness, units, runtime_selector,
        store_present=store_present,
        container_sockets=container_sockets,
        installed_bootstrap_identity=installed_bootstrap_identity,
        candidate_identity_collision=candidate_identity_collision,
    )
    inventory = dict(fields)
    inventory.update({
        "readiness": complete,
        "runtime_selector": runtime_selector,
        "store_present": store_present,
        "container_sockets": container_sockets,
        "installed_bootstrap_identity": installed_bootstrap_identity,
        "candidate_identity_collision": candidate_identity_collision,
    })
    return inventory

def sanitized_git_environment(environment):
    """Remove Git environment overrides so -C always resolves this checkout."""
    return {key: value for key, value in environment.items()
            if not key.upper().startswith("GIT_")}

def require_success(result, label, accepted_codes=(0,), expected_stderr=""):
    if (not isinstance(result, dict)
            or type(result.get("exit_code")) is not int
            or result["exit_code"] not in accepted_codes
            or result.get("stderr") != expected_stderr):
        raise RuntimeError(label + " command failed or produced unexpected stderr")
    return result

def parse_os_release(text):
    fields = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "VERSION_ID"}:
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
            fields[key] = value
    if fields.get("ID") != "ubuntu" or fields.get("VERSION_ID") != "24.04":
        raise RuntimeError("observed OS release is not Ubuntu 24.04")
    return "Ubuntu-" + fields["VERSION_ID"]

def parse_unit_observation(result, unit, systemd_jobs):
    require_success(result, "systemd unit " + unit)
    required = {"LoadState", "ActiveState", "SubState", "Job"}
    fields = {}
    for line in result["stdout"].splitlines():
        if "=" not in line:
            raise RuntimeError("systemd unit output is malformed: " + unit)
        key, value = line.split("=", 1)
        if key not in required or key in fields:
            raise RuntimeError("systemd unit output has unexpected or duplicate fields: " + unit)
        fields[key] = value
    if set(fields) != required:
        raise RuntimeError("systemd unit output is incomplete: " + unit)
    if fields["Job"] == "" and not systemd_jobs.strip():
        fields["Job"] = "0"
    return [fields[key] for key in ("LoadState", "ActiveState", "SubState", "Job")]

def account_from_observation(result, name):
    output = result.get("stdout", "") if isinstance(result, dict) else ""
    if isinstance(result, dict):
        result["stdout"] = "[redacted after UID/GID extraction]"
    require_success(result, "getent " + name)
    fields = output.strip().split(":")
    if len(fields) < 4 or fields[0] != name:
        raise RuntimeError("getent returned a malformed account record: " + name)
    try:
        uid, gid = int(fields[2]), int(fields[3])
    except ValueError as exc:
        raise RuntimeError("getent returned a malformed UID/GID: " + name) from exc
    return {"uid": uid, "gid": gid}

def shutdown_is_scheduled(result):
    if (isinstance(result, dict) and result.get("exit_code") == 1
            and not result.get("stdout", "").strip()
            and result.get("stderr", "").strip() == "No scheduled shutdown."):
        return False
    if (isinstance(result, dict) and result.get("exit_code") == 0
            and not result.get("stderr", "")
            and result.get("stdout", "").strip().startswith("Shutdown scheduled for ")):
        return True
    raise RuntimeError("shutdown schedule command returned an unknown result")

def candidate_identity_collision(store_present, bootstrap):
    if type(store_present) is not bool:
        raise ValueError("Store presence observation is missing")
    keys = {"request_id", "run_id"}
    if (not isinstance(bootstrap, dict) or set(bootstrap) != keys
            or any(not isinstance(bootstrap[key], str) or not bootstrap[key].strip() for key in keys)):
        raise ValueError("bootstrap identity observation is incomplete")
    return bool(
        store_present
        or bootstrap["run_id"] == RUN_ID
        or bootstrap["request_id"] == REQUEST_ID
    )

observations = []
def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")
def run(label, argv, cwd=None, timeout=20):
    started = utc()
    try:
        p = subprocess.run(argv, cwd=cwd, env=sanitized_git_environment(os.environ),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           check=False)
        result = {"label": label, "command": argv, "cwd": cwd, "started_utc": started,
                  "finished_utc": utc(), "exit_code": p.returncode,
                  "stdout": p.stdout, "stderr": p.stderr}
    except Exception as exc:
        result = {"label": label, "command": argv, "cwd": cwd, "started_utc": started,
                  "finished_utc": utc(), "exit_code": 127, "stdout": "",
                  "stderr": type(exc).__name__ + ": " + str(exc)}
    observations.append(result)
    return result
def internal(label, command, fn):
    started = utc()
    try:
        value = fn()
        result = {"label": label, "command": command, "started_utc": started,
                  "finished_utc": utc(), "exit_code": 0,
                  "stdout": json.dumps(value, sort_keys=True, separators=(",", ":")),
                  "stderr": ""}
        observations.append(result)
        return value
    except Exception as exc:
        result = {"label": label, "command": command, "started_utc": started,
                  "finished_utc": utc(), "exit_code": 1, "stdout": "",
                  "stderr": type(exc).__name__ + ": " + str(exc)}
        observations.append(result)
        return {"error": result["stderr"]}
def parse_field(text, name):
    for line in text.splitlines():
        if line.startswith(name + ":"):
            return [int(x) for x in line.split(":", 1)[1].split()]
    raise ValueError("missing " + name + " in /proc/1/status")
def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()
def file_fingerprint(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            return {"state": "PRESENT", "kind": "non-regular"}
        h = hashlib.sha256()
        size = 0
        while True:
            b = os.read(fd, 1024 * 1024)
            if not b:
                break
            h.update(b)
            size += len(b)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            return {"state": "CHANGED_DURING_READ"}
        return {"state": "PRESENT", "kind": "regular", "uid": after.st_uid,
                "gid": after.st_gid, "mode": format(stat.S_IMODE(after.st_mode), "04o"),
                "size": size, "sha256": h.hexdigest()}
    finally:
        os.close(fd)
def account(name):
    p = run("getent_" + name, ["/usr/bin/getent", "passwd", name])
    return account_from_observation(p, name)
def command_text(label, argv, cwd=None):
    item = run(label, argv, cwd)
    require_success(item, label)
    return item["stdout"].strip()
def main():
    mountpoint = run("mountpoint_check", ["/usr/bin/mountpoint", "-q", "/mnt/d"])
    if mountpoint["exit_code"] == 32 and not mountpoint["stderr"]:
        mounted = run("temporary_read_only_D_mount",
                      ["/usr/bin/mount", "-t", "drvfs", "D:", "/mnt/d", "-o", "ro"])
        require_success(mounted, "temporary read-only D: mount")
    elif mountpoint["exit_code"] != 0 or mountpoint["stderr"]:
        raise RuntimeError("mountpoint check returned an unknown result")
    src = run("findmnt_source", ["/usr/bin/findmnt", "-n", "-o", "SOURCE", "--target", "/mnt/d"])
    fs = run("findmnt_filesystem_options",
             ["/usr/bin/findmnt", "-n", "-o", "FSTYPE,OPTIONS", "--target", "/mnt/d"])
    require_success(src, "findmnt source")
    require_success(fs, "findmnt filesystem/options")
    mount = {
        "source": {"command": "/usr/bin/findmnt -n -o SOURCE --target /mnt/d",
                   "exit_code": src["exit_code"], "started_utc": src["started_utc"],
                   "finished_utc": src["finished_utc"], "stdout": src["stdout"], "stderr": src["stderr"]},
        "filesystem_options": {"command": "/usr/bin/findmnt -n -o FSTYPE,OPTIONS --target /mnt/d",
                   "exit_code": fs["exit_code"], "started_utc": fs["started_utc"],
                   "finished_utc": fs["finished_utc"], "stdout": fs["stdout"], "stderr": fs["stderr"]},
    }
    if src["exit_code"] != 0 or fs["exit_code"] != 0 or not fs["stdout"].split():
        raise RuntimeError("D: mount observation failed; preserved in observations")
    mount_fields = fs["stdout"].split()
    if src["stdout"].split() != ["D:"] or len(mount_fields) != 2 or mount_fields[0] != "9p" or "ro" not in mount_fields[1].split(",") or "rw" in mount_fields[1].split(","):
        raise RuntimeError("D_MOUNT_NOT_9P_RO")
    repo_root = command_text("source_repo_root", ["/usr/bin/git", "-C", REPO,
                                                  "rev-parse", "--show-toplevel"])
    if os.path.realpath(repo_root) != os.path.realpath(REPO):
        raise RuntimeError("Git resolved a repository root outside the authorized checkout")
    head = command_text("source_repo_head", ["/usr/bin/git", "-C", REPO, "rev-parse", "HEAD"])
    source_files = {
        "capture": ("tools/vst/preflight_capture.py", CAPTURE_SHA),
        "applier": ("tools/qa/apply_s2_runtime_configuration.py", APPLIER_SHA),
        "validator": ("tools/qa/verify_s2_runtime_config_inventory.py", VALIDATOR_SHA),
        "bundle": ("docs/sdlc/runtime-config/bundle-manifest.json", BUNDLE_SHA),
        "layout": ("docs/sdlc/runtime-config/installation-layout.json", LAYOUT_SHA),
    }
    source_identity = {"repo_head": head, "implementation_source_commit": IMPLEMENTATION_HEAD,
                       "runtime_source_head": "ee69f9fbf074a4c73d2d5d1da81c627a57d06071",
                       "runtime_capture_sha256": CAPTURE_SHA, "applier_sha256": APPLIER_SHA,
                       "validator_sha256": VALIDATOR_SHA, "bundle_manifest_sha256": BUNDLE_SHA,
                       "installation_layout_sha256": LAYOUT_SHA}
    for key, (rel, expected) in source_files.items():
        path = os.path.join(REPO, rel)
        actual = file_hash(path)
        blob = subprocess.run(["/usr/bin/git", "-C", REPO, "show", "HEAD:" + rel],
                              env=sanitized_git_environment(os.environ),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        match = blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == actual and actual == expected
        if not match or blob.stderr:
            raise RuntimeError("source pin differs from current Git blob: " + rel)
        field = {"capture":"runtime_capture_sha256_matches_head_blob",
                 "applier":"applier_sha256_matches_head_blob",
                 "validator":"validator_sha256_matches_head_blob",
                 "bundle":"bundle_manifest_sha256_matches_head_blob",
                 "layout":"installation_layout_sha256_matches_head_blob"}[key]
        source_identity[field] = bool(match)
        internal("source_hash_" + key, "sha256 + git show HEAD:" + rel,
                 lambda a=actual, b=expected, c=bool(match): {"actual_sha256":a, "authorized_sha256":b, "head_blob_match":c})
    def json_fields(path, keys):
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
        return {k:value.get(k) for k in keys}
    installed = internal("installed_bootstrap_identity", "read identity fields only: /etc/vst-runner/bootstrap-request.json",
                         lambda: json_fields("/etc/vst-runner/bootstrap-request.json", ["request_id","run_id"]))
    store_path = "/var/lib/vst-runner/private/store.sqlite3"
    store_present = os.path.lexists(store_path)
    candidate_collision = candidate_identity_collision(store_present, installed)
    boot = command_text("boot_id", ["/usr/bin/cat", "/proc/sys/kernel/random/boot_id"])
    kernel = command_text("kernel_release", ["/usr/bin/uname", "-r"])
    os_release = run("os_release", ["/usr/bin/cat", "/etc/os-release"])
    require_success(os_release, "OS release")
    distro = parse_os_release(os_release["stdout"])
    systemd_state = command_text("systemd_state", ["/usr/bin/systemctl", "is-system-running"])
    jobs = run("systemd_jobs", ["/usr/bin/systemctl", "list-jobs", "--no-legend", "--no-pager"])
    version = run("systemd_version", ["/usr/bin/systemctl", "--version"])
    shutdown = run("shutdown_schedule", ["/usr/sbin/shutdown", "--show"])
    require_success(jobs, "systemd jobs")
    require_success(version, "systemd version")
    shutdown_scheduled = shutdown_is_scheduled(shutdown)
    comm = command_text("pid1_comm", ["/usr/bin/cat", "/proc/1/comm"])
    pidstat = run("pid1_stat", ["/usr/bin/cat", "/proc/1/stat"])
    status = run("pid1_status", ["/usr/bin/cat", "/proc/1/status"])
    require_success(pidstat, "PID 1 stat")
    require_success(status, "PID 1 status")
    netns = command_text("pid1_net_namespace", ["/usr/bin/stat", "-Lc", "%i", "/proc/1/ns/net"])
    mntns = command_text("pid1_mount_namespace", ["/usr/bin/stat", "-Lc", "%i", "/proc/1/ns/mnt"])
    stat_tail = pidstat["stdout"][pidstat["stdout"].rfind(")") + 2:].split()
    start_ticks = int(stat_tail[19])
    uids = parse_field(status["stdout"], "Uid")
    gids = parse_field(status["stdout"], "Gid")
    pid1 = {"comm":comm, "start_ticks":start_ticks, "net_ns_inode":int(netns),
            "mount_ns_inode":int(mntns), "uid":uids, "gid":gids}
    readiness = {"distro":distro, "kernel":kernel, "systemd":systemd_state,
                 "systemd_jobs":jobs["stdout"].strip(),
                 "shutdown_scheduled":shutdown_scheduled,
                 "systemd_version":version["stdout"].splitlines()[0] if version["stdout"].splitlines() else "",
                 "boot_id":boot, "pid1":pid1}
    accounts = {"vst-runner":account("vst-runner"), "vst-worker":account("vst-worker")}
    readiness["accounts"] = accounts
    units = {}
    for unit in UNITS:
        record = run("unit_" + unit, ["/usr/bin/systemctl", "show", "--property=LoadState",
                     "--property=ActiveState", "--property=SubState", "--property=Job", unit])
        units[unit] = parse_unit_observation(record, unit, jobs["stdout"])
    link = "/opt/vst-runtime"
    if os.path.islink(link):
        runtime_selector = {"state":"PRESENT","kind":"symlink","link_target":os.readlink(link)}
    elif os.path.lexists(link):
        runtime_selector = {"state":"PRESENT","kind":"non-symlink","link_target":""}
    else:
        runtime_selector = {"state":"ABSENT","kind":"unknown","link_target":""}
    with open(os.path.join(REPO,"docs/sdlc/runtime-config/bundle-manifest.json"),"r",encoding="utf-8") as f:
        bundle=json.load(f)
    with open(os.path.join(REPO,"docs/sdlc/runtime-config/installation-layout.json"),"r",encoding="utf-8") as f:
        layout=json.load(f)
    entries=list(bundle["configuration_installation"])+list(layout["unit_overrides"])
    entries += [item for item in bundle["units"] if item["publication"].startswith("new absent-only configuration unit")]
    configuration_files={}
    for item in entries:
        dest=item["destination"]
        fingerprint = internal("fingerprint_"+dest,"read-only O_NOFOLLOW stat+sha256: "+dest,
                               lambda p=dest:file_fingerprint(p))
        if not isinstance(fingerprint, dict) or fingerprint.get("state") != "PRESENT":
            raise RuntimeError("configuration destination fingerprint is incomplete: " + dest)
        configuration_files[dest] = fingerprint
    sockets={p:os.path.lexists(p) for p in CONTAINER_SOCKETS}
    inventory_fields={
        "schema":"VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1",
        "captured_utc":utc(),"source_head":"ee69f9fbf074a4c73d2d5d1da81c627a57d06071",
        "boot_id":boot,"mount":mount,"source_identity":source_identity,
        "configuration_files":configuration_files,"observations":observations,
    }
    inventory=assemble_inventory(
        inventory_fields, readiness, units, runtime_selector,
        store_present=store_present, container_sockets=sockets,
        installed_bootstrap_identity=installed,
        candidate_identity_collision=candidate_collision,
    )
    print(json.dumps(inventory,sort_keys=True,separators=(",",":"),ensure_ascii=True))
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_ATTEMPT_V1",
                          "captured_utc":utc(),"error":type(exc).__name__+": "+str(exc),
                          "observations":observations},sort_keys=True,separators=(",",":"),ensure_ascii=True))
        sys.exit(1)
