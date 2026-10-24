# S2 E2E Windows and WSL diagnostic evidence

## Windows focused lifecycle suite

- Source HEAD: `c470542dbedf992b785804e421b1ff52e142003c`.
- Environment: Windows, PowerShell 7.6.7, Python 3.14.3 at `C:\Python314\python.exe`.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py`.
- Result: 80 passed, 21 skipped, 1 deprecation warning, exit code 0.
- Skips remain `NOT_RUN`: 5 runner identity/containment cases, 9 POSIX anchor cases, 1 real WSL/VM inventory and 6 E8 sandbox cases. Process-kill and kill-table scenarios were not run.

## WSL unsigned diagnostic

The source archive was taken from the exact committed HEAD above and installed in the isolated Ubuntu-24.04 WSL distribution for this diagnostic. It ran as `vst-runner` in `vst-run.slice`; the slice reports CPU quota 100%, memory limit 2 GiB and task limit 64.

- Diagnostic run ID: `s2-c470542dbedf992b785804e421b1ff52e142003c-preflight-wsl24-09b08fb53dd942d1a8a2e607a8dc9724`.
- Fresh nonce: `a592329347f748ed8758e24c0e96ebdc`.
- `docs/SANDBOX_SPEC.md` SHA-256: `451efdb04a346d6f53d012f2f67d21ce3452b645dae67b9337bd1841da5a9ab3`.
- The run ID embeds the source HEAD because the probe schema has no separate code-head field. Any eventual signature binds run ID, spec digest and nonce; it does not contain a separate signed code-head field.
- The operator attestation placeholder was unsigned and omitted its signature. Diagnostic result: `FAIL`.

Checked properties:

| Property | Result |
|---|---|
| `automount_disabled` | false |
| `interop_disabled` | true |
| `no_container_socket` | false; enumeration incomplete |
| `non_root` | true |
| `external_egress_blocked` | true; reserved-target smoke check only |
| `loopback_canary` | true |
| `empty_external_allowlist` | false; unsigned placeholder |

The detected socket basename list was empty, but completeness was false, so this does not establish socket absence. The `/run/user` scan found one numeric entry and one real directory, with no nonnumeric entry, symlink, or entry-stat permission error. During candidate inspection, two parent-directory permission errors and one socket-path stat permission error occurred. `/proc/net/unix` was readable; all enumerated standard engine endpoint paths were missing. No directory names, UIDs, or full paths are retained here.

Mount-table rows are recorded only by target class and filesystem type:

| Target class | Filesystem type | Count |
|---|---:|---:|
| `/mnt/wslg` | ext4 | 1 |
| `/mnt/wslg` | overlay | 2 |
| `/mnt/wslg` | tmpfs | 2 |
| `/usr/lib/wsl*` | 9p | 1 |
| `/usr/lib/wsl*` | overlay | 1 |
| `/usr/lib/modules` | overlay | 1 |
| Windows drive mounts | none detected | 0 |

Other observed filesystem types were `binfmt_misc`, `cgroup2`, `configfs`, `debugfs`, `devpts`, `devtmpfs`, `ext4`, `fusectl`, `hugetlbfs`, `mqueue`, `proc`, `rootfs`, `sysfs`, `tmpfs`, and `tracefs`. A mount target under `/mnt/` was present, which makes the current broad `automount_disabled` check false even though the sanitized classification found no Windows drive mount. Whether WSLg and system mounts are approved remains an operator decision. Unapproved host-path status is `UNKNOWN` pending an operator-signed policy attestation.

The reserved-address probe only checks one target and is not evidence of default-deny egress. The signer socket was absent and `vst-signer.service` inactive at diagnostic time. No operator or signer key was read. No signed final inventory or POSIX anchor test was run; both remain `NOT_RUN` pending correction/approval of the diagnostic blockers and signer provisioning.
