# S4 local synthetic E2E evidence

## Scope and provenance

- Initial product/source baseline: `1cd868b776a50147b951c9282cc73e2868c6bad6` on branch `s4-native-qa-runner`. Later reruns used the subsequent revisions recorded below, up to the final clean validation HEAD `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`.
- The first two executions used source HEAD `1cd868b776a50147b951c9282cc73e2868c6bad6`; the third used `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771`. The fourth execution used exact test commit `0c8232e237477328d3dd5b9a658288d977360073`; the test module was tracked at that HEAD. The worktree still contained concurrent uncommitted registry/catalog changes and another agent's untracked test, so the candidate worktree was dirty and this does not establish native runner acceptance.
- E2E test IDs are `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence` and `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution`. The final registry records both IDs with source head `4913425c9327b2416ac7cc1e421268223ee43ae1`, which contains the committed test nodes and is an ancestor of final validation HEAD `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`.
- Local environment: Windows host, Python 3.14.3, pytest 8.4.2. The named `Ubuntu-24.04` WSL runtime reports Python 3.12.3 and pytest 7.4.4, but the repository source was not transferred there and no S4 native test was run.

## Executed journeys

Command:

```text
python -m pytest -q tests/qa/test_s4_qa_e2e.py
```

The first execution produced one pass and one failure. The synthetic VST slice CLI returned its established 23-scenario report; my new assertion incorrectly expected the shape of a different runner report. This was a **test defect**. I inspected `tools/vst/slice.py` and the existing S1 slice assertions, corrected the test to assert the CLI's actual scenario report, and did not change product code or weaken a product assertion.

The second execution passed both scenarios: **2 passed, 0 failed** in 10.52 seconds. After coordinator commit 0104, a third execution at source HEAD `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771` also passed both scenarios: **2 passed, 0 failed** in 5.79 seconds. After committing the test source, a fourth execution at exact HEAD `0c8232e237477328d3dd5b9a658288d977360073` passed both scenarios: **2 passed, 0 failed** in 7.97 seconds. Each passing output showed one existing `pytest-asyncio` deprecation warning. The slice journey verified the `APPROVE` happy path, retained earlier failed-attempt evidence after retry, a budget-overrun `MODIFY`, and per-scenario SQLite artifacts. The snapshot CLI journey verified that an unapproved WSL distribution is rejected with exit code 2 before launching WSL or creating a Git bundle.

The first failure and single corrected rerun do not establish flakiness; no test was quarantined. The output contained no trace, screenshot, or network response because these are local CLI journeys; pytest assertion output is the failure evidence.

## Not run and exact dependencies

- Native S4 runner/report/signing and exact-head gate acceptance: `NOT_RUN`. The source transfer was not attempted because S4 provisioning evidence does not identify the runner account, worker group ID, or pre-provisioned private snapshot root. S4 signer socket availability is also not established. No values were inferred from earlier S2 evidence.
- Transfer permissions, bundle digest, exact clone HEAD, worker read-only access, report artifact resolution, and signed receipt behavior: `NOT_RUN` for the same missing S4 provisioning boundary.
- Technical service owner for the S4 private provisioning values is `UNKNOWN` in the in-scope repository records. Accountable task owner is the operator under delegation; Codex is executor. Next step: use the designated S4 provisioning evidence to identify the exact runner account, worker GID, private root, and signer socket, then transfer the committed candidate and run the mapped native E2E category in `Ubuntu-24.04` without installing packages.

No Playwright/Cypress dependency was introduced. No CI, build, migration, package installation, or source transfer was run.

## Exact test-commit rerun

- Revision: `0c8232e237477328d3dd5b9a658288d977360073`.
- Command: `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Result: **2 passed, 0 failed** in 7.97 seconds; one `pytest-asyncio` deprecation warning.
- Environment: Windows host, Python 3.14.3, pytest 8.4.2.
- Worktree limitation: concurrent modifications to `docs/qa/categories.json` and `docs/qa/seeded_failures.json`, plus another agent's untracked registry test, remained outside this commit. Native snapshot transfer requires a clean worktree, so it remains `NOT_RUN`.

## Placeholder-hardening commit rerun

- Revision: `b8128461ec20c0b05f8172f5599e5be80ed626f9`.
- Command: `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Result: **2 passed, 0 failed** in 6.61 seconds; one `pytest-asyncio` deprecation warning.
- Environment: Windows host, Python 3.14.3, pytest 8.4.2.
- The snapshot refusal test supplied only visibly inert placeholders for arguments that are never consumed because the wrong-distribution guard runs first. The worktree still had concurrent category and generated-registry changes; native transfer remains `NOT_RUN`.

## Final clean-head rerun

- Revision: `594eeddcd1f6409928e7eebb1e9f8581c8eba75c`; the worktree was clean before execution.
- Commands: `python --version`; `python -m pytest --version`; `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Environment: Windows host, Python 3.14.3, pytest 8.4.2.
- Result: **2 passed, 0 failed** in 5.28 seconds. One warning: `pytest-asyncio` emitted `DeprecationWarning` for `asyncio.get_event_loop_policy`, with a reference to removal in Python 3.16.
- This is exact clean-head local synthetic evidence. It does not run native WSL transfer, the S4 signer socket, report-bound native QA, or the exact-head VST gate.
