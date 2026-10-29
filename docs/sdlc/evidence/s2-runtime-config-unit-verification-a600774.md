# S2 runtime configuration static unit verification

## Scope and result

This is a read-only static integration check of the prepared `docs/sdlc/runtime-config` bundle against the already staged source tree for `a600774649527ff0b33eb81f4d431f8226119b2c`. It did not install or activate any configuration, create accounts/groups, install units, reload systemd, start services, run bootstrap/issuer/probe operations, execute tests, or read private-key bytes. The only filesystem writes were temporary copies under WSL `/tmp` for `systemd-analyze verify`; the temporary directory was removed when that command returned.

The three new configuration units parsed successfully. The combined check returned code `0`, but emitted three nonfatal warnings in the six existing staged source units: `StartLimitIntervalSec` appears under `[Service]` and is ignored there. The warning does not come from the three new candidate units. No original source unit was edited in this task.

## Repository and staged-source identity

- Checkout observed during review: branch `s2-canonical-continuation`, `HEAD` `9021b98d6458cb09d7ea1d35942661ff1fee9587`.
- Runtime source staged for verification: `/opt/vst-runtime-a600774649527ff0b33eb81f4d431f8226119b2c`.
- New candidate bundle state in `bundle-manifest.json`: `PREPARED_NOT_INSTALLED`; manifest states that installation does not start services and that the runtime is selected before configuration is installed.
- The candidate files and bundle remain worktree inputs; this report does not claim a configuration install or a live runtime test.

## Candidate unit hashes and identity/command mapping

Each of the three candidate unit SHA-256 values matched its corresponding `files[]` entry in `bundle-manifest.json` at inspection time.

| Candidate unit | Candidate identity and supplementary group | Source-config identity | `ExecStart` contract |
| --- | --- | --- | --- |
| `vst-assignment-bootstrap.service` | `vst-assignment-bootstrap:vst-assignment-bootstrap`, supplementary `vst-supervisor-client` | `identity-candidates.json`: UID:GID `978:980`; `supervisor-service.json` peer `assignment_bootstrap`: UID:GID `978:980`; shared socket group GID `984` | Isolated Python 3.12 (`-I -S`, then `-c`) reads `/etc/vst-runner/bootstrap-request.json` and calls `SupervisorClient(...).call('bootstrap_assignment', body)`. The request file is listed for root:`vst-assignment-bootstrap` group (`0:980`) mode `0640`. |
| `vst-dispatch-issuer.service` | `vst-dispatch-issuer:vst-dispatch-issuer`, supplementary `vst-supervisor-client` | `identity-candidates.json`: UID:GID `979:981`; `supervisor-service.json` peer `delegated_issuer`: UID:GID `979:981`; shared socket group GID `984` | Isolated Python 3.12 (`-I -S`, then `-c`) reads `/etc/vst-runner/issuance-request.json` and calls `SupervisorClient(...).call('issue_root_dispatch_instruction', body)`. The layout declares this request as a runtime-derived file for root:`vst-dispatch-issuer` group (`0:981`) mode `0640`, sourced from the actual successful bootstrap response. |
| `vst-sandbox-probe.service` | `vst-worker:vst-worker`; no supplementary group | `probe-entrypoint.py` requires effective UID:GID `999:989`; the source helper and runtime plan use the same worker identity | Isolated Python 3.12 (`-I -S`) executes `/etc/vst-runner/probe-entrypoint.py`; that path is installed root-owned mode `0644` by the candidate layout. The entrypoint reads the bounded probe request and measured root policy attestation, then calls `collect_inventory`. |

The `supervisor_service.py` implementation at the staged source revision exposes the two operations named by the candidate commands. The source probe module exposes `collect_inventory`. The new unit hashes observed from the candidate files and matched against the bundle manifest were:

```text
vst-assignment-bootstrap.service  e714fb88699ae07fbd96ccd8758cb58d1db8bcf075d52145c6e8a3ec8931f43f
vst-dispatch-issuer.service       d798f141e33d15444afccb1ac26213665571f19e70f1dc61fbd7f60b23140c7d
vst-sandbox-probe.service         d80c171238985ffcc7f19c6eac74276c7ea7615ebf85d63391b6f2dbf097f33f
```

A supplementary POSIX `shlex.split` inspection of each candidate `ExecStart` produced one `-c` code argument for bootstrap and issuer, with the full inline Python code retained as that one argument. All three parsed command vectors used `/usr/bin/python3.12 -I -S`. This supplemental tokenization check is not presented as a substitute for the systemd parser.

The post-stage read-only systemd state query remained: `vst-runner.service`, `vst-signer.service`, and `vst-supervisor.service` were `loaded/inactive/dead`; `vst-dispatcher.service`, `vst-dispatch-owner.service`, and `vst-dispatch-owner.socket` were `not-found/inactive/dead`. The three new candidate units were not installed.

## Live identity availability observed

A fresh read-only lookup in Ubuntu 24.04 WSL showed the new candidate numeric identities are not provisioned: UIDs `978` and `979` were unassigned; GIDs `980`, `981`, `982`, `983`, and `984` were unassigned. Existing worker identities were present as UID:GID `999:989`; runner group GID `988` was present. Consequently, this check confirms that unit names and static IDs agree with the prepared source configuration, but it does not prove the new service identities can be resolved at runtime. No account or group was created.

The lookup used the Python `pwd`/`grp` databases read-only in Ubuntu 24.04 WSL for UIDs `[978, 979, 980, 981, 997, 999]` and GIDs `[980, 981, 982, 983, 984, 988, 989]`. Its observed result was:

```json
{"groups":{"980":{"state":"UNASSIGNED"},"981":{"state":"UNASSIGNED"},"982":{"state":"UNASSIGNED"},"983":{"state":"UNASSIGNED"},"984":{"state":"UNASSIGNED"},"988":{"gid":988,"members":["vst-signer"],"name":"vst-runner"},"989":{"gid":989,"members":[],"name":"vst-worker"}},"users":{"978":{"state":"UNASSIGNED"},"979":{"state":"UNASSIGNED"},"980":{"state":"UNASSIGNED"},"981":{"state":"UNASSIGNED"},"997":{"gid":988,"name":"vst-runner","uid":997},"999":{"gid":989,"name":"vst-worker","uid":999}}}
```

A separate name lookup confirmed the new service names and shared client group are absent, while the worker and runner identities resolve as configured:

```json
{"vst-assignment-bootstrap":{"group":{"state":"ABSENT"},"user":{"state":"ABSENT"}},"vst-dispatch-issuer":{"group":{"state":"ABSENT"},"user":{"state":"ABSENT"}},"vst-runner":{"group":{"gid":988,"members":["vst-signer"],"state":"PRESENT"},"user":{"gid":988,"state":"PRESENT","uid":997}},"vst-supervisor-client":{"group":{"state":"ABSENT"},"user":{"state":"ABSENT"}},"vst-worker":{"group":{"gid":989,"members":[],"state":"PRESENT"},"user":{"gid":989,"state":"PRESENT","uid":999}}}
```

## Commands and exact systemd verification output

Systemd version query:

```text
wsl.exe -d Ubuntu-24.04 -u root -- systemd-analyze --version
```

Observed first line: `systemd 255 (255.4-1ubuntu8.17)`.

The verification harness copied the three new candidate units from the worktree and the six existing source units from the staged `a600774…` runtime into one temporary WSL directory, set `SYSTEMD_UNIT_PATH` to that directory followed by the existing system unit paths, and ran this exact `systemd-analyze` argument vector (the temporary directory name is the one printed by the completed run):

```text
/usr/bin/systemd-analyze verify \
  /tmp/s2-systemd-verify-92ku5hby/vst-supervisor.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-signer.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-runner.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-dispatcher.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-dispatch-owner.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-dispatch-owner.socket \
  /tmp/s2-systemd-verify-92ku5hby/vst-assignment-bootstrap.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-sandbox-probe.service \
  /tmp/s2-systemd-verify-92ku5hby/vst-dispatch-issuer.service
```

The Python harness returned exit code `0`; `stdout` was empty and `stderr` was:

```text
/tmp/s2-systemd-verify-92ku5hby/vst-supervisor.service:17: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
/tmp/s2-systemd-verify-92ku5hby/vst-runner.service:24: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
/tmp/s2-systemd-verify-92ku5hby/vst-signer.service:20: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
```

These are existing source-template warnings for the six staged base units. They are nonfatal to the parser result but mean that the explicit start-rate settings in those three `[Service]` sections are ignored. No rate-limit drop-ins were part of this static input set or applied here; the source units were not edited or re-staged.

## Acceptance boundary

Static config hashes, Python `ExecStart` quoting shape, and identity/group names/IDs were cross-checked. `systemd-analyze verify` parsed all nine candidate-plus-source units successfully with the warnings above. The new accounts/groups are absent and the repository candidate configuration remains uninstalled. The separate stage evidence record [s2-4-pidfd-stage-a600774.md](s2-4-pidfd-stage-a600774.md) reports `selected=false` and the unchanged older selector target. No systemd unit was installed, enabled, started, stopped, or reloaded. No private-key bytes, private preparation directory, live `/etc/vst-runner` runtime configuration, selector, or Store were read or changed. The repository candidate configuration was read for this static check but not modified. No real bootstrap, issuer, sandbox probe, or test suite was run. The result is static unit/config evidence, not runtime acceptance.

## Supplemental rate-limit drop-in recheck

After the three deployment-only rate-limit drop-ins were added to the candidate bundle, a second static parse included them under the matching unit drop-in directories. The bundle still identifies runtime source `a600774649527ff0b33eb81f4d431f8226119b2c`, remains `PREPARED_NOT_INSTALLED`, and lists 32 files. The checkout HEAD observed for this recheck remained `9021b98d6458cb09d7ea1d35942661ff1fee9587` on `s2-canonical-continuation`; the updated bundle files were worktree inputs. No claim is made that a Git revision `2fc8a99` was checked out.

The three drop-ins have these exact values and each actual SHA-256 matched its `bundle-manifest.json` entry:

```ini
[Unit]
StartLimitIntervalSec=60s
StartLimitBurst=3
```

```text
unit-overrides/vst-supervisor.service.d/rate-limits.conf  c0ae4900c88e6c9e4b57a5bf10d1fa7b637ea76e03b44aaa7c8efa8a9cb9a590
unit-overrides/vst-runner.service.d/rate-limits.conf      c0ae4900c88e6c9e4b57a5bf10d1fa7b637ea76e03b44aaa7c8efa8a9cb9a590
unit-overrides/vst-signer.service.d/rate-limits.conf       c0ae4900c88e6c9e4b57a5bf10d1fa7b637ea76e03b44aaa7c8efa8a9cb9a590
```

The check copied the six staged source units, the three candidate units, and the three candidate drop-ins into a disposable WSL temporary unit search directory. `SYSTEMD_UNIT_PATH` put that directory first, followed by existing system unit paths. It invoked `systemd-analyze verify` by unit name so matching `.service.d` drop-ins were found through the unit search path. The actual argument vector was:

```text
/usr/bin/systemd-analyze verify vst-supervisor.service vst-signer.service vst-runner.service vst-dispatcher.service vst-dispatch-owner.service vst-dispatch-owner.socket vst-assignment-bootstrap.service vst-dispatch-issuer.service vst-sandbox-probe.service
```

For this invocation, `SYSTEMD_UNIT_PATH` was:

```text
/tmp/s2-systemd-byname-29tnd3lz:/etc/systemd/system:/usr/local/lib/systemd/system:/usr/lib/systemd/system:/lib/systemd/system
```

The temporary fixture was cleaned after command completion. The WSL process returned `0`; `stdout` was empty and `stderr` remained exactly the three existing-base-unit warnings already recorded above:

```text
/tmp/s2-systemd-byname-29tnd3lz/vst-supervisor.service:17: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
/tmp/s2-systemd-byname-29tnd3lz/vst-runner.service:24: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
/tmp/s2-systemd-byname-29tnd3lz/vst-signer.service:20: Unknown key name 'StartLimitIntervalSec' in section 'Service', ignoring.
```

An initial disposable-fixture attempt placed the new candidate service files one directory below the unit search root. That attempt returned `1` and said the three candidate units were not found. The fixture layout was corrected; the successful by-name invocation above found and parsed all nine unit files and the three drop-ins. This was a harness path correction; no source/config file was changed as a result.

The successful verification shows the candidate drop-in syntax is accepted alongside the staged base units. It does not prove effective properties in the live systemd manager because the drop-ins and candidate configuration remain uninstalled. Any later assertion of effective `StartLimitIntervalUSec`/`StartLimitBurst` must be made after its separately authorized installation. No source/runtime tree rebuild, service activation, enablement, unit-file write, reload, test rerun, private-key read, or configuration installation occurred in this recheck.
