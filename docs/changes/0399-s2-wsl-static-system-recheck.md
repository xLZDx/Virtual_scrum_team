# Change 0399: record current S2 WSL static system recheck

## What changed

- Added a fresh root-shell WSL system inventory to the S2 evidence file.
- Recorded that Ubuntu 24.04 was started from a Stopped state for this read-only inspection and was listed Running afterward.
- Reaffirmed that all WSL observations are configuration-only and do not close S2 acceptance.

## Why

The operator directed Codex to continue only permitted Windows/POSIX/system evidence while keeping prohibited process, crash, and mutation scenarios `NOT_RUN`.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-wsl-system-inventory-20261027.md`
- `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`
- `docs/changes/0399-s2-wsl-static-system-recheck.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Exact command: `wsl.exe -d Ubuntu-24.04 --user root --exec sh -lc 'id; uname -r; cat /etc/wsl.conf; findmnt -rn -o TARGET,FSTYPE | grep -E "^(/ |/tmp |/dev/shm |/mnt/c |/mnt/d )"; getent passwd vst-worker vst-runner; ls -l /var/run/docker.sock; nft list chain inet vst_s2_filter input; nft list chain inet vst_s2_filter output; cat /proc/sys/net/ipv4/ip_forward; cat /proc/sys/net/ipv6/conf/all/forwarding'`.
- Observed root UID 0; WSL2 kernel `6.6.114.1-microsoft-standard-WSL2`; systemd on; automount and interop off; only `/` ext4 and `/dev/shm` tmpfs in the filtered mount output; no Windows drive mounts in that output; worker/runner accounts present; Docker socket absent; loopback-only nftables input/output chains with `drop` policies; IPv4 forwarding `1`, IPv6 `0`.
- No packets, DNS requests, network probes, child/worker runs, tests, builds, or policy-restricted scenarios were executed.
- No persistent WSL configuration, packages, accounts, mounts, firewall rules, or test files were changed intentionally. The distribution runtime transitioned from Stopped to Running to permit inspection.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Decision

Preserve this as a point-in-time static inventory from the root identity. It does not prove worker identity, policy immutability, restart persistence, egress enforcement, process containment, or Phase 8 acceptance. Keep S2 NOT APPROVED and prohibited scenarios `NOT_RUN`.
