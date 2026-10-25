# S4 worker capability probe and current-head snapshot

Date: 2026-10-25

## Source and runtime identity

- Repository: `Virtual_scrum_team-s4`; branch: `s4-native-qa-runner`.
- Windows source HEAD: `0aa7a53cdf7c4ad160ee40af00dd9743646a0b08`.
- WSL distribution: `Ubuntu-24.04`.
- Runtime identities recorded in the existing S4 WSL feasibility evidence: `vst-runner` UID/GID `997:988`, `vst-worker` `999:989`, `vst-signer` `995:987`.
- Operator selected dedicated WSL2 for S2 provisioning and explicitly authorized the narrow S4 runner-to-worker helper in the current task. The selection alone did not authorize S4; the later explicit S4 authorization did.

## Transient capability probe

The coordinator first ran a bounded `systemd-run` unit named `vst-s4-identity-probe-10252026` with `User=vst-runner`, `Group=vst-runner`, `AmbientCapabilities=CAP_SETUID CAP_SETGID`, `NoNewPrivileges=yes`, private network/devices, a strict filesystem view, 2 GiB memory, 64 tasks and a 30-second runtime cap. Its child printed UID `999`; this established only that the process could perform the requested identity transition. It did not inspect or prove capability removal.

The E2E test agent then ran a separate read-only security probe on the same source snapshot. Exact invocation:

```powershell
wsl.exe --distribution Ubuntu-24.04 --user root --exec bash -lc 'systemd-run --unit=vst-s4-capdrop-probe-final --collect --wait --pipe --property=Type=exec --property=User=vst-runner --property=Group=vst-runner --property=AmbientCapabilities="CAP_SETUID CAP_SETGID" --property=CapabilityBoundingSet="CAP_SETUID CAP_SETGID" --property=NoNewPrivileges=yes --property=PrivateNetwork=yes --property=PrivateDevices=yes --property=ProtectSystem=strict --property=ProtectHome=yes --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=30s /usr/bin/python3 /var/lib/vst-s4/qa-snapshots/28f9a8ea3833471e841ee113615d1db3/repo/.vst-qa-runs/capdrop_probe.py'
```

The probe script spawned `/usr/bin/python3` with `user=999, group=989, extra_groups=()`, read the child's `/proc/self/status` capability sets, then attempted `os.setuid(997)`. Output:

```text
Running as unit: vst-s4-capdrop-probe-final.service; invocation ID: cef3d18bae714213a1878c88e022297a
{"uid_before": 999, "uid_after": 997, "regained_runner_uid": true, "error": null, "caps": {"CapInh": "00000000000000c0", "CapPrm": "00000000000000c0", "CapEff": "00000000000000c0", "CapBnd": "00000000000000c0", "CapAmb": "00000000000000c0"}}
Finished with result: success
Main processes terminated with: code=exited/status=0
Service runtime: 164ms
CPU time consumed: 163ms
Memory peak: 2.3M
Memory swap peak: 0B
```

This confirmed a security defect in the ambient-capability-only mechanism: the worker retained `CAP_SETUID` and could become the runner, potentially crossing the signer boundary. The report-bound QA CLI was not run; no signer or manifest was created. The test agent's probe script is in the ignored per-run `.vst-qa-runs` directory of the WSL snapshot.

## Exact-head snapshot

The first destination attempt used `/var/lib/vst/s4-qa`, whose parent `/var/lib/vst` is root-only (`0700`). The transfer did not complete; the coordinator stopped the transfer process. This initial attempt is not accepted as a snapshot. Without changing that existing parent, a dedicated S4 location was created under the traversable `/var/lib` parent, with `/var/lib/vst-s4` as `root:root 0755` and `/var/lib/vst-s4/qa-snapshots` as `vst-runner:vst-worker 2710`.

Exact transfer command:

```powershell
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user vst-runner --worker-gid 989 --snapshot-root /var/lib/vst-s4/qa-snapshots
```

The tool returned `TRANSFERRED` for run ID `28f9a8ea3833471e841ee113615d1db3`, candidate HEAD `0aa7a53cdf7c4ad160ee40af00dd9743646a0b08`, bundle size `1,244,496` bytes and SHA-256 `aafffd2cb1ecbdf17968043dcbaf70f59b4d48c93dd3262ba380c99394b812f5`. Under `vst-runner`, `git rev-parse HEAD` returned the same HEAD and `git status --short` was empty. The run root was `vst-runner:vst-worker 2710`; its repository directory was `vst-runner:vst-worker 0750`.

## Remediation state and limitations

- At base HEAD `0aa7a53`, `implementation-engineer` (GPT-6 Luna, medium effort) added a POSIX-only trusted worker trampoline. `tools/vst/runner.py` invokes it after the OS identity transition; `tools/vst/worker_exec.py` checks the resulting UID/GID and empty supplementary groups, sets `PR_SET_NO_NEW_PRIVS`, clears ambient/effective/permitted/inheritable capabilities, verifies the cleared state, and execs the original manifest argv. Any failed check exits `126` before the manifest command runs.
- The implementer inspected the pinned CPython 3.12.3 `_posixsubprocess.c`: `setgroups`, `setregid`, and `setreuid` precede `preexec_fn`, but the runtime warns that `preexec_fn` can deadlock in threaded programs. The implementation therefore uses an isolated `python -I -S` trampoline rather than `preexec_fn`.
- This source change is not yet runtime-verified. No QA tests or CLI report-bound run were executed against it. The one `git diff --check` the implementer ran was against an earlier draft, before a final correction; it is not evidence for the current diff.
- The staged snapshot and capability probe above predate the remediation. A fresh clean exact-head snapshot and test-agent verification are required before another QA runner attempt.
- A trusted S4 signer service, run-specific v2 manifest, registered report-bound E2E selector, signed report/receipt consumption, and aggregate regression run remain unverified. The synthetic capability probe does not provide any of those.
