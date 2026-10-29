# Change 0487 — Correct S2 WSL selector provenance

Date: 2026-10-28

## What and why

Exact source review found that the recorded WSL E3 store and synthetic identity commands in change
0483 named selectors that do not exist under the cited modules at source/test revision
`d5001797cb94113efd9a8dc26e4a15f2dc130976`. The exact original command and raw pytest output were
not retained, so the pass summaries cannot be independently reconciled to the current test IDs.

## Correction

- WSL E3's retained “10 passed” summary is `NOT_VERIFIED`; five of six recorded node IDs are wrong
  for the module. The six actual current IDs are listed in the corrected evidence.
- The two synthetic identity selectors' retained “2 passed” summary is `NOT_VERIFIED`; both IDs
  were recorded under the wrong module. Their actual source modules are now recorded.
- Change 0485 already downgraded the two runner capability/timeout skips because one node module
  was wrong and the original invocation/output are missing. All three WSL result groups remain
  `NOT_RUN` for acceptance pending valid exact evidence.
- Valid Windows E4 cleanup and waiver-boundary results are unchanged.
- No code/test file, service configuration, credential, capability, E5 signature, or S4 record was
  changed. No test ran during this documentation correction.

## Evidence and verification

- Selector definitions were verified at commit `d5001797cb94113efd9a8dc26e4a15f2dc130976` with
  `git grep` against `tests/vst/test_s2_store_lifecycle.py`,
  `tests/vst/test_s2_runner_lifecycle.py`, and `tests/vst/test_s2_sandbox_probe.py`.
- No test was run in this change. The corrected, existing selectors will be run only by the
  designated test agent after this documentation update is committed.
- See `docs/sdlc/evidence/s2-controlled-runtime-selectors-20261028.md`.

## Ownership and next action

Codex owns the correction; the designated e2e-runner owns any fresh test execution. Next: run the
actual six E3 temporary-fixture selectors and two synthetic identity selectors with exact commands
and raw results; keep runner capability/service cases `NOT_RUN` until their prerequisites exist.
S2 remains NOT APPROVED; S3 remains unstarted.

Change 0488 subsequently ran the corrected E3 and identity selectors. Its evidence supersedes the
`NOT_RUN` status for those eight selectors only; capability/service-dependent selectors remain
`NOT_RUN`.
