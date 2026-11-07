# S2 compiler and runner-data metadata inventory

Date: 2026-10-29

## Scope

- Project checkout: `D:\Repo\Virtual_scrum_team`.
- Frozen committed source HEAD: `c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`.
- Target inspected: the dedicated `Ubuntu-24.04` WSL2 distribution only.
- Read-only scope: exact path `/usr/bin/cc` and exact path `/var/lib/vst-runner`. The latter's directory entry was inspected only; its contents were not listed or opened. No `/etc/vst-runner` file, key, Store file, sibling path, or recursive directory contents were read.

## Compiler metadata

`/usr/bin/cc` is a symlink to `/etc/alternatives/cc`, resolving to `/usr/bin/x86_64-linux-gnu-gcc-13`. The resolved target is a root-owned, root-group regular file with mode `0755`, ELF magic `7f454c46`, and SHA-256 `1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26`. `/usr/bin/cc --version` returned exit code 0 and first line `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.

The direct read-only command was executed as Python 3.12.3 in the named distro, as root, using stdin and no mount:

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -I -S -c "import sys; exec(sys.stdin.read())"
```

The stdin script called `lstat`, `realpath`, `stat`, read the resolved compiler's bytes to compute SHA-256, and ran only `/usr/bin/cc --version`. It did not compile or build anything. Exact captured compiler facts:

```json
{"path":"/usr/bin/cc","state":"PRESENT","lstat_type":"symlink","lstat_uid":0,"lstat_gid":0,"lstat_mode":"0777","symlink_target":"/etc/alternatives/cc","resolved_path":"/usr/bin/x86_64-linux-gnu-gcc-13","target_type":"regular-file","target_uid":0,"target_gid":0,"target_owner":"root","target_group":"root","target_mode":"0755","magic":"7f454c46","sha256":"1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26","version_exit_code":0,"version_first_line":"cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0"}
```

## Runner config/unit metadata and old selector

Only the fixed unit/config paths declared by the source were checked; no directory was enumerated and no configuration content was opened.

| Exact path | State and metadata |
|---|---|
| `/etc/systemd/system/vst-supervisor.service` | Present, `root:root`, mode `0644`, 886 bytes; SHA-256 `aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c`. |
| `/etc/systemd/system/vst-signer.service` | Present, `root:root`, mode `0644`, 1020 bytes; SHA-256 `33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d`. |
| `/etc/systemd/system/vst-runner.service` | Present, `root:root`, mode `0644`, 1605 bytes; SHA-256 `4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be`. |
| `/etc/systemd/system/vst-dispatcher.service` | Absent. |
| `/etc/systemd/system/vst-dispatch-owner.service` | Absent. |
| `/etc/systemd/system/vst-dispatch-owner.socket` | Absent. |
| `/etc/vst-runner/runner-service.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/supervisor-service.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/signer-service.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/dispatcher-service.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/dispatch-owner-service.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/fence.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/assignment-delegation-policy.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/dispatch-instruction-trust.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/machine-delegation-trust.json` | Absent; metadata only, contents not read. |
| `/etc/vst-runner/dispatch-owner-admission-blocked.json` | Absent; metadata only, contents not read. |
| `/opt/vst-runtime` | Present root-owned symlink mode `0777`, target `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. |
| `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976` | Present root-owned directory mode `0755`; no recursive fingerprint was performed. This path suffix is an observation from the symlink target, not verified source provenance. |
| `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976/.vst-runtime-manifest.json` | Present, `root:root`, mode `0644`, 146 bytes; contents not read. |
| `/var/lib/vst-runner` | Absent (`lstat` returned `ENOENT`); no child path was enumerated. |

Supervisor obtains `store_path` from its root-owned service configuration (`tools/vst/supervisor_service.py:700, 727, 885-919`; `tools/vst/systemd/README.md:96`). That configuration and any configured Store path were not read. The absence of `/var/lib/vst-runner` does not establish a configured Store's presence, absence, or freshness; Store disposition remains **UNKNOWN**.

The non-secret systemd unit hashes above are current file fingerprints, not service activation evidence. No systemd active/enabled commands were run.

## Windows handoff runtime

`Get-Command pwsh -ErrorAction SilentlyContinue` resolved `C:\Program Files\PowerShell\7\pwsh.exe`, command version `7.6.9.0`. A headless, non-interactive `pwsh -NoLogo -NoProfile -NonInteractive -Command '$PSVersionTable | ConvertTo-Json -Compress; [System.Runtime.InteropServices.RuntimeInformation]::FrameworkDescription'` reported PowerShell `7.6.9` (`PSEdition=Core`) and `.NET 10.0.14`. This is the PowerShell 7 host family required by the handoff's `ProcessStartInfo.ArgumentList` and `Convert.ToHexString` usage. The installer was not run.

No service, systemd unit, cgroup, Store, E5 provenance, runtime tree, or configuration was changed. No compiler installation, activation, or network probe was performed.

## Unsigned source staging candidate

The canonical source-plan utility was invoked with the full frozen revision and its stdout was saved as [s2-runtime-staging-plan-20261029.json](s2-runtime-staging-plan-20261029.json) (SHA-256 `DA7F39095B1944E3B2F040641CCFB7A7E0D3AC45362AF6BA5CA0403D9A270B2D`):

```powershell
python tools/qa/prepare_wsl_runtime_plan.py --expected-head c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0
```

The script verified the current canonical checkout HEAD and emitted an `UNSIGNED_REVIEW_CANDIDATE`; it does not stage files or grant authorization. Captured plan fields: `source_head=c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`, `archive_sha256=93449cac19103cd1fbd6c13982933135da0e2f3389bd5c05f976e9c84b85ed51`, `target_inventory=NOT_VERIFIED`, `helper.compiler_provenance=NOT_VERIFIED`, `store_disposition=UNKNOWN`, and `activation=NOT_AUTHORIZED_BY_THIS_PLAN`. Staging still requires separate exact-plan review and source/test approval.

This plan is bound to source HEAD `c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`. Any later HEAD change, including a documentation-only commit, requires regenerating the plan for the exact intended staging revision; this candidate is not an installation or approval artifact.
