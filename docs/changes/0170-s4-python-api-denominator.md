# 0170 — Expand the mapped Python API denominator

## What changed

`docs/qa/categories.json` now maps five existing falsifying selectors for the S4 plan's named `tools.vst` Python API modules: manifest validation (`contracts`), stale receipt evaluation (`gate`), persisted store reopening (`store`), a successful signed test run (`runner`), and breaker recovery across restart (`supervisor`/store boundary). The API category provenance now points to the committed source base `11cdba225a7eaa4a9c89c16cd990b74a5bda4a47`. Its coverage reason explicitly keeps the category `PARTIAL` because the full public VST API surface is not inventoried or mapped.

No test bodies or product source changed. Existing S4 registry/provenance/selector tests and the single hash-bound seeded invalid-manifest fixture remain mapped. The absent network API remains explicitly `UNSUPPORTED`.

## Why

S4 AC-2 and AC-8 define API coverage as the documented direct Python API and require truthful unsupported status for absent HTTP routes. S4.3.2 names `contracts.py`, `gate.py`, `store.py`, `runner.py`, and `supervisor.py`. Before this update, the API category had no mapped behavior tests for contracts, store, runner, or supervisor and only one gate authority test. The five selectors reuse committed tests whose outcomes can falsify representative accepted API behavior without duplicating tests or editing product code.

## Affected contracts and paths

- S4 plan AC-1, AC-2, AC-7, AC-8, AC-11, AC-12.
- `docs/qa/categories.json` API inventory and provenance.
- Existing test selectors in `tests/vst/test_e1_contracts.py`, `test_e2_gate.py`, `test_e3_store.py`, `test_e4_runner.py`, and `test_s2_runner_lifecycle.py`.
- Existing seeded fixture linkage in `docs/qa/seeded_failures.json` and `tests/qa/test_s4_registry_contracts.py`.

## Verification state

Focused exact-head execution is pending this registry commit. No tests, checks, builds, or migrations were run before committing. The subsequent evidence record must list the exact command, interpreter, committed HEAD, per-selector results, and limitations.

## Decisions and remaining scope

The API category remains `PARTIAL`; adding representative selectors does not establish complete public API breadth. Network API remains `UNSUPPORTED` as the in-scope repository has no HTTP route contract. The seeded-failure category retains one fixture: AC-12 requires every committed fixture to be exercised and observed, which its existing linked test does; it does not require inventing additional defect seeds. Signer/report-bound runtime paths are outside this focused local API run and remain dependent on the named WSL signer/report environment.
