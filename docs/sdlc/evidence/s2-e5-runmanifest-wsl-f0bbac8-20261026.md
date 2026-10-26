# S2 E5 exact-head WSL preflight — 2026-10-26

## Scope and provenance

- Canonical checkout at run time: `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`, repository HEAD `ca3e31ff1172c899458a7a8f1886539d1d1ae634`.
- Exact product source and test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- The runtime input was a `git archive` snapshot of that exact commit, 21,739,520 bytes, SHA-256 `2c6be40566806d164fac515cfca18f8584ecc3df6087c017f0f3e321d848dec1`. It had no `.git` directory and was bound read-only into the transient runner. No worktree, fork, or per-sprint checkout was created.
- `docs/SANDBOX_SPEC.md` SHA-256: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.
- Fresh sanitized provisioning-evidence bundle SHA-256: `d247417dddde3dffe388312cf925ace5aff91c497f5a32b33b0557aa7d08a745` (private root-only WSL evidence, not committed). It binds the environment, policy, exact archive, and separate read-only boundary observation.
- Normalized nftables JSON SHA-256: `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`; raw ruleset SHA-256 at evidence capture: `ac01a9a9e43e658b4c7b6d1a8015d0e73cdad3a27a9b86c68c6dbd8f631f2f1b`. Input and output policy were `drop`, with loopback accepts only. Raw digest can vary with transient nftables handles; normalized policy digest was recomputed immediately before signing and matched after the run.
- Environment: dedicated `Ubuntu-24.04` WSL2, Ubuntu 24.04.5, systemd 255.4, Python 3.12.3. WSL automount, Windows interop, and Windows PATH append were disabled. No Windows-drive mounts were observed in the transient runner.

## Run-bound attestation

The public operator-root attestation is [s2-e5-operator-attestation-f0bbac8-20261026.json](s2-e5-operator-attestation-f0bbac8-20261026.json). It binds:

- Run ID `s2-f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2-e5-20261026-591249434bde4989b6d320bf3675fe20`.
- Nonce `591249434bde4989b6d320bf3675fe20` (consumed; do not reuse).
- Environment ID `Ubuntu-24.04`, spec digest, normalized network-policy digest, and private provisioning-evidence digest above.
- `empty_external_allowlist=true`, `no_container_socket=true`, and `no_unapproved_host_paths=true`.

The separate read-only boundary observation used ID `s2-observe-f0bbac8-20261026-7bd767da9074424e8a32fc5a5b6e9d4b`, nonce `7bd767da9074424e8a32fc5a5b6e9d4b`, and had private-record SHA-256 `1e934fb6a13dc74203ecfe686d892e886ed75e711f462f9dfe41e732c2e23386`. It used the exact snapshot read-only and did not call the acceptance probe, signer, or network canaries. It observed 28 mount rows, zero Windows-drive mounts, complete container-socket enumeration with zero paths, runner UID:GID `997:988`, a read-only `/run/user`, and the effective limits and masks below. The only source mount was the trusted exact-head WSL ext4 archive bound read-only to the runner preflight; no worker command was started.

The coordinator signed the attestation using the repository's `sign_network_policy_attestation` implementation from the exact snapshot and verified its signature and bindings before handoff. The operator key bytes were never printed or included in evidence. The E2E executor did not access the operator key.

## Exact acceptance run

The designated `e2e-runner` ran the preflight from the exact source archive. Runner unit shape:

```text
systemd-run --wait --pipe --collect --unit=s2-e5-final-probe-591249434bde --slice=vst-run.slice --uid=vst-runner --gid=vst-runner --working-directory=<read-only exact source bind> --setenv=PYTHONPATH=<read-only exact source bind> --setenv=TMPDIR=/tmp --setenv=VST_ATTESTATION_PATH=<per-run signed attestation> --setenv=VST_SIGNER_SOCKET=<per-run AF_UNIX endpoint> --property=CPUQuota=100% --property=MemoryMax=2G --property=TasksMax=64 --property=RuntimeMaxSec=45s --property=BindReadOnlyPaths=<exact f0bbac8 WSL archive>:<source bind> --property='InaccessiblePaths=-/mnt/wsl -/mnt/wslg -/tmp/.X11-unix -/usr/lib/wsl -/usr/lib/modules -/var/tmp -/dev/mqueue -/run/lock -/run/shm' --property=TemporaryFileSystem=/run/user:ro --property=TemporaryFileSystem=/tmp:size=1G,mode=1777 --property=TemporaryFileSystem=/dev/shm:size=64M,mode=1777 --property=PrivateNetwork=yes --property='RestrictAddressFamilies=AF_UNIX AF_INET' --property=NoNewPrivileges=yes --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' --property='AmbientCapabilities=CAP_SETUID CAP_SETGID' /usr/bin/python3 -c '<harness calling collect_inventory then sign_inventory_with_service>'
```

The runner identity was UID:GID `997:988` with supplementary groups `987,988`. Effective cgroups reported `cpu.max=100000 100000`, `memory.max=2147483648`, and `pids.max=64`. The transient `/tmp` was a 1 GiB tmpfs, `/dev/shm` was 64 MiB, and `/run/user` was not writable. The unit used a private network and only `AF_UNIX`/`AF_INET` address families. The signer was a separate transient unit under UID `995`, runner GID `988`, restricted to `AF_UNIX`, with a 120-second ceiling and the same bounded source/mount environment.

The signer-owned key remained UID:GID `995:987`, mode `0600`; its contents were not printed. Before starting either service, the coordinator captured the owners, modes, and raw ACL-xattr state of exactly `/var/lib/vst` and `/var/lib/vst/keys`; both were root:root `0700` with no access-ACL xattr. Using already-installed `libacl.so.1`, the one-run wrapper added only `user:995:--x` to those two directories. Its guarded cleanup path stopped both transient units, removed the unique run's socket/ledger/attestation artifacts, restored the original ACL-xattr absence and root:root `0700` metadata, and byte-checked the ACL state. Independent post-run inspection confirmed both ACL xattrs absent, both directories root:root `0700`, both units `not-found`, and no per-run socket, ledger, or run directory. The operator-key directory remained root:root `0700`.

## Result and verification

- Runner command exit: `0`; inventory result: **PASS**.
- All seven checks were `true`: automount disabled, interop disabled, no container socket, non-root, reserved-target egress smoke blocked, loopback canary works, and empty external allowlist attested.
- Inventory facts: UID:GID `997:988`, 28 mount rows, zero Windows-drive mounts, complete container-socket inventory with zero paths.
- Full signed inventory remains private in WSL, root:root mode `0600`, 3,673 bytes, SHA-256 `de8fd9394867f8c79bfe0d516143d922c1c1fe5b97728ef5ea986a18c9aaf995`. Its runner-signature SHA-256 fingerprint is `70247361463a7c8150afaa91fa2c28eb641e72b0aee4d9a91341fa6e431874a9`.
- The coordinator independently verified `verify_network_policy_attestation` and `verify_fresh_probe` against the WSL-held operator and runner keys without printing either key. Both returned true. The normalized policy digest still matched the attestation after the run.
- Verification is limited to this exact per-run WSL boundary. The reserved-address egress probe is a smoke check, not proof of general egress enforcement. The observation and inventory do not prove persistent production deployment, external direct-writer exclusion, a worker-specific workspace binding, Windows Job Object behavior, full POSIX process-tree cleanup, or process-kill/crash-resume safety.
- No source or test files changed. No process-kill, kill-table, mutation, or crash/resume scenario ran. GPT-6 Luna role `e2e-runner` executed the probe; resumed-agent effort metadata is not available. The overall S2 gate remains open pending E4/E8, remaining system evidence, and refreshed GPT-PM disposition.

## Diagnostic attempts and corrections

Before the final run, two disposable boundary-observation attempts stopped before collecting an inventory: the first source bind remained under `/tmp` hidden by the unit's private tmpfs, and the next observer used `__file__` under `python -c`. The successful observation used a root-only archive parent and read-only source bind with a corrected observer. A manually transcribed policy digest also failed a pre-ACL guard because it was 62 rather than 64 hexadecimal characters; no ACL or service was started by that attempt. The coordinator recomputed the normalized digest from current nftables JSON, regenerated and verified the attestation programmatically, and the final pre-run comparisons all matched. These diagnostics did not consume the final run ID/nonce or change product code.

Change: 0339  
Executor: Codex
