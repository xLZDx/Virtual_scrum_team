# Change 0156: Verify S4 registry resource budgets

## What changed

- Expanded the shared-source cache case to verify module functions and a class method resolve from one compact per-file index, with one read and one parse.
- Added an aggregate source-byte budget case using multiple controlled files.
- Added a registry-wide 2,048-ID cap case proving rejection happens before per-ID resolution.
- Recorded targeted and full focused-module results in `docs/sdlc/evidence/s4-registry-resource-budgets-6903b7b.md`.

## Why

The S4 follow-up code change 0155 adds bounded compact indexing across sources and caps the registry-wide number of node IDs. These tests falsify the acceptance boundaries, including whether expensive per-ID resolution starts before the count cap.

## Affected paths

- `tests/qa/test_s4_registry_contracts.py`
- `docs/sdlc/evidence/s4-registry-resource-budgets-6903b7b.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

At code HEAD `6903b7bf3e3dd4fc1281412c173fb82db9924d11`, Python 3.14.3 / pytest 8.4.2: targeted cases passed (3 passed, 17 deselected); full module passed (19 passed, 1 skipped, 0 failed). One pytest-asyncio deprecation warning. Windows symlink creation skip is `NOT_RUN` for POSIX behavior.

## Provenance

Test owner: functional-test-reviewer (GPT-6 Luna, medium). Exact commands, code HEAD and status are in the linked evidence.
