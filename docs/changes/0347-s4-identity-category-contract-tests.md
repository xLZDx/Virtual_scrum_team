# Change 0347 — Add focused tests for S4 identity category contracts

## Summary

- Extended the synthetic registry fixture with the committed AC-16 selector under a singleton `identity` category.
- Added assertions that the real registry keeps that selector outside the four-member regression aggregate.
- Added falsifying tests for non-singleton identity membership, WSL-only identity matrix requirements, and the runner's fixed identity artifact/category paths.
- Updated only `tests/qa/test_s4_functional_runner_contracts.py` and `tests/qa/test_s4_functional_runtime_matrix.py`.

## Why

Change 0344 introduced a new category and changed the report matrix/runner allowlists. The functional contracts must demonstrate that the selector cannot broaden identity execution, Windows/root reports are not accepted for that lane, and only fixed identity artifact paths are accepted.

## Verification state

- Test author: designated `functional-test-reviewer`.
- Manual review: Codex reviewed the resulting test diff and assertions.
- Tests: `NOT_RUN`; the author intentionally did not execute before the test-source commit.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` and unrelated S3 documentation were not modified or staged by the test author.

## Exact proposed selectors

```text
tests/qa/test_s4_functional_runner_contracts.py::test_s4_registry_accepts_real_committed_selector_denominator
tests/qa/test_s4_functional_runner_contracts.py::test_s4_registry_rejects_non_singleton_identity_category
tests/qa/test_s4_functional_runner_contracts.py::test_s4_runner_accepts_identity_category_fixed_artifact_paths
tests/qa/test_s4_functional_runtime_matrix.py::test_s4_matrix_requires_identity_report_only_for_unprivileged_wsl
```

The exact command and result must be recorded by the designated test role after the registry is refreshed at the committed test source head.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Test author: `functional-test-reviewer`.
- Coordinator and manual diff reviewer: Codex.
