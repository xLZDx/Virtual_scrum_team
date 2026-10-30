#!/bin/sh
set -eu

usage() {
    echo "usage: install_wsl_runner_runtime.sh EXPECTED_HEAD SOURCE_BUNDLE_ROOT ARCHIVE_SHA256 PLAN_SHA256 INVENTORY_SHA256 [--stage-only]" >&2
    exit 2
}

[ "$#" -eq 5 ] || [ "$#" -eq 6 ] || usage
expected_head=$1
bundle_root=$2
archive_sha=$3
plan_sha=$4
inventory_sha=$5
stage_only=0
if [ "$#" -eq 6 ]; then
    [ "$6" = "--stage-only" ] || usage
    stage_only=1
fi
case "$expected_head" in
    *[!0-9a-f]*|'') echo "expected head must be a full lowercase commit id" >&2; exit 1 ;;
esac
[ "${#expected_head}" -eq 40 ] || { echo "expected head must be 40 hex characters" >&2; exit 1; }
case "$archive_sha" in
    *[!0-9a-f]*|'') echo "archive digest must be a lowercase SHA-256" >&2; exit 1 ;;
esac
[ "${#archive_sha}" -eq 64 ] || { echo "archive digest must be 64 hex characters" >&2; exit 1; }
case "$plan_sha" in
    *[!0-9a-f]*|'') echo "source plan digest must be a lowercase SHA-256" >&2; exit 1 ;;
esac
[ "${#plan_sha}" -eq 64 ] || { echo "source plan digest must be 64 hex characters" >&2; exit 1; }
case "$inventory_sha" in
    *[!0-9a-f]*|'') echo "target inventory digest must be a lowercase SHA-256" >&2; exit 1 ;;
esac
[ "${#inventory_sha}" -eq 64 ] || { echo "target inventory digest must be 64 hex characters" >&2; exit 1; }
[ "$(/usr/bin/id -u)" -eq 0 ] || { echo "installer must run as root" >&2; exit 1; }

bundle_root=$(/usr/bin/realpath -e -- "$bundle_root")
/usr/bin/python3.12 -I -S -c 'import os,re,sys; head,path=sys.argv[1:]; assert re.fullmatch(r"/run/vst-deploy-"+head+r"-[0-9a-f]{32}", path)' "$expected_head" "$bundle_root" || {
    echo "source bundle must use a unique fixed distro-local deployment path" >&2; exit 1;
}
[ "$(/usr/bin/stat -c '%u:%a' "$bundle_root")" = "0:700" ] || {
    echo "source bundle must be a root-owned mode-0700 directory" >&2; exit 1;
}
/usr/bin/python3.12 -I -S "$bundle_root/tools/qa/verify_wsl_source_bundle.py" \
    --root "$bundle_root" --expected-head "$expected_head" \
    --archive-sha256 "$archive_sha" --plan-sha256 "$plan_sha" \
    --inventory-sha256 "$inventory_sha"

. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || {
    echo "installer requires Ubuntu 24.04" >&2; exit 1;
}
/bin/grep -qi microsoft /proc/sys/kernel/osrelease || {
    echo "installer requires WSL" >&2; exit 1;
}
/usr/bin/python3.12 -I -S -c 'import configparser; p=configparser.ConfigParser(); p.read("/etc/wsl.conf"); assert p.getboolean("automount", "enabled") is False; assert p.getboolean("interop", "enabled") is False; assert p.getboolean("interop", "appendWindowsPath") is False' || {
    echo "WSL automount and interop must both be disabled" >&2; exit 1;
}
/usr/bin/python3.12 -I -S - <<'PY'
import re
with open("/proc/self/mountinfo", encoding="ascii") as stream:
    for line in stream:
        fields = line.rstrip("\n").split(" - ", 1)
        if len(fields) != 2:
            raise SystemExit("cannot parse complete mount inventory")
        mount = fields[1].split()
        if len(mount) < 3:
            raise SystemExit("cannot parse mount entry")
        fs_type, source, super_options = mount[:3]
        drive_source = bool(re.match(r"^[A-Za-z]:[\\/]?$", source))
        if fs_type == "drvfs" or (fs_type == "9p" and (drive_source or "aname=drvfs" in super_options)):
            raise SystemExit("Windows-drive mount is visible; refusing runtime install")
PY

if [ "$stage_only" -eq 1 ]; then
    /usr/bin/python3.12 -I -B -S - "$bundle_root" <<'PY'
import os, subprocess, sys

sys.path.insert(0, sys.argv[1])
from tools.vst.runtime_bundle import validate_stage_only_config_directory

for path in ("/run/vst-supervisor", "/run/vst-runner"):
    if os.path.lexists(path):
        raise SystemExit("stage-only requires absent runtime socket paths: " + path)
validate_stage_only_config_directory("/etc/vst-runner")

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
        continue
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
PY
fi

runtime_dir="/opt/vst-runtime-$expected_head"
runtime_link=/opt/vst-runtime
unit_dir=/etc/systemd/system

stage=$(/usr/bin/mktemp -d /opt/.vst-runtime-stage.XXXXXX)
unit_tmp=
trap '[ -z "$unit_tmp" ] || /bin/rm -f -- "$unit_tmp"; /bin/rm -rf -- "$stage"' EXIT HUP INT TERM
/usr/bin/install -d -o root -g root -m 0755 "$stage/tools"
/usr/bin/cp -a -- "$bundle_root/tools/vst" "$stage/tools/vst"
[ -f "$bundle_root/docs/SANDBOX_SPEC.md" ] || {
    echo "source bundle is missing the S2 sandbox specification" >&2; exit 1;
}
/usr/bin/cp -a -- "$bundle_root/docs" "$stage/docs"
[ -f "$stage/tools/vst/systemd/vst-supervisor.service" ] &&
    [ -f "$stage/tools/vst/systemd/vst-signer.service" ] &&
    [ -f "$stage/tools/vst/systemd/vst-runner.service" ] &&
    [ -f "$stage/tools/vst/systemd/vst-dispatcher.service" ] &&
    [ -f "$stage/tools/vst/systemd/vst-dispatch-owner.service" ] &&
    [ -f "$stage/tools/vst/systemd/vst-dispatch-owner.socket" ] || {
    echo "source bundle is missing a required systemd unit" >&2; exit 1;
}
/usr/bin/chown -R root:root "$stage/tools/vst"
/usr/bin/find "$stage/tools/vst" -type d -exec /bin/chmod 0755 {} +
/usr/bin/find "$stage/tools/vst" -type f -exec /bin/chmod 0644 {} +
/usr/bin/chown -R root:root "$stage/docs"
/usr/bin/find "$stage/docs" -type d -exec /bin/chmod 0755 {} +
/usr/bin/find "$stage/docs" -type f -exec /bin/chmod 0644 {} +
/usr/bin/python3.12 -I -S - "$stage/.vst-runtime-manifest.json" "$expected_head" "$archive_sha" "$plan_sha" "$inventory_sha" "$bundle_root" <<'PY'
import json, os, sys
path, head, digest, plan_digest, inventory_digest, bundle_root = sys.argv[1:]
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
with os.fdopen(fd, "w", encoding="ascii") as stream:
    source_manifest_path = os.path.join(bundle_root, ".vst-source-manifest.json")
    with open(source_manifest_path, "r", encoding="ascii") as source_stream:
        source_manifest = json.load(source_stream)
    json.dump({"archive_sha256": digest,
               "compiler_path": source_manifest["compiler_path"],
               "compiler_resolved_path": source_manifest["compiler_resolved_path"],
               "compiler_sha256": source_manifest["compiler_sha256"],
               "compiler_symlink_target": source_manifest["compiler_symlink_target"],
               "head": head, "inventory_sha256": inventory_digest,
               "plan_sha256": plan_digest, "schema": 3}, stream,
              sort_keys=True, separators=(",", ":"))
    stream.flush()
    os.fsync(stream.fileno())
os.chmod(path, 0o644)
PY
/bin/chmod 0755 "$stage"
/usr/bin/python3.12 -I -S "$bundle_root/tools/qa/verify_wsl_runtime_stage.py" \
    --stage "$stage" --source-manifest "$bundle_root/.vst-source-manifest.json" \
    --expected-head "$expected_head" --archive-sha256 "$archive_sha" \
    --plan-sha256 "$plan_sha" --inventory-sha256 "$inventory_sha"
/usr/bin/python3.12 -I -S - "$stage" "$runtime_dir" "$runtime_link" "$unit_dir" "$expected_head" "$archive_sha" "$stage_only" "$plan_sha" "$inventory_sha" "$bundle_root" <<'PY'
import hashlib, json, os, stat, sys
stage, runtime, link, unit_dir, head, digest, stage_only, plan_sha, inventory_sha, bundle_root = sys.argv[1:]
stage_only = stage_only == "1"
def path_exists(path): return os.path.lexists(path)
def scan(root, installed=False):
    result = {}
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode):
        raise SystemExit("runtime package root is not a directory: " + root)
    if installed and (root_info.st_uid != 0 or stat.S_IMODE(root_info.st_mode) != 0o755):
        raise SystemExit("installed runtime package root has unexpected owner/mode: " + root)
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs.sort(); files.sort()
        for name in dirs + files:
            path = os.path.join(current, name)
            info = os.lstat(path)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if stat.S_ISDIR(info.st_mode):
                if installed and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o755):
                    raise SystemExit("existing runtime directory has unexpected owner/mode: " + path)
                result[rel] = ("dir", None)
            elif stat.S_ISREG(info.st_mode):
                if installed and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o644 or info.st_nlink != 1):
                    raise SystemExit("existing runtime file has unexpected owner/mode: " + path)
                with open(path, "rb") as stream: digest_value = hashlib.sha256(stream.read()).hexdigest()
                result[rel] = ("file", digest_value)
            else:
                raise SystemExit("runtime path contains an unexpected file type: " + path)
    return result
with open(os.path.join(bundle_root, ".vst-source-manifest.json"), "r", encoding="ascii") as stream:
    source_manifest = json.load(stream)
expected_runtime = {
    name: (entry["kind"], entry.get("sha256"))
    for name, entry in source_manifest["archive_members"].items()
    if name in ("tools", "tools/vst", "docs")
    or name.startswith("tools/vst/") or name.startswith("docs/")
}
if not expected_runtime:
    raise SystemExit("reviewed source manifest has no runtime entries")
staged_tree = scan(stage, installed=True)
if sorted(os.listdir(stage)) != [".vst-runtime-manifest.json", "docs", "tools"]:
    raise SystemExit("staged runtime has unexpected or missing top-level entries")
staged_tree.pop(".vst-runtime-manifest.json", None)
if staged_tree != expected_runtime:
    raise SystemExit("staged runtime tree differs from exact reviewed source manifest")
if path_exists(runtime):
    info = os.lstat(runtime)
    marker = os.path.join(runtime, ".vst-runtime-manifest.json")
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o755:
        raise SystemExit("runtime destination is not a root-owned mode-0755 directory")
    if sorted(os.listdir(runtime)) != [".vst-runtime-manifest.json", "docs", "tools"]:
        raise SystemExit("runtime destination has unexpected or missing entries")
    marker_info = os.lstat(marker)
    if not stat.S_ISREG(marker_info.st_mode) or marker_info.st_uid != 0 or stat.S_IMODE(marker_info.st_mode) != 0o644:
        raise SystemExit("runtime destination manifest has unexpected owner, mode, or type")
    with open(marker, "r", encoding="ascii") as stream: manifest = json.load(stream)
    expected_marker = {
        "archive_sha256": digest,
        "compiler_path": source_manifest["compiler_path"],
        "compiler_resolved_path": source_manifest["compiler_resolved_path"],
        "compiler_sha256": source_manifest["compiler_sha256"],
        "compiler_symlink_target": source_manifest["compiler_symlink_target"],
        "head": head, "inventory_sha256": inventory_sha,
        "plan_sha256": plan_sha, "schema": 3,
    }
    if manifest != expected_marker:
        raise SystemExit("runtime destination manifest differs from requested head/digest")
    for subtree in ("tools/vst", "docs"):
        subtree_info = os.lstat(os.path.join(runtime, subtree.split("/", 1)[0]))
        if not stat.S_ISDIR(subtree_info.st_mode) or subtree_info.st_uid != 0 or stat.S_IMODE(subtree_info.st_mode) != 0o755:
            raise SystemExit("runtime top-level directory has unexpected owner/mode")
        if scan(os.path.join(stage, subtree)) != scan(os.path.join(runtime, subtree), installed=True):
            raise SystemExit("runtime destination differs from requested source: " + subtree)
if not stage_only:
    if path_exists(link):
        info = os.lstat(link)
        if not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or os.readlink(link) != runtime:
            raise SystemExit("runtime selector exists with different target/type/owner")
    for unit in ("vst-supervisor.service", "vst-signer.service", "vst-runner.service",
                 "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket"):
        source = os.path.join(stage, "tools/vst/systemd", unit)
        dest = os.path.join(unit_dir, unit)
        if path_exists(dest):
            info = os.lstat(dest)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o644:
                raise SystemExit("systemd unit exists with unexpected type/owner/mode: " + dest)
            with open(source, "rb") as a, open(dest, "rb") as b:
                if a.read() != b.read(): raise SystemExit("systemd unit bytes differ: " + dest)
PY
if [ ! -e "$runtime_dir" ] && [ ! -L "$runtime_dir" ]; then
    /usr/bin/mv -Tn -- "$stage" "$runtime_dir"
    [ ! -e "$stage" ] || {
        echo "runtime path changed during no-overwrite install; inspect state before retry" >&2; exit 1;
    }
fi
if [ "$stage_only" -eq 1 ]; then
    echo "staged immutable runtime revision $expected_head from the verified source bundle"
    echo "runtime_dir=$runtime_dir"
    echo "selected=false"
    echo "systemd_units_installed=0"
    exit 0
fi

if [ ! -e "$runtime_link" ] && [ ! -L "$runtime_link" ]; then
    /bin/ln -s "$runtime_dir" "$runtime_link"
fi

for unit in vst-supervisor.service vst-signer.service vst-runner.service vst-dispatcher.service \
    vst-dispatch-owner.service vst-dispatch-owner.socket; do
    unit_path="$unit_dir/$unit"
    if [ ! -e "$unit_path" ] && [ ! -L "$unit_path" ]; then
        unit_tmp=$(/usr/bin/mktemp "$unit_dir/.vst-unit.XXXXXX")
        /usr/bin/install -o root -g root -m 0644 \
            "$runtime_dir/tools/vst/systemd/$unit" "$unit_tmp"
        /bin/ln -- "$unit_tmp" "$unit_path" || {
            echo "unit destination changed during no-overwrite installation: $unit_path" >&2; exit 1;
        }
        /bin/rm -f -- "$unit_tmp"
        unit_tmp=
    fi
done

echo "installed immutable runtime revision $expected_head from the verified source bundle"
echo "runtime_dir=$runtime_dir"
echo "systemd_units_installed=6 (not enabled or started)"
