# S2 read-only WSL system inventory — 2026-10-27

## Scope and provenance

Read-only inventory from the canonical repository `D:\Repo\Virtual_scrum_team`. No source or test files were changed, no package was installed, and no network probe, child-process/worker execution, process termination, crash, or mutation scenario was run. The invoking shell used the existing `Ubuntu-24.04` WSL2 distribution as `root`.

## Observed facts

Command: `wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc '<read-only inventory>'`.

- Kernel identifies as WSL2: `6.6.114.1-microsoft-standard-WSL2`.
- `/etc/wsl.conf` reports `automount.enabled=false`, `interop.enabled=false`, and `appendWindowsPath=false`.
- The queried mount inventory showed `/` on ext4 and `/dev/shm` on tmpfs; no `/mnt/c` or `/mnt/d` mount was present in the queried mount output.
- `/var/run/docker.sock` was absent.
- The queried network socket inventory counted 13 listening sockets. This is a point-in-time count, not an egress or firewall test.
- The command identity was `root` (UID 0). Accounts `vst-worker` (UID 999) and `vst-runner` (UID 997) exist, but this inventory did not execute as either account and does not prove the authorized identity transition.
- The observed `/proc/self/limits` reported 127709 max processes, 10240 soft / 1048576 hard open files, 64 MiB locked memory, and unlimited address space. These are process limits for this root shell, not proof of sandbox resource enforcement.

## Acceptance disposition

This inventory is supplemental system evidence only. It does not prove worker isolation, process containment, filesystem write exclusion, full egress enforcement, persistent deployment, host firewall/hypervisor policy, or Windows Job Object behavior. S2 Phase 8 remains NOT APPROVED. Prohibited process, crash, and mutation scenarios remain `NOT_RUN`; do not infer PASS from this inventory. The prior 81-case safe Windows/WSL subset and its 86-ID registry denominator remain documented in `s2-safe-platform-subset-6ca2ee0-20261026.md`.

Owner: Codex owns evidence recording and gate reconciliation; the operator owns any authorization to broaden process/crash/mutation scope; GPT-PM owns gate adjudication. Next: preserve these limits and request another gate only after all mandatory permitted evidence and any required explicit waiver are recorded.
