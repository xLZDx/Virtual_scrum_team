# S2 exact-head WSL runtime install — `d5001797` — 2026-10-28

## Result and scope

The authorized installer completed successfully at exact committed code/test HEAD
`d5001797cb94113efd9a8dc26e4a15f2dc130976` in the in-scope `Ubuntu-24.04` WSL2 distribution.
It installed the versioned, root-owned UID-transition helper, immutable runtime tree, and three
unit files. The prior legacy helper was not overwritten or deleted. The installer reported that
the units were not enabled or started. No systemd reload/enable/start command, runner configuration,
keys, operator attestation, manifest, worker run, network traffic probe, or prohibited selector was
performed. This record proves installation only; it does not claim S2 runtime acceptance or E5
PASS.

## Exact-head and clean-source preflight

Commands and results:

```text
git rev-parse HEAD
=> d5001797cb94113efd9a8dc26e4a15f2dc130976

git status --porcelain --untracked-files=no
=> empty (tracked worktree clean)

git rev-parse d5001797cb94113efd9a8dc26e4a15f2dc130976:tools/qa/install_wsl_runtime.ps1
git hash-object --path=tools/qa/install_wsl_runtime.ps1 -- tools/qa/install_wsl_runtime.ps1
=> both f5c8e30fc6f8aec045405032fdefabef735a9148
```

The unrelated pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not
inspected or staged. The untracked `docs/sdlc/evidence/s2-versioned-worker-helper-execution-20261028-attempt5.md`
was observed in status and left untouched; its provenance was not verified.

## Read-only WSL preflight

Distribution listing command:

```powershell
wsl.exe --list --verbose
```

The distro was `Ubuntu-24.04`, WSL version 2. The root-run, standard-library-only read-only probe
was invoked as:

```powershell
wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -I -S -c <base64-encoded read-only preflight probe>
```

The probe inspected `/etc/os-release`, `/etc/wsl.conf`, `/proc/self/mountinfo`, cgroup controller
files, accounts 997/999, systemd state, the existing helper and target paths, nftables rules, and
compiler availability. It did not write configuration or execute a worker. Results:

- Ubuntu 24.04.5 LTS; kernel `6.6.114.1-microsoft-standard-WSL2`; systemd reported `running`.
- WSL automount disabled; interop disabled; `appendWindowsPath=false`; zero Windows-drive mounts
  in the inspected 31-entry mount inventory.
- Runner identity is `vst-runner` UID/GID `997:988`; worker identity is `vst-worker` UID/GID
  `999:989`.
- Cgroup controllers/subtree controllers available: `cpuset cpu io memory hugetlb pids rdma`.
- nftables table `inet vst_s2_filter`: input and output chains both had policy `drop` and accepted
  loopback only. No traffic was sent; effective network enforcement is not established by this
  configuration snapshot.
- `/usr/bin/cc` exists and resolves to `/usr/bin/x86_64-linux-gnu-gcc-13`.
- Before installation, the versioned helper, versioned runtime directory, runtime selector link,
  and all three VST unit files were absent. Their fixed parent directories `/usr/local/libexec`,
  `/opt`, and `/etc/systemd/system` were root-owned mode `0755`.
- The in-scope provisioning guide labels this distribution as dedicated for the recorded per-run
  E5 correlation. This task verified its local configuration, but did not create a new distro or
  independently attest its external provisioning identity.

## Archive LF verification

The installer uses the following read-only archive command at the exact head:

```text
git -c core.autocrlf=false -c core.eol=lf -C D:\Repo\Virtual_scrum_team --no-replace-objects archive --format=tar d5001797cb94113efd9a8dc26e4a15f2dc130976 -- tools/vst tools/qa/install_wsl_runner_runtime.sh tools/qa/install_wsl_worker_helper.sh tools/qa/worker_exec.c docs/SANDBOX_SPEC.md
```

The in-memory archive SHA-256 was
`9f344b763d8b7e5a376af0cc2c8ed40f9da262bcb88aca5da2ac2f71c32b7c9b` (901120 bytes). Both shell
script members had zero CRLF and zero bare-CR bytes; line 2 was `set -eu\n`. Their member hashes
were:

- `install_wsl_runner_runtime.sh`: `b15117bf2d6ead8e29572f090c747692a18dc09e728d6771c399aa611f45f55c`.
- `install_wsl_worker_helper.sh`: `9e1d70c6df5a3ba195ba67581d4cf0485f1d0207ca0ddebecd7e9025883cead1`.

The archive SHA matches the installer-emitted digest and the installed runtime manifest.

## Existing helper before and after

The old fixed helper was inspected before the installer and again afterward. It remained unchanged:

```text
Path: /usr/local/libexec/vst-s4-worker-exec
Type: regular file; owner/group/mode: 0:988:4750
SHA-256: a9d381acab8cbfd299be2e631caeca370f98193271df85fa8583172dbc0591dc
--version: schema=1 head=621ddc01d1b5bbf701ccced7bb073c26e89c8c07 source_sha256=8c1a5986c8e081a05a3291b65f082fbd3a0dd0f93109a6395dd2bf57d43beb21
```

No replacement or deletion of this legacy root-owned setuid executable occurred.

## Installer command and result

Exact command:

```powershell
$expected='d5001797cb94113efd9a8dc26e4a15f2dc130976'
& .\tools\qa\install_wsl_runtime.ps1 -ExpectedHead $expected -Distribution 'Ubuntu-24.04'
```

Installer output:

```text
installed immutable versioned WSL worker helper from source bundle d5001797cb94113efd9a8dc26e4a15f2dc130976
binary_sha256=fbff000986ea7db666e6aaaeb85ebbb26599f060c196fe4d018b8871052d03e5
helper_mode=0:988:4750
installed immutable runtime revision d5001797cb94113efd9a8dc26e4a15f2dc130976 from the verified source bundle
runtime_dir=/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976
systemd_units_installed=3 (not enabled or started)
source_bundle_path=/run/vst-deploy-d5001797cb94113efd9a8dc26e4a15f2dc130976-495d6ca90b834b5a8b2d2c4a3be43a6c
source_head=d5001797cb94113efd9a8dc26e4a15f2dc130976
source_archive_sha256=9f344b763d8b7e5a376af0cc2c8ed40f9da262bcb88aca5da2ac2f71c32b7c9b
source_transfer=stdin; no Windows-drive mount or second checkout used
```

The source bundle was passed by stdin. No second checkout or Windows-drive mount was used by the
installer.

## Post-install read-only verification

The root-run Python probe used `os.lstat`, SHA-256, JSON manifest parsing, and direct helper
`--version` calls; it did not modify installed state. It confirmed:

- New helper `/usr/local/libexec/vst-s4-worker-exec-d5001797cb94113efd9a8dc26e4a15f2dc130976` is
  a regular file, owner/group/mode `0:988:4750`, SHA-256
  `fbff000986ea7db666e6aaaeb85ebbb26599f060c196fe4d018b8871052d03e5`, and reports
  `schema=1 head=d5001797cb94113efd9a8dc26e4a15f2dc130976 source_sha256=ea76231fe4b3ae99902be7be43d3a7a970f9ea28c7b27258097f0ceb9d20d951`.
- Legacy helper path, digest, mode, owner/group, and `621ddc01` identity match the pre-install
  snapshot above.
- Runtime `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976` is a root-owned mode-0755
  directory. Its `.vst-runtime-manifest.json` records schema 1, exact HEAD `d5001797...`, and the
  archive SHA above. `/opt/vst-runtime` is a root-owned symlink to that exact directory.
- Installed units are root:root mode `0644` and byte-identical to the unit copies in the runtime:
  - `vst-runner.service`: SHA-256
    `4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be`.
  - `vst-signer.service`: SHA-256
    `33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d`.
  - `vst-supervisor.service`: SHA-256
    `aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c`.

No service was enabled, started, or run as part of this operation. The systemd manager still
reported `running`; service activation was neither requested nor performed.

## Limitations and next actions

This evidence proves exact-head artifact installation and file identity only. It does not prove
effective systemd sandbox directives, cgroup delegation/enforcement, worker identity transition,
capability clearing at runtime, default-deny egress through an actual attempted connection,
Windows/POSIX process containment, workspace isolation, signed inventory, operator E5 attestation,
or any manifest execution. Process-kill, crash/recovery, mutation, E8, policy selectors, service
enable/start, key creation, runner configuration, and manifest run remain `NOT_RUN`.

Codex owns the next code and documentation work; `e2e-runner` owns permitted runtime evidence only
after the accepted configuration and keys exist. GPT-PM owns exact-head adjudication. A fresh
run-bound operator E5 signature remains an actual operator attestation and is not implied here.
