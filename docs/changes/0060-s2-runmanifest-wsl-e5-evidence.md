# 0060 S2 run_manifest_commands and scoped WSL E5 evidence

## What changed

- Recorded the first clean end-to-end `run_manifest_commands` execution under the provisioned WSL runner/worker identities and real signer socket.
- Recorded the trusted-parser fixture correction, receipt IDs/results, signer peer credentials, worker denial, and signed diff-gate evidence.
- Extended the scoped systemd boundary evidence to cover `/var/tmp`, `/dev/shm`, `/run/lock`, `/run/shm`, `/dev/mqueue`, and `/usr/lib/modules`, with bounded writable tmpfs and finite runtime.
- Recorded a runner-signed but unattested probe diagnostic, sanitized mount classifications, policy/spec/evidence digests, and an unused correlation reserved for the operator's separate probe.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The earlier WSL evidence proved signer socket authorization and resource controls separately, but did not exercise the real `run_manifest_commands` lifecycle. This run closes that integration gap for the synthetic manifest and disposable repository while preserving the distinction between a runner receipt and operator-approved environment attestation.

## Verification state

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Documentation HEAD before this record: `15e05f199833a2b1b8f75822435dbdf9242aaf33`.
- Exact command: `wsl -d Ubuntu-24.04 -- python3 /opt/vst-s2/run-manifest-integration.py`.
- Result: exit 0. TestRun `PASS`, IDs `t1`,`t2`, no skips; two commands exit 0; diff gate `PASS`; receipt and diff signatures present.
- Worker identity: UID:GID `999:989`; signer connection denied with errno 13. Signer recorded 26 requests, all peer UID:GID `997:988`.
- Effective transient limits: 45-second RuntimeMax, 1 GiB `/tmp` tmpfs, 64 MiB `/dev/shm` tmpfs, 2 GiB MemoryMax, 100% CPUQuota, TasksMax 64, per-run masks and private network namespace.
- Probe diagnostic: signed by runner signer only, result `FAIL`, no operator attestation. `no_unapproved_host_paths` remains false/unestablished pending operator/security review.
- nftables raw digest observations differ by snapshot; the run-time raw digest and later raw rechecks are recorded separately in the evidence file. The current normalized semantic digest matches the independent operator's normalization, but the raw snapshots were not retained, so a handles-only explanation is not claimed. Recompute both fingerprints at final-probe time.
- No source/test edits, operator-key access, or prohibited process-kill/kill-table/mutation tests.
- Full detail and reserved run correlation: [S2 E5 WSL integration evidence](../sdlc/evidence/s2-e5-runmanifest-wsl-280e2d0.md).

## Ownership and next action

- Accountable task owner: operator.
- Executor: E2E runner (`gpt-6-luna`).
- Technical owner for production worker-unit deployment and host/system mount approval is not established by the in-scope records.
- Recommended next action: operator/security owner reviews the sanitized mount/policy evidence and signs a fresh final inventory attestation only if all policy booleans are supportable. Keep the diagnostic run ID/nonce out of any final attestation.
