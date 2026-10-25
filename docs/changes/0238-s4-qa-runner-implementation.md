# 0238 S4 QA runner implementation

**Date:** 2026-10-25  
**Executor:** Codex  
**Implementation role/model:** `implementation-engineer`, GPT-6 Luna, medium effort  
**Branch/base:** `s4-reproducible-qa-automation` / `6beb3a87a2e4d13163bcb023b11d04bfe3466df5`

## What changed

- Added the S4 QA package: strict category registry validation, static registry generation, pytest collection/outcome plugin, synthetic-fixture catalog validation, normalized report encoding, and one bounded native runner CLI.
- Added the committed category registry and initial fixture catalog under `docs/qa/`.
- The registry distinguishes function/method selectors from concrete pytest node IDs, retains the full inventory, and assigns explicit reasons to policy-prohibited process-kill and `os._exit` selectors as `NOT_RUN`.
- Added deterministic category rules for future `tests/qa/test_s4_*.py` tests and the seeded-failure lane. Unknown paths fail registry generation. Seeded-failure switches to `SUPPORTED` only when its tests exist.
- Runner requires the approved `C:\Python314\python.exe`, checks the exact wheel lock and installed versions, never installs dependencies, limits runtime and captured output, and fails closed on missing, skipped, xfailed, duplicate, unexpected, or uncollected cases.
- Category stdout/stderr logs are append-only. Each report binds its own byte ranges and chunk digests; old log history does not affect the normalized run digest.
- Expanded `docs/QA_RUNNER_DESIGN.md` with interpreter, artifact, test-inventory, and exact per-invocation VST `change_scope.allowed_paths` rules. Existing `tools/vst` contracts and diffgate remain unchanged.
- Updated `core/DECISION_LOG.md` and `core/LESSONS_LOG.md` for the implemented contract.

## Why

S4 acceptance requires exact selector accounting, pinned and non-installing execution, truthful unsupported/unrun states, seeded negative inputs through unchanged product interfaces, and privacy-safe evidence. The readiness review found that parameterized functions expand into multiple concrete cases. A selector can pass only after every concrete case maps to it and passes. The implementation also needs to preserve operator-prohibited process-death scenarios in the inventory without invoking them.

## Affected contracts and paths

- `tools/qa/__init__.py`
- `tools/qa/build_registry.py`
- `tools/qa/fixtures.py`
- `tools/qa/pytest_plugin.py`
- `tools/qa/registry.py`
- `tools/qa/report.py`
- `tools/qa/run.py`
- `docs/qa/categories.json`
- `docs/qa/fixtures.json`
- `docs/QA_RUNNER_DESIGN.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `tools/vst/` and its receipt/diffgate contracts were not changed.

## Verification and provenance

- Static category generation only: `python -m tools.qa.build_registry --repo-root . --write`.
- Manual source review found and corrected: (a) seeded-failure category generation remaining empty after fixture tests are added; (b) malformed JSON event/catalog objects escaping typed fail-closed reporting; (c) empty selector sets potentially invoking pytest with default full discovery; and (d) append-only cumulative output hashes changing across repeated runs.
- No tests, checks, builds, CI, dependency installations, candidate/sandbox executions, or VST receipt generation were run. Required tests remain for the post-coding phase and are owned by `functional-test-reviewer` and `e2e-runner`.
- The repository's pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not staged or modified.

## Acceptance status

S4 AC-1 through AC-6 have implementation evidence but no test execution. AC-7 through AC-15 remain unverified or partially implemented pending committed fixture-consuming tests, category runs, seeded failures, relevant review, and exact-head gate evidence. Process-kill/process-death selectors remain `NOT_RUN` by explicit policy. The design specifies that each VST invocation must list its exact three artifact paths in `change_scope.allowed_paths`; no global permission or diffgate rule was changed.

## Ownership and next steps

- Accountable task owner: operator, under the delegated S2-S5 continuation.
- Executor: Codex.
- Test authors/executors: `functional-test-reviewer` and `e2e-runner` after coding is committed.
- Canonical QA service/lock maintainer: UNKNOWN in repository records.
- Next: complete the static integration review, then commit the QA implementation with this record. After that exact code commit, begin the owned test phase, remediate findings, and update the registry/fixture catalog from committed tests.
