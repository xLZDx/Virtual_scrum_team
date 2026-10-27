#!/bin/sh
set -eu

usage() {
    echo "usage: install_wsl_worker_helper.sh EXPECTED_HEAD SOURCE_BUNDLE_ROOT ARCHIVE_SHA256" >&2
    exit 2
}

[ "$#" -eq 3 ] || usage
expected_head=$1
bundle_root=$2
archive_sha=$3

[ "$(id -u)" -eq 0 ] || { echo "installer must run as root" >&2; exit 1; }
case "$expected_head" in
    *[!0-9a-f]*|'') echo "expected head must be a full lowercase commit id" >&2; exit 1 ;;
esac
[ "${#expected_head}" -eq 40 ] || { echo "expected head must be a full lowercase commit id" >&2; exit 1; }
case "$archive_sha" in
    *[!0-9a-f]*|'') echo "archive digest must be a lowercase SHA-256" >&2; exit 1 ;;
esac
[ "${#archive_sha}" -eq 64 ] || { echo "archive digest must be 64 hex characters" >&2; exit 1; }

[ "$(/usr/bin/realpath -e -- "$bundle_root")" = "$bundle_root" ] || {
    echo "source bundle path must be canonical" >&2; exit 1;
}
/usr/bin/python3.12 -I -S -c 'import os,re,sys; head,path=sys.argv[1:]; assert re.fullmatch(r"/run/vst-deploy-"+head+r"-[0-9a-f]{32}", path)' "$expected_head" "$bundle_root" || {
    echo "source bundle must use a unique fixed distro-local deployment path" >&2; exit 1;
}
[ "$(/usr/bin/stat -c '%u:%a' "$bundle_root")" = "0:700" ] || {
    echo "source bundle must be a root-owned mode-0700 directory" >&2; exit 1;
}
/usr/bin/python3.12 -I -S - "$bundle_root/.vst-source-manifest.json" "$expected_head" "$archive_sha" <<'PY'
import json, os, stat, sys
path, head, digest = sys.argv[1:]
info = os.stat(path, follow_symlinks=False)
if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
    raise SystemExit("source bundle manifest must be a root-owned mode-0600 regular file")
with open(path, "r", encoding="ascii") as stream:
    manifest = json.load(stream)
if manifest != {"archive_sha256": digest, "head": head, "schema": 1}:
    raise SystemExit("source bundle manifest does not match requested revision and digest")
PY

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
            raise SystemExit("Windows-drive mount is visible; refusing helper install")
PY

[ "$(/usr/bin/getent passwd 997 | /usr/bin/cut -d: -f1,3,4)" = "vst-runner:997:988" ] || {
    echo "UID/GID 997:988 is not vst-runner" >&2; exit 1;
}
[ "$(/usr/bin/getent passwd 999 | /usr/bin/cut -d: -f1,3,4)" = "vst-worker:999:989" ] || {
    echo "UID/GID 999:989 is not vst-worker" >&2; exit 1;
}
[ "$(/usr/bin/getent group 988 | /usr/bin/cut -d: -f1,3)" = "vst-runner:988" ] || {
    echo "GID 988 is not vst-runner" >&2; exit 1;
}
[ "$(/usr/bin/getent group 989 | /usr/bin/cut -d: -f1,3)" = "vst-worker:989" ] || {
    echo "GID 989 is not vst-worker" >&2; exit 1;
}

install_dir=/usr/local/libexec
helper=$install_dir/vst-s4-worker-exec-$expected_head
[ "$(/usr/bin/realpath -e -- "$install_dir")" = "$install_dir" ] || {
    echo "helper directory must be the canonical /usr/local/libexec path" >&2; exit 1;
}
[ "$(/usr/bin/stat -c '%u' "$install_dir")" = 0 ] || {
    echo "helper directory must be root-owned" >&2; exit 1;
}
dir_mode=$(/usr/bin/stat -c '%a' "$install_dir")
[ $((0$dir_mode & 0022)) -eq 0 ] || {
    echo "helper directory must not be group/world writable" >&2; exit 1;
}

build_dir=$(/usr/bin/mktemp -d "$install_dir/.vst-s4-worker-installer.XXXXXX")
case "$build_dir" in
    /usr/local/libexec/.vst-s4-worker-installer.*) ;;
    *) echo "unsafe installer scratch path" >&2; exit 1 ;;
esac
trap '/bin/rm -rf -- "$build_dir"' EXIT HUP INT TERM

/usr/bin/install -o root -g root -m 0600 \
    "$bundle_root/tools/qa/worker_exec.c" "$build_dir/worker_exec.c"
source_sha=$(/usr/bin/sha256sum "$build_dir/worker_exec.c" | /usr/bin/cut -d' ' -f1)
/usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/cc \
    -std=c11 -O2 -D_FORTIFY_SOURCE=2 -fstack-protector-strong \
    -Wall -Wextra -Wconversion -Wshadow -Wformat=2 -Werror \
    "-DHELPER_BUILD_HEAD=\"$expected_head\"" \
    "-DHELPER_SOURCE_SHA256=\"$source_sha\"" \
    -Wl,-z,relro,-z,now -o "$build_dir/vst-s4-worker-exec" "$build_dir/worker_exec.c"
binary_sha=$(/usr/bin/sha256sum "$build_dir/vst-s4-worker-exec" | /usr/bin/cut -d' ' -f1)
expected_identity="schema=1 head=$expected_head source_sha256=$source_sha"
staged_identity=$(/usr/bin/env -i PATH=/usr/bin:/bin "$build_dir/vst-s4-worker-exec" --version)
[ "$staged_identity" = "$expected_identity" ] || {
    echo "staged helper build identity did not match the committed source" >&2; exit 1;
}

if [ -e "$helper" ] || [ -L "$helper" ]; then
    [ ! -L "$helper" ] && [ -f "$helper" ] || {
        echo "existing exact-version helper is not a regular file; no host state changed" >&2; exit 1;
    }
    existing_metadata=$(/usr/bin/stat -c '%u:%g:%a:%h' "$helper")
    [ "$existing_metadata" = "0:988:4750:1" ] || {
        echo "existing exact-version helper metadata differs; preserve and inspect before retry" >&2; exit 1;
    }
    existing_sha=$(/usr/bin/sha256sum "$helper" | /usr/bin/cut -d' ' -f1)
    [ "$existing_sha" = "$binary_sha" ] || {
        echo "existing helper bytes differ from the requested build; preserve and inspect before retry" >&2; exit 1;
    }
    existing_identity=$(/usr/bin/env -i PATH=/usr/bin:/bin "$helper" --version)
    [ "$existing_identity" = "$expected_identity" ] || {
        echo "existing helper identity differs from the requested source; no host state changed" >&2; exit 1;
    }
else
    # Publish only a fully built exact binary; hard-link creation cannot replace an existing path.
    /usr/bin/install -o root -g vst-runner -m 4750 "$build_dir/vst-s4-worker-exec" "$build_dir/installed-helper"
    /bin/ln -- "$build_dir/installed-helper" "$helper" || {
        echo "helper destination changed during no-overwrite installation; inspect and retry" >&2; exit 1;
    }
    /bin/rm -- "$build_dir/installed-helper"
fi

installed_identity=$(/usr/bin/env -i PATH=/usr/bin:/bin "$helper" --version)
[ "$installed_identity" = "$expected_identity" ] || {
    echo "installed helper build identity did not match the committed source; preserve and inspect state" >&2; exit 1;
}
[ "$(/usr/bin/sha256sum "$helper" | /usr/bin/cut -d' ' -f1)" = "$binary_sha" ] || {
    echo "published helper digest differs from the verified build; preserve and inspect state" >&2; exit 1;
}
[ "$(/usr/bin/stat -c '%u:%g:%a:%h' "$helper")" = "0:988:4750:1" ] || {
    echo "published helper metadata differs from the required immutable installation; preserve and inspect" >&2; exit 1;
}

echo "installed immutable versioned WSL worker helper from source bundle $expected_head"
echo "binary_sha256=$binary_sha"
echo "helper_mode=$( /usr/bin/stat -c '%u:%g:%a' "$helper" )"
