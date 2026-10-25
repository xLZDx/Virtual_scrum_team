# Change 0137: S5 POSIX symlink selector evidence

## What changed and why

Recorded the focused Linux/WSL run for the S5 source-tree digest symlink-rejection selector and a read-only recheck of the final approval gate. The earlier Windows functional run skipped symlink creation, so this run closes that one unit-level scenario while keeping analyzer/runtime isolation claims open.

## Affected contracts and paths

- S5 AC-6 for source-tree path rejection.
- `docs/sdlc/evidence/s5-posix-symlink-606bba9.md`
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- Bilingual `reports/S5_V3_GATE_STATUS_2026-10-25.*.html`
- `governance/DOCUMENT_REGISTRY.md`

## Evidence and decisions

- Exact S5 HEAD: `606bba9a5c3563b195eee7b5dd11f0dd243c44a5`.
- Ubuntu-24.04 WSL2, Python 3.12.3, pytest 7.4.4: one selector passed, zero failed, zero skipped.
- Windows and staged WSL SHA-256 for the test file matched. The archive itself was not hashed.
- An incidental `wsl.exe -l -q` was invoked before the test despite the pinned-distro workflow; no subsequent distro enumeration or configuration change occurred. This process shortcoming is recorded for prevention.
- In this turn `pm_bridge_health` and read-only `pm_bridge_job_status` calls for the two prior S5 request IDs returned `Transport closed`; the named receipt log had no matching rows. No fresh exact-head approval exists and no new request was sent.
- This selector proves source-tree digest rejection of a symlinked path only. Actual AEVE adapter, sandbox, resource/network/process boundaries and analyzer attestor remain `NOT_RUN` or `UNKNOWN`.

## Verification and ownership

The designated `functional-test-reviewer` executed only the existing selector. No source or test code changed. The operator remains accountable for delegated S5 work; Codex coordinates it. The analyzer technical owner is `UNKNOWN` in repository records.
