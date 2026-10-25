# 0196 — Add S4 ancestry outcome functional tests

## What changed

Added five static-ID tests to `tests/qa/test_s4_registry_contracts.py` for the registry's Git ancestry query: return code 0 returns true; return code 1 returns false; another nonzero code raises `ContractError`; two consecutive timeout outcomes raise `ContractError` after the bounded retry; and an `OSError` raises invocation `ContractError`. Deterministic monkeypatched subprocess outcomes keep the tests local and independent of Git history or network state. Assertions check the observable result, typed error/cause, and that timeout retries stop after the second attempt. No product code or category mapping changed in this commit.

New static selectors:

- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_returncode_zero_is_true`
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_returncode_one_is_false`
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_other_returncode_is_contract_error`
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_second_timeout_is_contract_error`
- `tests/qa/test_s4_registry_contracts.py::test_s4_git_ancestry_oserror_is_contract_error`

## Why

The registry ancestry contract distinguishes a true ancestor (Git return code 0), a valid non-ancestor (1), and an indeterminate/error result (>1, exhausted timeout retry, invocation failure). AC-7 requires relevant negative/error paths to produce explicit falsifiable coverage. The tests exercise the `subprocess.run` boundary deterministically and assert that infrastructure failures do not silently become `False`.

## Verification state

No tests were run in this source-test commit. Per the accepted code-before-tests sequence, category registration follows in change 0197; the functional and related mapped category sets will run only after test and mapping commits are complete.

## Scope

Test-only change. Product source, category manifest, API IDs, E2E IDs, and reports are unchanged. The intentionally untracked `.codex-s4-final-review.patch` was not read or modified.

Executor: Codex
