# Change 0363 — Pass the verified wheelhouse path into QA test children

## What changed

- `tools/qa/run.py`: `_pytest_command()` now receives the already validated dependency wheelhouse and exposes its path to the bounded pytest child as `VST_QA_DEPENDENCY_WHEELHOUSE`.

## Why

The E2E synthetic candidate archives committed runner source from `BASELINE_HEAD`. Updating that fixture baseline to source commit `7929bc0` includes the cache-prefix fix, but it also requires the current `--dependency-wheelhouse` CLI argument. The nested E2E `_run_cli` helper must pass the same verified wheelhouse that the report-bound run already validated. A dedicated child environment variable conveys that path without inventing a second wheel source or allowing a download/install action.

## Affected contracts and paths

- Nested report-bound test runners receive the exact wheelhouse validated by their parent run.
- `tools/qa/run.py`, `_pytest_command()` environment handoff.
- The test helper consumes the value only to pass `--dependency-wheelhouse` to its nested synthetic runner; test-source changes and registry provenance are recorded separately.

## Verification state

- Evidence: using the updated fixture baseline `7929bc0` reached the nested CLI but failed before selector execution because the synthetic `_run_cli` omitted the required `--dependency-wheelhouse` argument; the dependency target remained unchanged at 495 locked files (SHA-256 `5336e1e65b39a62348160c2f5cdd56a622f8c066685f6232f55bd334c3518b84`).
- The source handoff and corresponding test-helper update require focused report-bound verification by the designated E2E runner. No selector result or AC-17 acceptance is upgraded by this change alone.
- Preserve all 52 policy-excluded selectors as `NOT_RUN`.

## Ownership and next action

- Accountable owner: operator.
- Production implementation: Codex.
- Test author and executor: designated E2E runner.
- Next: commit test-helper coverage and its record, refresh the selector registry separately, then rerun the exact-candidate E2E report with a fresh target and verify pre/post dependency hashes.
