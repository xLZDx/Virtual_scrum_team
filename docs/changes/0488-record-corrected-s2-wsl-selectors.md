# Change 0488 — Record corrected S2 WSL selectors

Date: 2026-10-28

## What changed and why

After change 0487 corrected invalid historical module paths, the designated e2e-runner executed the
actual existing S2 WSL E3 and synthetic identity selectors from source/test commit
`d5001797cb94113efd9a8dc26e4a15f2dc130976`. This supplies selector-level evidence without relying
on the malformed command records in change 0483.

## Result

The eight corrected selectors cover 12 collected cases: 10 E3 anchor/recovery cases, one synthetic
worker key/socket-boundary case and one synthetic reviewer write-boundary case. The first batch
reported 11 passed and one harness-only import failure because the disposable archive root was mode
`0700`. The one affected selector was rerun after changing only that temporary root to `0755` and
passed. Final acceptance for this selection: **12 passed, 0 failed**, with the setup failure
preserved in the evidence. The functional-test-reviewer independently confirmed the test-to-acceptance
mapping.

## Affected paths and acceptance limits

- Evidence: `docs/sdlc/evidence/s2-corrected-wsl-runtime-selectors-20261028.md`.
- S2 state/backlog/decision and document registry updated.
- VST-012/E3 and the synthetic POSIX portions of VST-011/E2 and VST-015/E6 gain bounded focused
  runtime evidence.
- Real key isolation, persistent runtime, capability/timeout, full platform containment, current
  E5, production dispatch and E8 remain unproven. S2 remains NOT APPROVED; no S3 work began.

## Verification and safety

- Source/test revision: `d5001797cb94113efd9a8dc26e4a15f2dc130976`; test-file hashes matched Git.
- WSL Ubuntu 24.04; Python 3.12.3; pytest 7.4.4; exact commands, temporary roots and results are
  in the evidence file.
- Both temporary roots were removed. No services, accounts, capabilities, credentials, E5
  signatures, root config or production settings were changed.
- The malformed earlier launches were not counted as test results.

## Ownership and next step

The designated `e2e-runner` executed the tests; `functional-test-reviewer` checked coverage; Codex
maintains the evidence. Next: preserve remaining system-dependent selectors as `NOT_RUN` until
their actual prerequisites and operational scope are available. GPT-PM owns final exact-head
adjudication; the operator owns any genuine root configuration, current-run E5 signature and
external coordinator source path.
