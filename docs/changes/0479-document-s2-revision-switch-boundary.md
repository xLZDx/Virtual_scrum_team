# Change 0479: Document the S2 runtime revision-switch boundary

## What changed

- Clarified that the versioned runtime installer installs immutable revision trees but does not
  switch `/opt/vst-runtime` between different revisions or provide rollback.
- Added prerequisites for a separately authorized and GPT-PM-reviewed future deployment runbook,
  including quiescence, consistent root configuration/runtime selection, failure handling and
  verification.
- Linked the exact-head artifact-only install evidence and stated that units remain inactive.

## Why

The exact-source reliability review for change 0475 identified a non-blocking operational
limitation: the installer refuses a different existing runtime selector and has no automatic
revision-switch procedure. This documentation closes that review follow-up without implying that a
switch or service activation has occurred.

## Affected paths

- `docs/sdlc/S2_VERSIONED_WORKER_HELPER_DESIGN.md`
- `tools/vst/systemd/README.md`
- `core/DECISION_LOG.md`, `core/BACKLOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Documentation-only change; no source/test change and no tests/checks run.
- The design text matches observed installer behavior in `tools/qa/install_wsl_runtime.ps1`:
  revision-specific immutable trees and selector validation before mutation.
- The in-scope exact-head installation is recorded in
  `docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`; the units were not
  enabled or started.
- GPT-PM request `7c9fcb10-61cc-4fdd-8292-c2dfbf97ff04` / correlated reply
  `f347e63d-f691-4561-86d9-95968bb3bb4e` still returns **NOT APPROVED** for S2. This documentation
  does not change that verdict or grant rollout authority.

## Next action and owner

Codex owns preparation of any later revision-switch runbook. GPT-PM owns review of its deployment
contract. The operator owns authorization for stopping/switching privileged services and providing
root-owned configuration/credentials. No runtime switch is permitted by this documentation alone.

## Commit attribution

Executor: Codex
