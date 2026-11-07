# Change 0224 — Update S2 E3 anchor test coverage

Date: 2026-10-25
Executor: Codex

## What changed

- Reconciled S2 E3/VST-012 backlog and report status with the exact-commit WSL Store lifecycle result.
- Added the nine POSIX-only anchor scenario mappings to the exact-head evidence and phase state.
- Preserved the limitation that aggregate pytest output did not retain per-node lines and did not prove production worker/mount binding.
- Regenerated the document registry.

## Why

The exact WSL run executed the complete committed `tests/vst/test_s2_store_lifecycle.py` module at `c2771b5` and returned 19 passed, 0 skipped. Its committed source has POSIX-only skip decorators around the anchor scenarios; they are inactive in the recorded Ubuntu/WSL environment. Earlier backlog/report text still marked those local E3 anchor cases `NOT_RUN`, so the evidence map needed correction.

## Affected contracts and paths

- S2 E3 external-anchor state, restoration detection, interruption recovery and fail-closed suffix behavior.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`, `docs/sdlc/evidence/s2-exact-head-functional-e2e-2026-10-25.md`, and both S2 reports.

## Evidence and limits

- Exact repository commit under test: `c2771b5968afcdd2b027f1c008fc8023fd0e0f12`; the WSL staging agent verified the test module Git blob against that HEAD.
- Whole-module command: `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py`.
- Result: 19 passed, 0 skipped, 0 failed in the bounded/private WSL `systemd-run` unit as `vst-runner`.
- Nine mapped E3 cases: anchor idempotency/fork rejection; older database restore detection; one-event-ahead recovery; multi-event suffix recovery; and five invalid suffix states (ahead, missing, forked, malformed, tampered).
- No separate per-node output was retained. This result applies to local fixture behavior at that exact committed source, not the unverified production worker/workspace/mount or quota boundary.
- No product or test files were modified or rerun for this documentation reconciliation. PM Bridge remains unavailable under change 0223; no new GPT-PM verdict is claimed.

## Verification state

- `report_conform.py` refreshed both S2 reports; `report_conform.py reports --check`, `tools/build_document_registry.py --check`, and `git diff --check` all exited 0. No product test was rerun during this documentation reconciliation.
