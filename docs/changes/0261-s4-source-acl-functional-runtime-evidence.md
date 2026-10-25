# Change 0261: Record exact-head S4 ACL and functional runtime evidence

## What changed

- Added `docs/sdlc/evidence/s4-source-acl-preflight-runtime-bc32f6f.md` with the corrected focused ACL/worker/parser run and the synthetic report-bound functional CLI run.
- Recorded snapshot/run/candidate identities, exact selector set, environment and systemd bounds, report/receipt/diff-gate outcomes, worker identity probe, artifact hashes, and explicit trust/acceptance limits.

## Why

The named-ACL source preflight fix at `c51105a` needed exact-head WSL runtime proof. The first run at `180e330` exposed stale signer ACL message expectations in three selectors. After correcting only those test expectations, a fresh exact-head snapshot passed all focused regressions; the synthetic functional report-bound run then passed the registry's full 33-ID functional denominator.

## Decisions and ownership

- Keep this evidence limited to test-only synthetic signer acceptance; do not infer trusted signer deployment or E2E-category completion.
- Preserve all generated WSL run artifacts.
- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator; executor: Codex.

## Affected contracts and paths

- Evidence: `docs/sdlc/evidence/s4-source-acl-preflight-runtime-bc32f6f.md`.
- Covered source contract: QA source tree and Git metadata ACL preflight in `tools/qa/run.py` / `tools/vst/sandbox.py`.
- Covered test mapping: functional category in `docs/qa/categories.json`.

## Verification state

- Exact source/test HEAD: `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`; implementation source provenance `c51105abfef72aceb295633bbdf637666ad843a2`.
- Snapshot run `2b4c4e0d4bf7432aa6c0bb2dda433123`, bundle 1,342,542 bytes, SHA-256 `ddeeb1789a562fe50616986502e7b8ec9969bcdd92f4fe7f107b08b132e7949d`.
- Focused selectors: 15 passed in 0.52 seconds, unit `vst-s4-acl-preflight-bc32.service`.
- Synthetic outer functional CLI: 33/33 expected IDs, report PASS, TestRun receipt PASS, manifest diff gate PASS; unit `vst-s4-cli-functional-bc32.service`.
- Trusted signer `NOT_USED`; aggregate regression and authoritative gate `NOT_RUN`; E2E coverage remains `PARTIAL` and was not attempted.

Executor: Codex
