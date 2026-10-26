# Change 0366 — Align the synthetic E2E registry fixture with the current contract

## What changed

- `tests/qa/test_s4_e2e_runner_cli.py`: the committed synthetic runner baseline now archives its exact identity-selector test source. The synthetic candidate includes that source in its inventory and manifest with the committed selector, source hash, `identity` primary category, and the selector's required WSL profiles.
- The synthetic manifest declares the fixed `identity` artifact paths and an `identity` category with `SUPPORTED` status and exactly that selector. The synthetic E2E category still selects only `tests/qa/test_native_fixture.py::test_native_fixture`; the identity selector is not executed by this focused E2E run.
- Fixture creation now allows `tests/` to already exist after the committed identity source is extracted.

## Why

The synthetic fixture's minimal registry predated the current registry contract. The report-bound runner correctly rejected it first because the fixture omitted fixed artifact paths for `identity`, then because the identity source/selector was absent. This was a test-fixture defect, not a product-runner failure. The compatibility update supplies the required committed identity source and metadata while preserving the existing E2E selector and assertions.

## Focused verification

- Canonical source HEAD before this fixture update: `c2a41fc6b1349edbeafd6ffa4eb7ec67911e0392`; the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not changed.
- Fresh dependency target: `D:\Temp\vst-s4-wheelhouse-target-20261026-r4`.
- Verified wheelhouse: `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`.
- Target preparation: `C:\Python314\python.exe -m tools.qa.prepare_dependencies --repo-root D:\Repo\Virtual_scrum_team --wheelhouse D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse --dependency-target D:\Temp\vst-s4-wheelhouse-target-20261026-r4`; result `PREPARED`.
- Focused command: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_native_collection_binds_candidate_and_repeatable_artifact_chunks --basetemp D:\Temp\vst-s4-wheelhouse-evidence-20261026-r4\pytest-tmp`.
- Environment: `VST_QA_DEPENDENCY_WHEELHOUSE=D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`; `PYTHONPATH=D:\Temp\vst-s4-wheelhouse-target-20261026-r4`; `PYTHONDONTWRITEBYTECODE=1`; `PYTHONPYCACHEPREFIX=D:\Temp\vst-s4-wheelhouse-evidence-20261026-r4\outer-pycache`.
- Result: exit 0; 1 passed, 1 existing `pytest-asyncio` deprecation warning, 26.59 seconds. Warning location: `C:\Users\koros\AppData\Roaming\Python\Python314\site-packages\pytest_asyncio\plugin.py:1216` (`asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16).
- The focused test's synthetic candidate head was `baf5b4505e90f7322cf1dab96822fc4e1962b893`. Its report contains two successful one-selector executions: `native-pass-1` row SHA-256 `7c7fc65508da07d60ff7088d7ed46c01626d554fbc39b5439935410832b9404c`, and `native-pass-2` row SHA-256 `36f3bfc506caad3e119161456196a13bdd1aa777c795c01807f02f806b94b10a`. Combined report SHA-256: `653f3f852c05bcffc73acb497fe082fe921d59abdf63e9acb79814b06e0dda08`.
- Both nested reports record dependency-target SHA-256 `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84` before and after execution. Raw report: `D:\Temp\vst-s4-wheelhouse-evidence-20261026-r4\pytest-tmp\test_s4_e2e_cli_native_collect0\candidate\docs\sdlc\evidence\qa\e2e.report.jsonl`; pytest output: `D:\Temp\vst-s4-wheelhouse-evidence-20261026-r4\focused.stdout.txt` (SHA-256 `68337f2c8b2cca85ed6a985bccd5554a533cda12204aec67b278dd00caf7383f`).
- `git diff --check`: exit 0.

## Acceptance still pending

- This is a focused synthetic report-bound runner test, not a full S4 E2E category acceptance run.
- The E2E category includes checkpoint/resume, out-of-scope edit, worker-death, and zombie-late-write scenarios excluded by the active execution constraints. Do not run that whole category as a shortcut; a safe report-bound subset needs an authorized selector/profile mechanism.
- Regenerate and separately commit `docs/qa/categories.json` after this test-source commit. The 52 policy selectors remain `NOT_RUN`.

## Ownership and next action

- Accountable owner: Codex.
- Test author and executor: designated E2E runner.
- Next: commit this test fix and record, refresh the registry in a separate commit, then continue only with selector/profile combinations that satisfy the active exclusions.
