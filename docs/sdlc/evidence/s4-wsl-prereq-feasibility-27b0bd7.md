# S4 WSL prerequisite feasibility audit at 27b0bd7

Date: 2026-10-25

- Repository: `Virtual_scrum_team-s4`; branch `s4-native-qa-runner`.
- Exact repository HEAD observed before and after the read-only audit: `27b0bd71fbc239ec5d3fe368c530a5c6044e4c57`.
- Executor: `e2e-runner`, GPT-6 Luna, low effort. No tests ran, no configuration or source staging occurred, and no key material was read or invoked.
- Scope was limited to the named project distro `Ubuntu-24.04` and S4 source/design/evidence.

## Runtime and identity observations

Read-only command (no source files or secrets):

```text
wsl.exe --distribution Ubuntu-24.04 --user root --exec bash -lc 'cat /etc/os-release; /usr/bin/python3 --version; /usr/bin/python3 -m pytest --version 2>&1; for u in vst-runner vst-worker vst-signer; do getent passwd "$u" | cut -d: -f1,3,4; done; systemctl show vst-run.slice -p LoadState -p CPUQuotaPerSecUSec -p MemoryMax -p TasksMax --no-pager; systemctl is-active vst-signer.service; systemctl show vst-signer.service -p LoadState -p ActiveState -p User -p Group -p RuntimeDirectory -p RuntimeDirectoryMode -p Socket --no-pager; stat -c "%n %U:%G %a" /opt/vst-s2/source'
```

Observed: Ubuntu 24.04.5, Python 3.12.3, pytest 7.4.4; `vst-runner` 997:988, `vst-worker` 999:989, `vst-signer` 995:987; `vst-run.slice` reported 100% CPU, 2 GiB memory maximum and 64 tasks. `vst-signer.service` was inactive and `LoadState=not-found`. `/opt/vst-s2/source` was `root:root` mode 0755; it is a historical S2 path, not a current S4 checkout.

## What the S2 precedent proves—and does not

The S2 E5 record documents a successful synthetic `run_manifest_commands` execution in a transient unit using `NoNewPrivileges=yes`, only `CAP_SETUID`/`CAP_SETGID`, private network, path masks/tmpfs and finite CPU/memory/task/runtime limits. The worker ran as UID 999 and could not access the signer socket. This proves technical feasibility of that bounded identity-switch model in the distro for the recorded S2 run only. It does not approve applying the capabilities to S4 and does not provide S4's trusted signer, manifest or snapshot.

## Exact S4 prerequisites still absent

1. Project/operator approval for one S4 report-serialization invocation using the transient runner capability/identity-drop model. The prior WSL selection was scoped to one S2 E5 correlation; it does not authorize an S4 capability grant or signer use.
2. A run-specific S4 v2 manifest.
3. A trusted S4 signer socket and signer identity. The observed S2 signer service is absent; S2 used a disposable synthetic signer in its recorded run.
4. A current-HEAD S4 snapshot staged under the designed runner-owned root with the required mode 2710 and confirmed worker group. The historical S4 transfer evidence at `452c8ea` does not establish this current state.

S4 design identifies `tools.qa.wsl_snapshot` as the transfer path. An ordinary `git archive` without Git metadata cannot satisfy the runner's Git/head/read-only checks. Keep report-bound serialization, signed v2 report, receipt/gate and aggregate acceptance `NOT_RUN` until the four prerequisites are met. Canonical records do not identify a technical QA infrastructure owner; the operator is accountable for the requested project approval and Codex is the executor.
