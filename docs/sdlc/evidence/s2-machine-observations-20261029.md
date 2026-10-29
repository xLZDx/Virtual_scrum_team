# S2 machine observation collection record

Date: 2026-10-29. These are **unsigned observations**, not a firewall verdict, E5 attestation, or production approval.

## Source identity

- Requested source was commit `3d5f6c2048238a79fb92ddf805bc562b4b392a63`. The checkout advanced to `6a6d7886746379e2b68218bd8d4fba01edf0bf56` before collection. The collector file blob is identical at both commits (`1458bdc64fc4effcab4e42cf52bef5219793d429`), and the working collector was clean.
- Collector: `tools/vst/machine_observations.py`, SHA-256 `5e613f36cf43ddc6272a410bebcb8301f97014499662b10df12c6ce9a9a41f21`.
- WSL source payload: `git archive --format=tar HEAD -- tools/vst`, SHA-256 `3612a5f959f1653f0965b4c2eda2e4ffad21da130afbb9503837bd02c731e8db`. It was relayed over stdin; no drive mount, checkout, or interop was used to load the collector in the guest.
- The collector contract calls the sources `VST_S2_WINDOWS_HOST_OBSERVATION_V1` and `VST_S2_WSL_GUEST_OBSERVATION_V1`. No signed receipt or observation evaluation was created.

## Collection matrix

| Source | Result and evidence | Remaining limitation | Next action and owner |
|---|---|---|---|
| Windows fixed collector | `collection_complete=false`; 2 `UNKNOWN` errors; it returned no command output. Canonical observation SHA-256 `2fe699e6e5fa584c92595211cc3e6216a3bf1342a0622ac85a6ef11c64dd33c5`. Private raw record SHA-256 `530964784e15e31f2d5394609c1e667947cd8d757851fc05a8b322b9e9d595d0`, 1877 bytes, at `.git/vst-private-evidence/ed7ff0b7952247cfa3684a537b064b6d.json`. | The fixed collector's Windows PowerShell 5.1 process failed to start its managed host (`8009001d`). Firewall rule/profile counts are unavailable; zero output is not evidence of zero rules. The contract normalizer is separately `UNKNOWN` because complete effective-rule normalization is not implemented (`machine_observations.py:164-205`). | Codex: decide whether to repair the fixed PowerShell host boundary. Keep the Windows source `UNKNOWN` until a complete bounded collection and reviewed normalization are available. |
| Windows PowerShell 7 limited native snapshot | `Get-Command` introspection found `Get-CimInstance` and the NetSecurity profile/rule/filter and Hyper-V cmdlets, with 0 introspection errors. The limited read-only CIM/ActiveStore-profile query succeeded: 3 profile records, 1 Hyper-V profile record. Private raw record SHA-256 `2a3827094f764cf85786b3b10112167bd4b4c4e94513c87b00634a2bd2018055`, 1509 bytes, at `.git/vst-private-evidence/windows-pwsh7-profile-c93425d91fd047cb84b3f4c0d53e9206.json`. | This is a separate, unsigned partial diagnostic; it is not the fixed collector receipt and has no rule inventory or effective-policy evaluation. A broader read-only PowerShell 7 rule/filter snapshot exceeded 60 seconds and timed out; it produced no retained snapshot. | Codex: use only after reviewing the collector host issue and its runtime bound. Do not interpret profile counts as policy acceptance. |
| WSL guest fixed collector | `collection_complete=true`; 0 collector errors; Ubuntu `24.04`, kernel `6.6.114.1-microsoft-standard-WSL2`, collector UID/GID `0:0`; container-socket inventory complete with 0 paths; 0 Windows-drive mounts; WSL interop absent/disabled. Sanitized line counts: nftables 10, IPv4 routes 9, IPv6 routes 4, IPv4 rules 3, IPv6 rules 2, namespaces 18, interfaces 14, mounts 31, listeners 13. Canonical observation SHA-256 `ce376812574a931236fd03e059056419e97bb0c833cee86b7d6cbd57b320e2e4`. | Guest collection completeness does not authenticate its source or prove effective Windows/WSL policy. Raw details are intentionally excluded here. | GPT-PM: adjudicate the observation contract and normalization scope. Codex: retain this only as unsigned guest evidence. |
| E5 / cross-source verdict | `UNKNOWN`; no signed receipt, human attestation, or evaluator result was produced. | Windows fixed collection failed and Windows normalization remains unsupported; WSL data alone cannot establish the cross-source policy. | GPT-PM: review the evidence contract after a complete Windows source is available. |

## Commands and wrappers

Windows collector identity and hidden-process adapter:

- Called `collect_windows_observations()` programmatically from repository-root Python; no caller-supplied command was accepted.
- The fixed source argv is `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Restricted -Command <embedded fixed collector script>` (`machine_observations.py:164-205`). Its `Popen` adapter added `CREATE_NO_WINDOW=134217728` only for that child. The raw source record was kept private; public fields above omit stderr beyond the sanitized startup error code.

Separate native diagnostic, after `Get-Command` introspection:

- `C:\Program Files\PowerShell\7\pwsh.exe -NoLogo -NoProfile -NonInteractive -Command <fixed read-only CIM/ActiveStore-profile script>` with `CREATE_NO_WINDOW=134217728`.
- `Get-Command pwsh` selected that PowerShell 7 executable, version `7.6.9.0`; its headless `$PSVersionTable` reported PowerShell `7.6.9` and `.NET 10.0.14`.
- The available cmdlets were `Get-CimInstance` from `CimCmdlets`, plus `Get-NetFirewallProfile`, `Get-NetFirewallRule`, address/port/application filters, and Hyper-V settings/rules from `NetSecurity`. Introspection command errors: 0.
- The successful limited script queried only `Get-CimInstance Win32_OperatingSystem`, `Get-NetFirewallProfile -PolicyStore ActiveStore`, and `Get-NetFirewallHyperVVMSetting`. It did not return rule content in this public record. The wider rule/filter query timed out at 60 seconds; this is recorded as `UNKNOWN`, not retried.

WSL guest collection:

- Outer command: `wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -B -I -S -c <stdin source-archive bootstrap and private courier>`.
- The fixed guest collector runs `/usr/sbin/nft list ruleset`; `/usr/sbin/ip -4 route show table all`; `/usr/sbin/ip -6 route show table all`; `/usr/sbin/ip -4 rule show`; `/usr/sbin/ip -6 rule show`; `/usr/bin/lsns --noheadings --output NS,TYPE,PATH`; `/usr/sbin/ip -details address show`; and `/usr/bin/ss -H -lntup` (`machine_observations.py:244-293`). These are local read-only snapshots, not packet probes.
- At collection time the canonical raw record was written to `/run/vst-private-evidence/1d72703067cc4b1f918d3bf874bbf37b.json`, verified in-process as UID 0, mode `0600`, size 7978, record SHA-256 `f4030fb8fb293f8251a3cb943e278f996b1f7613eba18b0d6547c905013ccec4`. The raw observation SHA is the value in the WSL row above.
- A courier streamed those exact canonical record bytes to `.git/vst-private-evidence/wsl-1d72703067cc4b1f918d3bf874bbf37b.json`; the host copy has the same SHA-256 and size. A later read-only `stat` of the `/run` path returned `ENOENT` after the WSL invocation ended. No deletion command was issued. Because `/run` is volatile, the retained copy is the Windows-host file; it has an explicit current-user-only NTFS ACL and is **not** represented as Linux-root-owned. The original WSL path may disappear when that WSL instance stops.

## Privacy, provenance, and limits

- Raw firewall rules, addresses, application paths, interface and listener data, mount strings, namespace paths, and command stderr were not included in this report. They remain only in private raw records under `.git/vst-private-evidence/` where available. Files were excluded from the Git working tree/index; `icacls` applied an explicit current-user-only ACL to those host files (exit code 0). No usernames, SIDs, full rules, IP addresses, credentials, or raw command outputs are published here.
- WSL raw copy on Windows is a transport-preserved private copy, not an independently signed receipt. Its ACL/security boundary is Windows-host current-user access, not WSL root ownership. The transient `/run` path is not claimed to persist after WSL shutdown.
- No keys or Store data were read. No packet, network probe, firewall change, service operation, installation, provisioning, source mutation, signature, human attestation, or E5 PASS occurred.
- WSL `collection_complete=true` means the collector's bounded local observations completed without errors. The source's evaluator intentionally returns `UNKNOWN` for unsigned observations and unsupported policy normalization (`machine_observations.py:502-527`).
