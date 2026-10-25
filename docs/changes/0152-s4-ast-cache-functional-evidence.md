# Change 0152: Add AST-cache regression coverage and record execution

## What changed

- Added functional coverage proving that distinct test IDs sharing one test source cause one read and one AST parse within one registry load.
- Added coverage proving an oversized source remains fail-closed and is read once when the same per-load cache is reused.
- Recorded the targeted pass and full-module `NOT_PASS` result in `docs/sdlc/evidence/s4-ast-cache-functional-93cd3c3.md`.

## Why

Change 0151 addresses the S4 security review's AST parse amplification finding. These tests observe source reads and parser calls at the actual registry boundary and exercise invalid-source caching.

## Affected paths

- `tests/qa/test_s4_registry_contracts.py`
- `docs/sdlc/evidence/s4-ast-cache-functional-93cd3c3.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

The two new regression cases passed (2 passed, 16 deselected). The full focused module did not pass: 16 passed, 1 skipped, 1 failed due to the existing bounded `git rev-parse --verify HEAD` call timing out after 5 seconds in the committed-registry integration test. See the evidence file for exact commands and details. Do not report the full module as green.

## Provenance

Test owner: functional-test-reviewer (GPT-6 Luna, medium). Tested code HEAD: `93cd3c334c66683a379ca594215eaa3f5507bfd8`. The source fix itself is documented in change 0151.
