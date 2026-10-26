# Change 0355 — Accept equivalent expanded pure-Python wheel tags

## What changed

- Updated `tools/qa/dependencies.py` to expand compressed wheel filename Python tags and repeated `WHEEL` metadata tags into the same constrained set before comparison. The verifier accepts only `py2`/`py3` with `none-any`, rejects duplicate or unsupported tags, and requires exact equality between filename and embedded metadata tags.
- Added a focused functional regression in `tests/qa/test_s4_dependency_provenance.py`. It verifies that `colorama-0.4.6-py2.py3-none-any.whl` is accepted when its metadata carries separate `py2-none-any` and `py3-none-any` tags, rejects a filename/metadata set mismatch, and rejects an unsupported `cp314-cp314-win_amd64` tag.
- The selector is not recorded in `docs/qa/categories.json` in this commit. Registry provenance must be regenerated after the modified test file has its own commit, because the registry records the path's latest source commit.

## Why

The hash-pinned `colorama 0.4.6` wheel in the provisioned trusted wheelhouse has a valid compressed filename tag, `py2.py3-none-any`, while its internal `WHEEL` metadata represents that tag as two entries: `py2-none-any` and `py3-none-any`. The previous verifier compared literal strings and rejected this valid wheel before selector collection. The fix supports the represented equivalence while keeping the accepted interpreter/ABI/platform set narrow and retaining existing lock hash, package identity, archive inventory, and target-content checks.

## Verification

- Designated `e2e-runner` executed the new focused selector on Windows 11 / CPython 3.14.3 using the existing isolated pytest target:
  `PYTHONPATH=D:\Temp\virtual_scrum_team_qa_f4ef8e7`, `PYTHONDONTWRITEBYTECODE=1`, then `C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/qa/test_s4_dependency_provenance.py::test_s4_dependency_accepts_equivalent_expanded_python_wheel_tags`.
- Result: exit 0, `1 passed, 1 warning in 0.76s`; the warning was a pytest-asyncio deprecation emitted from the installed test environment. The agent had two earlier fixture-only attempts that failed because the synthetic lock omitted required metadata and then the pytest pin; the final fixture corrected both and passed.
- A read-only call to `_verified_wheels` on `tools/qa/requirements.lock` and `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse` accepted all six hash-pinned wheels, including colorama SHA-256 `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6`.
- `verify_dependency_environment` on the pre-existing target `D:\Temp\virtual_scrum_team_qa_f4ef8e7` did not pass: it reported `dependency target inventory differs from the locked wheel inventory` (969 files, with extra `__pycache__`, `_pytest`, and `bin` entries). The existing target and wheelhouse were left unchanged. No report-bound selector was executed by the broad matrix attempt at candidate `4fe1503`; its Windows preflight stopped on the tag defect, and its WSL staging stopped before invoking the runner.
- Fresh GPT-6 Luna code review found one MAJOR registry-provenance follow-up, resolved by regenerating `docs/qa/categories.json` in the next commit after this test-source commit. GPT-6 Luna medium-effort security review found no actionable BLOCKER/MAJOR/MINOR issue. Neither reviewer ran tests.

## Limits and follow-up

- This commit does not close S4 AC-17: reports still explicitly leave same-identity dependency mutation/change-and-restore during pytest as `NOT_VERIFIED`.
- The 52 policy-excluded selectors remain `NOT_RUN`. No process-kill, process-death, timeout termination, mutation, crash/resume, or prohibited kill-table selector was executed.
- Prepare a new isolated dependency target from the already-present wheelhouse without changing the stale pre-existing target; regenerate the category registry after this source commit; then run the authorized report-bound selectors at a clean exact head.
- Accountable task owner: operator. Implementation/evidence owner: Codex. Test author/executor: designated `e2e-runner`.
