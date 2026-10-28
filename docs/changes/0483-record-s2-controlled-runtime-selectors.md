# Change 0483 — Record controlled S2 runtime selector results

Date: 2026-10-28

## What and why

Added focused Windows and WSL test evidence and reconciled S2 state/backlog/decision/lesson records. GPT-PM controlled-testing decision: request `a94486c9-f8e2-451e-91d2-4adb1799b8d6`, reply `85eba0d2-3670-5274-a787-58012255f22b`, job `3ff013cd-f5e4-441e-98c5-8c823f62a96f`. Its scope is controlled selectors only; it keeps `S2-DISPATCH-M01` MAJOR/OPEN and is not final S2 approval.

## Affected acceptance and verification

Against source/test revision `d5001797cb94113efd9a8dc26e4a15f2dc130976` (repository HEAD `a94486c9f8e2051e01d2ad2adb1799b8d238ace5`): Windows E4 process cleanup passed 2/2; waiver-boundary selectors passed 7/7; WSL E3 store selectors passed 10 cases; two synthetic POSIX identity selectors passed; two POSIX runner capability/timeout selectors skipped because the provisioned ambient capability profile is absent. An earlier WSL attempt failed during harness setup because `/tmp` did not persist between invocations; it is not a test result. Exact commands/interpreters/limits are in `docs/sdlc/evidence/s2-controlled-runtime-selectors-20261028.md`.

No production code or test source changed. No systemd/service, capability, credential, E5/E8, manifest, or production dispatch operation occurred. S2 remains NOT APPROVED and `VST-013` partial.

## Ownership / next step

Codex maintains evidence and coordinates focused reruns. Operator owns separate operational authorization for the dedicated WSL runner capability profile. GPT-PM owns final exact-revision adjudication after acceptance evidence is complete. Keep skipped selectors `NOT_RUN`; do not infer production acceptance from these focused tests.
