# Change 0538: complete S2 dispatch-owner transport source scope

## Purpose

Provide the accepted coordinator path with a transport-only client for an already signed exact
instruction. Preserve Store assignment/lease authority, signed provenance, one submission, and
conservative ambiguous-outcome handling.

## Changes

- Added `tools/vst/dispatch_owner_transport.py`: fixed AF_UNIX path; root-owned parent/socket
  metadata checks; systemd PID 1/UID 0 and live pidfd checks before sending; canonical bounded
  request; request half-close; exact principal/envelope/result-field binding; no automatic retry.
- Added focused tests in `tests/vst/test_s2_dispatch_owner_transport.py`, including real local
  AF_UNIX socketpair interoperability with `DispatchOwnerService._handle()`.
- Reconciled current S2 backlog/state and recorded coordinator/runtime adjudications and test
  evidence. The existing bounded coordinator is accepted; no external coordinator is required.
- Preserved the complete prior `docs/sdlc/STATE.md` history from baseline `20fda2c` in
  `docs/sdlc/S2_STATE_HISTORY.md` because enabling Agentic_Framework replaced STATE.md with its
  generated phase table. Framework tracking files are kept outside this transport commit.

## Review and evidence

GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55` accepted the attached source/test scope and
resolved transport M01 (missing EOF) and M02 (unauthenticated endpoint). A later read-only PM
Bridge job-status query recovered the stored correlation: job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c`,
reply `d555b078-5647-46eb-bfc1-dd99654d634f`, `correlated=true`. The job lifecycle is marked
uncertain because the parked wait deadline elapsed, while the stored reply contains the exact
request ID and ACCEPT verdict. Read-only code, security and test-mapping reviewers found no
actionable remaining findings.

The functional-test role reported Windows 33 passed / 1 POSIX-only skip. The E2E role ran the same
focused file in Ubuntu-24.04 WSL as root: 34 passed, 0 skipped, 0 failed, exit 0. The first WSL
attempt exposed a test-only SHUT_WR constant mismatch, corrected before the final passing run.
Commands, versions and hashes: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.
Decisions: `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.

## Scope limits

Source/test baseline HEAD was `20fda2cbf26274192652a1c829a19f6b1844e9c4`; the new files were
working-tree additions. Kernel credentials, pidfd and socket metadata are mocked in the source
fixture. Actual systemd peer identity, production issuer/custody, root runtime configuration,
owner-to-Runner integration, E5 and final S2 approval remain open. No privileged provisioning,
service activation, migration, production dispatch, push, PR or merge occurred in this change.

Delivery reconciliation: the source and change record were included in already-pushed commit
`e987a24483a5130298a28cccd2efd08f457aab9a`, a large mixed S2 import rather than an isolated task
commit. Its exact source/test blobs are verified against that commit; see change record 0588 for
the delivery limits and current task order. This historical commit is not rewritten.
