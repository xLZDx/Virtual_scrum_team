# S2 WSL installer preflight — exact HEAD `7120e2c` — 2026-10-28

## Result

The committed WSL runtime installer did not complete. It launched the WSL-side
`install_wsl_worker_helper.sh`, which exited with status 2 at line 2. Exact-head archive
inspection established that Git converted the committed LF shell-script blob to CRLF while
exporting it. WSL `/bin/sh` then rejected `set -eu\r` with `Illegal option -`. The fixed runtime
and its systemd units were not installed. This is installer failure evidence, not runtime
acceptance. No E5 signature, worker execution, network traffic probe, or restricted selector was
performed.

## Scope and identity

- Repository: `D:\Repo\Virtual_scrum_team`; branch `s4-canonical-continuation`.
- Exact committed code/test head: `7120e2c647cc95703704905efa76de735ca8d0ec`.
- The in-scope operator guide labels `Ubuntu-24.04` a dedicated Ubuntu-24.04 WSL2 environment for
  the recorded per-run E5 correlation. This session verified the listed distribution and its local
  controls, but did not independently attest its provisioning identity or host network owner.
- `wsl.exe --list --verbose` initially showed `Ubuntu-24.04` stopped. The read-only probe started
  it; subsequent listing showed it running. No persistent configuration was edited by this probe.

## Read-only environment evidence

Command used to start the read-only probe:

```powershell
wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -I -S -c <base64-encoded read-only probe>
```

The probe read `/etc/os-release`, `/etc/wsl.conf`, `/proc/self/mountinfo`, kernel release,
`/sys/fs/cgroup/cgroup.controllers`, account database entries for UIDs 997/999, systemd status,
VST unit load/active states, and the nftables ruleset. Observed output:

- Ubuntu 24.04.5 LTS; WSL2 kernel `6.6.114.1-microsoft-standard-WSL2`.
- Automount disabled; interop disabled; `appendWindowsPath=false`; zero Windows-drive mounts in
  the inspected mount table (31 total mounts).
- Read-only probe ran as root (UID 0); UID 997 is `vst-runner:997:988`; UID 999 is
  `vst-worker:999:989`.
- `systemctl is-system-running` returned `running`; all three `vst-runner.service`,
  `vst-signer.service`, and `vst-supervisor.service` reported `LoadState=not-found`,
  `ActiveState=inactive`.
- Cgroup v2 controller files reported `cpuset cpu io memory hugetlb pids rdma` in both
  `cgroup.controllers` and `cgroup.subtree_control`. This snapshot does not prove per-run delegated
  cgroup enforcement.
- nftables snapshot showed table `inet vst_s2_filter`; input and output chains both had policy
  `drop` and accepted loopback only. No egress traffic was attempted; this is configuration
  evidence, not proof of effective external-egress denial.
- `/opt/vst-runtime` did not exist. The existing worker helper reported build identity
  `schema=1 head=621ddc01d1b5bbf701ccced7bb073c26e89c8c07`; it is not the requested 7120e2c build.

## Installer attempt and failure

Exact host command:

```powershell
$expected='7120e2c647cc95703704905efa76de735ca8d0ec'
& .\tools\qa\install_wsl_runtime.ps1 -ExpectedHead $expected -Distribution 'Ubuntu-24.04'
```

Observed PowerShell exception from `tools/qa/install_wsl_runtime.ps1:304`:

```text
WSL source deployment failed with exit code 2:
/run/vst-deploy-7120e2c647cc95703704905efa76de735ca8d0ec-21e34c1dc3b144b3aa925c494c384204/tools/qa/install_wsl_worker_helper.sh: 2: set: Illegal option -
source bundle retained at /run/vst-deploy-7120e2c647cc95703704905efa76de735ca8d0ec-21e34c1dc3b144b3aa925c494c384204; preserve it, do not delete host state; retry uses a fresh transfer ID
No pre-existing destination was removed or overwritten.
```

The WSL stderr was surfaced by the PowerShell exception rather than separately saved. The original
installer stated that the source bundle was retained. A subsequent read-only `find /run ...` showed
no matching stage directory; no manual deletion was performed. The existing helper still reported
its previous build identity, `/opt/vst-runtime` was absent, and the three units were not found.

## Root-cause evidence

The installer invokes this WSL-side argv through its Python bootstrap:

```text
['/bin/sh', '<stage>/tools/qa/install_wsl_worker_helper.sh', '<HEAD>', '<stage>', '<archive SHA-256>']
```

Read-only checks:

```text
git check-attr -a -- tools/qa/install_wsl_worker_helper.sh
=> tools/qa/install_wsl_worker_helper.sh: text: auto

git config --show-origin --get core.autocrlf
=> file:C:/Program Files/Git/etc/gitconfig true
```

Repository `.gitattributes` contains `* text=auto`; it has no explicit `*.sh eol=lf` rule. No
filter attribute applies to this path. Raw committed blob SHA-256 is
`ef14f99d1eed7b3af6624015c55404ea1927bec2387e53c5cc67fe749a5cf1cc`, beginning
`#!/bin/sh\nset -eu\n`, with zero CRLF or bare-CR bytes.

Read-only reproduction command:

```text
git --no-replace-objects archive --format=tar 7120e2c647cc95703704905efa76de735ca8d0ec -- tools/vst tools/qa/install_wsl_runner_runtime.sh tools/qa/install_wsl_worker_helper.sh tools/qa/worker_exec.c docs/SANDBOX_SPEC.md
```

The archive SHA-256 was `cd89ea7c78b5a9335562af4bb889cf67b70d9c35923173d477df7e16cac597e6`
(890880 bytes). The `install_wsl_worker_helper.sh` archive member SHA-256 was
`cd3031fab777bf286876087058cc613788499c69d62c5d97632a1fcbbe592bc1` (7332 bytes): line 2 was
`set -eu\r\n`, with 149 CRLFs. The `install_wsl_runner_runtime.sh` archive member also contained
CRLF (`e6a79e9a58e4b5930a0aae57d106fbda29aff10e7b2b09d8f6517388d704be38`, 10168 bytes, 190
CRLFs). This directly explains the shell's rejection. A separate harmless WSL diagnostic
`/bin/sh -c 'set -eu; printf shell_ok'` succeeded, ruling out a general `/bin/sh` option problem.

The retained stage was absent, so its extracted bytes could not be inspected. The root-cause finding
is based on deterministic archive-member bytes at the exact committed head, not a claim about the
now-absent staged copy. Do not claim system/runtime acceptance until archive export is corrected,
the revised exact HEAD is installed, and permitted E2E evidence is collected. Keep process-kill,
crash/recovery, mutation, E8, policy selectors, and fresh run-bound E5 signing `NOT_RUN`.

## Required follow-up

Codex owns a narrow archive line-ending correction and exact-head installer retry after code review
and tests. The e2e-runner owns subsequent permitted system-boundary evidence. GPT-PM owns final
exact-head adjudication. An actual run-bound operator E5 signature remains the operator's
attestation; it must not be inferred from this snapshot.
