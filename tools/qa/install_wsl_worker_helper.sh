#!/bin/sh
set -eu

usage() {
    echo "usage: install_wsl_worker_helper.sh EXPECTED_HEAD CANDIDATE_REPO_ROOT" >&2
    exit 2
}

[ "$#" -eq 2 ] || usage
expected_head=$1
repo_root=$2

[ "$(id -u)" -eq 0 ] || { echo "installer must run as root" >&2; exit 1; }
case "$expected_head" in
    *[!0-9a-f]*|'') echo "expected head must be a full lowercase commit id" >&2; exit 1 ;;
esac
[ "${#expected_head}" -eq 40 ] || { echo "expected head must be a full lowercase commit id" >&2; exit 1; }

repo_root=$(/usr/bin/realpath -e -- "$repo_root")
case "$repo_root" in
    /tmp/vst-s4-candidate|/tmp/vst-s4-candidate/*) ;;
    *) echo "candidate must be inside the distro-local /tmp/vst-s4-candidate root" >&2; exit 1 ;;
esac

. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || {
    echo "installer requires Ubuntu 24.04" >&2; exit 1;
}
/bin/grep -qi microsoft /proc/sys/kernel/osrelease || {
    echo "installer requires WSL" >&2; exit 1;
}
/usr/bin/python3.12 -I -c 'import configparser; p=configparser.ConfigParser(); p.read("/etc/wsl.conf"); assert p.getboolean("automount", "enabled") is False; assert p.getboolean("interop", "enabled") is False' || {
    echo "WSL automount and interop must both be disabled" >&2; exit 1;
}

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

gitc() {
    /usr/bin/env -i PATH=/usr/bin:/bin GIT_CONFIG_NOSYSTEM=1 \
        GIT_CONFIG_GLOBAL=/dev/null GIT_PAGER=cat \
        /usr/bin/git --no-replace-objects --no-pager -c "safe.directory=$repo_root" \
        -c core.fsmonitor=false -c core.hooksPath=/dev/null \
        -C "$repo_root" "$@"
}

[ "$(gitc rev-parse --verify HEAD)" = "$expected_head" ] || {
    echo "candidate HEAD does not match the requested helper source" >&2; exit 1;
}
[ -z "$(gitc status --porcelain=v1 --untracked-files=all)" ] || {
    echo "candidate worktree must be clean before helper installation" >&2; exit 1;
}

install_dir=/usr/local/libexec
helper=$install_dir/vst-s4-worker-exec
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

if [ -e "$helper" ] || [ -L "$helper" ]; then
    echo "refusing to replace a pre-existing worker helper" >&2
    exit 1
fi

build_dir=$(/usr/bin/mktemp -d "$install_dir/.vst-s4-worker-installer.XXXXXX")
case "$build_dir" in
    /usr/local/libexec/.vst-s4-worker-installer.*) ;;
    *) echo "unsafe installer scratch path" >&2; exit 1 ;;
esac
trap '/bin/rm -rf -- "$build_dir"' EXIT HUP INT TERM

gitc show "$expected_head:tools/qa/worker_exec.c" > "$build_dir/worker_exec.c"
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

# Fixed destination, owner and mode: no parameter can broaden the privilege.
/usr/bin/install -o root -g vst-runner -m 4750 "$build_dir/vst-s4-worker-exec" "$build_dir/installed-helper"
/bin/mv -- "$build_dir/installed-helper" "$helper"

installed_identity=$(/usr/bin/env -i PATH=/usr/bin:/bin "$helper" --version)
[ "$installed_identity" = "$expected_identity" ] || {
    /bin/chmod 0750 "$helper"
    echo "installed helper build identity did not match the committed source" >&2; exit 1;
}

echo "installed fixed WSL worker helper for candidate $expected_head"
echo "binary_sha256=$binary_sha"
echo "helper_mode=$( /usr/bin/stat -c '%u:%g:%a' "$helper" )"
