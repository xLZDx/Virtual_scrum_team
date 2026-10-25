# 0174 — Exact-head AC-7 API signature and seeded evidence

## Acceptance coverage

Tested the API category plus seeded-failure category at committed HEAD `7b1b0027cf07a33a8325017de08dd74c81fb0681`.

| Criterion | Exact mapped falsifiers in this run | Result / limit |
|---|---|---|
| AC-1 | Registry single primary assignment, duplicate assignment, unknown node, missing required IDs, exact manifest projection | Passed; no duplicate/missing required ID was accepted. |
| AC-2 / AC-8 | Representative contracts, gate, store, runner, supervisor selectors; network API is `UNSUPPORTED` | Passed for mapped Python paths. The full callable inventory is recorded separately and category remains `PARTIAL` pending reconciliation. |
| AC-3 | Provenance outside candidate history; committed registry resolution | Passed. |
| AC-7 | `test_stale_head_one_receipt_is_a_hard_reason_and_the_slot_is_unmet`; `test_forged_unsigned_receipt_rejected`; runner nonzero exit; supervisor restart/recovery | Passed, covering stale evidence, signature failure, invalid command result, and restart behavior. |
| AC-11 | Duplicate/missing/unresolvable registry IDs and projection mismatch | Passed for focused registry contracts. Full aggregate/report-bound regression remains outside this run. |
| AC-12 | `test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation` against the one committed hash-bound fixture | Passed for the catalog's one fixture; no mutation claim. |

## Exact command and runtime

Windows x64, PowerShell, Python 3.14.3, pytest 8.4.2. The installed `pytest-asyncio` plugin emitted one deprecation warning (`asyncio.get_event_loop_policy`); it did not affect outcomes.

```powershell
$apiIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.api.test_ids
$seedIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.'seeded-failure'.test_ids
python --version
python -m pytest --version
git rev-parse HEAD
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @apiIds @seedIds
```

The command ran 21 required IDs (20 API and one seeded-failure); parametrized cases expanded to 23 collected. Result: **22 passed, 1 skipped, 0 failed** in 8.10 seconds.

The skipped test was separately diagnosed using:

```powershell
python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance
```

Result: **1 skipped**, exact cause `[WinError 1314] A required privilege is not held by the client` while Windows attempted to create a symlink. POSIX symlink behavior is therefore `NOT_RUN` on this host.

## Provenance and limitations

An earlier run on `c310b6098754036eacbe74ea09062cca929163f6` failed 4 registry cases because an integration selector had also been assigned to API. The AC-1 uniqueness rejection was correct; change 0171 replaced that ID with a distinct runner negative-path selector. At `f057020c62211b7787de368f300929b7a35b9838`, 21 passed, 1 skipped, 0 failed. Change 0173 then mapped the existing forged-unsigned gate test required to complete AC-7's applicable signature-failure path. This record gives the final rerun after that mapping.

No product source or test body was changed. API coverage remains `PARTIAL` until the finite source-defined entrypoint inventory is reconciled against registered selectors and concrete gaps; see the API inventory record. Network API is unsupported. Full regression aggregation, report-bound runner, signer socket, receipt and authoritative-gate acceptance remain outside this focused test run.

