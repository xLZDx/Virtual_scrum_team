# S2 Runtime Bundle Inventory — 2026-10-29

## Scope and provenance

This is a point-in-time, read-only inventory of the already-existing `Ubuntu-24.04` WSL distribution for the S2 runtime bundle at repository `HEAD` `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`. The observations were collected on 2026-10-29; command output did not include a reliable local timestamp, so no time-of-day is claimed.

The initial repository status was:

```text
 M docs/sdlc/STATE.md
?? docs/sdlc/evidence/s2-functional-test-run.md
?? docs/sdlc/requirements.md
?? docs/sdlc/state.json
```

The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not opened or changed. This inventory does not assert that the listed WSL state was created by this task.

## Identity and collision observations

Existing named accounts:

```text
vst-runner:x:997:988::/nonexistent:/usr/sbin/nologin
vst-signer:x:995:987::/nonexistent:/usr/sbin/nologin
vst-supervisor:x:994:986::/nonexistent:/usr/sbin/nologin
vst-worker:x:999:989::/nonexistent:/usr/sbin/nologin
vst-reviewer:x:993:985::/nonexistent:/usr/sbin/nologin
```

Named accounts `vst-dispatcher`, `vst-dispatch-owner`, and `vst-supervisor-client` returned no `getent passwd` records. Candidate UID lookup for `980` and `981` returned no records. Candidate GID lookup for `982`, `983`, and `984` returned no records. These IDs were unassigned at observation time; this is not a reservation and must be rechecked immediately before any authorized provisioning.

Existing groups:

```text
vst-runner:x:988:vst-signer
vst-signer:x:987:vst-runner
vst-supervisor:x:986:
vst-worker:x:989:
vst-reviewer:x:985:
```

## Runtime and service manager

```text
PID1=systemd
6.6.114.1-microsoft-standard-WSL2
Python 3.12.3
OpenSSL 3.0.13 30 Jan 2024 (Library: OpenSSL 3.0.13 30 Jan 2024)
running
```

The last line is `systemctl is-system-running`. The runtime is WSL2 Linux kernel `6.6.114.1-microsoft-standard-WSL2`; systemd is PID 1 and reported `running`.

Unit metadata from `systemctl show <unit> -p LoadState -p ActiveState -p SubState --no-pager`:

| Unit | LoadState | ActiveState | SubState |
|---|---|---|---|
| `vst-supervisor.service` | loaded | inactive | dead |
| `vst-runner.service` | loaded | inactive | dead |
| `vst-worker.service` | not-found | inactive | dead |
| `vst-signer.service` | loaded | inactive | dead |
| `vst-reviewer.service` | not-found | inactive | dead |
| `vst-dispatcher.service` | not-found | inactive | dead |
| `vst-dispatch-owner.service` | not-found | inactive | dead |
| `vst-supervisor-client.socket` | not-found | inactive | dead |

No unit was activated during this inventory.

## Paths and metadata

`stat -c "%n|%F|%U:%G|%a|%s"` returned:

```text
/etc/vst-runner|ABSENT
/run/vst-supervisor|ABSENT
/run/vst-runner|ABSENT
/var/lib/vst|directory|root:root|700|4096
/var/lib/vst/keys|directory|root:root|700|4096
/opt/vst-runtime|symbolic link|root:root|777|57
/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976|directory|root:root|755|4096
```

`readlink -e /opt/vst-runtime` resolved to `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. Dereferenced metadata for `/opt/vst-runtime` was `directory|root:root|755|4096`. The observed symlink target is the older `d5001797...` runtime directory, not evidence that the current S2 bundle is installed.

Immediate `/var/lib/vst` entries were listed by name, type, mode, UID and GID only:

```text
private-e5-boundary-observation-591249434bde4989b6d320bf3675fe20.json|file|0600|0:0
private-e5-source-snapshot-03af03d387eb4187a5a9c73e734ca274|dir|0755|0:0
private-e5-provisioning-evidence-591249434bde4989b6d320bf3675fe20.json|file|0600|0:0
private-e5-operator-attestation-591249434bde4989b6d320bf3675fe20.json|file|0600|0:0
s4-qa|dir|2710|997:989
private-e5-boundary-observation-7bd767da9074424e8a32fc5a5b6e9d4b.json|file|0600|0:0
private-e5-final-inventory-591249434bde4989b6d320bf3675fe20.json|file|0600|0:0
evidence|dir|0700|0:0
private-e5-final-inventory-8024493e38ba44df96ee5f127a24b338.json|file|0600|0:0
```

Immediate `/var/lib/vst/keys` entry metadata, without opening file contents:

```text
operator|directory|0700|root:root
worker|directory|0700|vst-worker:vst-worker
event|directory|0700|vst-supervisor:vst-supervisor
supervisor|directory|0700|vst-supervisor:vst-supervisor
reviewer|directory|0700|vst-reviewer:vst-reviewer
```

No key bytes or file contents were read. No clearly identified SQLite Store database was present among the immediate `/var/lib/vst` entries. Consequently, Store disposition is **UNKNOWN**: this inventory does not establish either fresh initialization or an existing database requiring migration. No SQLite file was opened and no schema query was run.

## Commands and method

Commands were run from the S2 repository root using the existing WSL distribution. All WSL commands were read-only.

```sh
git rev-parse HEAD
git status --short
```

```sh
getent passwd vst-runner
getent passwd vst-signer
getent passwd vst-supervisor
getent passwd vst-worker
getent passwd vst-reviewer
getent passwd vst-dispatcher   # no record returned
getent passwd vst-dispatch-owner # no record returned
getent passwd vst-supervisor-client # no record returned
getent passwd 980              # no record returned
getent passwd 981              # no record returned
getent group 982               # no record returned
getent group 983               # no record returned
getent group 984               # no record returned
getent group vst-runner
getent group vst-signer
getent group vst-supervisor
getent group vst-worker
getent group vst-reviewer
```

```sh
cat /proc/1/comm
uname -r
python3 --version
openssl version
systemctl is-system-running
```

```sh
systemctl show vst-supervisor.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-runner.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-worker.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-signer.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-reviewer.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-dispatcher.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-dispatch-owner.service -p LoadState -p ActiveState -p SubState --no-pager
systemctl show vst-supervisor-client.socket -p LoadState -p ActiveState -p SubState --no-pager
```

```sh
stat -c '%n|%F|%U:%G|%a|%s' \
  /etc/vst-runner /run/vst-supervisor /run/vst-runner \
  /var/lib/vst /var/lib/vst/keys /opt/vst-runtime \
  /opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976
readlink -e /opt/vst-runtime
stat -Lc '%n|%F|%U:%G|%a|%s' /opt/vst-runtime
```

The `/var/lib/vst` inventory used `os.scandir` plus `os.lstat` for immediate entries and `find -mindepth 1 -maxdepth 1` limited to names/types/modes/owners in `keys`; it did not read file contents or recurse elsewhere.

## Acceptance and next action

This artifact supplies fresh environmental metadata only. It does not provision accounts, reserve candidate IDs, establish trusted runtime provenance, prove the current bundle installed, classify the Store as fresh or migratable, authorize service activation, or satisfy S2 functional acceptance. Before provisioning, Codex should recheck the observed UID/GID candidates, resolve Store disposition using the authorized S2 procedure, and compare the installed runtime target against the exact reviewed S2 bundle. Restricted process/crash/mutation and policy-selector scenarios remain outside this inventory and must retain their separately recorded `NOT_RUN` state.
