# Change record 0209: Record the permitted S2 WSL E2E subset

## What changed

- Added an exact-head WSL2 E2E evidence record for the permitted Store, runner, and sandbox lifecycle subset.
- Reconciled `core/STATE.md`, S2 current state, backlog rows VST-013/VST-014/VST-020, and both sprint reports with the run and its remaining skips.
- Preserved the earlier WSL snapshot and its separate run-bound E5 evidence; this run does not claim a new inventory attestation.

## Why

The operator selected a dedicated WSL2 environment. A safe test subset could run after coding was complete, but the prior state did not include that run. The exact HEAD and skipped acceptance cases must remain explicit.

## Evidence and limits

- Test owner: `e2e-runner` (GPT-6 Luna, low effort). No implementation or test source was changed.
- Source/test HEAD: `ed723a953d51b92827d3977c96e833258a38342c`. A new stage was extracted from tracked source with archive SHA-256 `61adb2b0e5d5a64310216fe2930b955ba04debee2aba5e96d9fd094bba6db477`; the pre-existing `/opt/vst-s2/source` was not altered.
- Store lifecycle: 19 passed, 0 skipped. Runner/sandbox lifecycle: 90 passed, 11 skipped. Combined: 109 passed, 11 skipped out of 120 collected.
- Environment: Ubuntu 24.04.5 on WSL2, Python 3.12.3, pytest 7.4.4. Full commands, transient unit limits, setup correction, and acceptance mapping are recorded in `docs/sdlc/evidence/s2-e2e-wsl-ed723a-2026-10-25.md`.
- Eleven scenarios remain `NOT_RUN`: four E4 containment scenarios, including prohibited process-kill/kill-table and Windows Job Object cases; one actual inventory probe; and six E8 bake-off scenarios, including prohibited process termination/mutation.
- The full E6 diff-gate test module was not included. No build, CI, migration, mutation, kill-table, or process-kill scenario was run. No GPT-PM exact-head approval was obtained; do not push or open a PR.

## Ownership and next step

- Accountable owner: operator for the delegated S2 sprint.
- Executor: Codex coordinates the record; `e2e-runner` owns the test evidence.
- GPT-PM owns the final exact-head review gate; current PM Bridge health call returned `Transport closed`.
- Next: obtain a fresh GPT-PM approval for the resulting exact repository HEAD when the bridge is available. Resolve prohibited/platform acceptance only through the applicable authorized path.

## Verification state

Runtime evidence is limited to the recorded WSL commands and their exact result. `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and regenerated the registry; the named `report_conform.py` command exited 0 and refreshed both HTML reports; `git diff --check` exited 0. No test was run by the coordinator.
