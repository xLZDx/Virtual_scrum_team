# 0105 S4 E2E exact test-commit rerun

## What changed

- Extended `docs/sdlc/evidence/s4-e2e-local-1cd868b.md` with the post-commit rerun of the two E2E node IDs at exact test commit `0c8232e237477328d3dd5b9a658288d977360073`.

## Why

The original 0103 record documented successful local executions before the test source was committed and explicitly left exact committed-candidate evidence open. The focused rerun closes that test-source revision gap while preserving the dirty-worktree and native-runtime limitations.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-e2e-local-1cd868b.md`: adds exact revision, command, result, environment, and worktree limitation.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- This rerun covers only the committed local synthetic E2E module. It does not sign a v2 receipt or establish native WSL sandbox acceptance.

## Verification state

- Revision: `0c8232e237477328d3dd5b9a658288d977360073`.
- Command: `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Result: 2 passed, 0 failed in 7.97 seconds on Windows Python 3.14.3 / pytest 8.4.2; one existing `pytest-asyncio` deprecation warning.
- The worktree included unrelated concurrent category/catalog modifications and another agent's untracked registry test. The local E2E module passed; clean native snapshot transfer remains `NOT_RUN`.

## Follow-up

1. Coordinator adds all accepted test IDs to the category registry with valid ancestor provenance.
2. Once all S4 tests are committed and the worktree is clean, execute the native mapped E2E category in `Ubuntu-24.04` only after exact S4 runner, worker, destination, and signer provisioning inputs are available.
