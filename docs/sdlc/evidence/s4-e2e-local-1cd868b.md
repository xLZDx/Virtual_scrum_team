# S4 local synthetic E2E evidence

## Scope and provenance

- Current product/source baseline HEAD: `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771` on branch `s4-native-qa-runner`; this includes coordinator commit 0104, which added static pytest node resolution.
- The first two executions used source HEAD `1cd868b776a50147b951c9282cc73e2868c6bad6`; the third used `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771`. The E2E test source was untracked during all three executions, so this is local synthetic evidence rather than an exact committed-candidate acceptance record.
- E2E test IDs are `tests/qa/test_s4_qa_e2e.py::test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence` and `tests/qa/test_s4_qa_e2e.py::test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution`. The coordinator will add them to the E2E registry with valid source provenance after the test commit.
- Local environment: Windows host, Python 3.14.3, pytest 8.4.2. The named `Ubuntu-24.04` WSL runtime reports Python 3.12.3 and pytest 7.4.4, but the repository source was not transferred there and no S4 native test was run.

## Executed journeys

Command:

```text
python -m pytest -q tests/qa/test_s4_qa_e2e.py
```

The first execution produced one pass and one failure. The synthetic VST slice CLI returned its established 23-scenario report; my new assertion incorrectly expected the shape of a different runner report. This was a **test defect**. I inspected `tools/vst/slice.py` and the existing S1 slice assertions, corrected the test to assert the CLI's actual scenario report, and did not change product code or weaken a product assertion.

The second execution passed both scenarios: **2 passed, 0 failed** in 10.52 seconds. After coordinator commit 0104, a third execution at source HEAD `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771` also passed both scenarios: **2 passed, 0 failed** in 5.79 seconds. Each passing output showed one existing `pytest-asyncio` deprecation warning. The slice journey verified the `APPROVE` happy path, retained earlier failed-attempt evidence after retry, a budget-overrun `MODIFY`, and per-scenario SQLite artifacts. The snapshot CLI journey verified that an unapproved WSL distribution is rejected with exit code 2 before launching WSL or creating a Git bundle.

The first failure and single corrected rerun do not establish flakiness; no test was quarantined. The output contained no trace, screenshot, or network response because these are local CLI journeys; pytest assertion output is the failure evidence.

## Not run and exact dependencies

- Native S4 runner/report/signing and exact-head gate acceptance: `NOT_RUN`. The source transfer was not attempted because S4 provisioning evidence does not identify the runner account, worker group ID, or pre-provisioned private snapshot root. S4 signer socket availability is also not established. No values were inferred from earlier S2 evidence.
- Transfer permissions, bundle digest, exact clone HEAD, worker read-only access, report artifact resolution, and signed receipt behavior: `NOT_RUN` for the same missing S4 provisioning boundary.
- Technical service owner for the S4 private provisioning values is `UNKNOWN` in the in-scope repository records. Accountable task owner is the operator under delegation; Codex is executor. Next step: use the designated S4 provisioning evidence to identify the exact runner account, worker GID, private root, and signer socket, then transfer the committed candidate and run the mapped native E2E category in `Ubuntu-24.04` without installing packages.

No Playwright/Cypress dependency was introduced. No CI, build, migration, package installation, or source transfer was run.
