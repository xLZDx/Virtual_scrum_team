# 0180 — Exact-head API and seeded-failure execution evidence

## Acceptance mapping

The source-derived S4.3.2 inventory contains 79 non-private entrypoints across `contracts`, `gate`, `store`, `runner`, and `supervisor`. All 79 map to API-primary falsifiers listed in `docs/qa/python_api_inventory.md`; the canonical API category requires 73 unique selectors. The seeded-failure category separately requires its one committed fixture selector.

| Criterion | Observed mapped behavior | State |
|---|---|---|
| AC-1 | Registry single-primary uniqueness, duplicate rejection, unknown node, missing IDs and exact projection selectors | Passed in focused API lane. |
| AC-2 / AC-8 | API category includes all 73 selectors covering all 79 inventoried Python names; network API remains `UNSUPPORTED` | Static denominator complete; focused Windows invocation has one skipped platform-specific selector, so that scenario remains `NOT_RUN` on this host. |
| AC-3 | Provenance outside candidate history rejects; committed registry resolves all mapped nodes | Passed. |
| AC-7 | Stale-head gate receipt, forged unsigned receipt, malformed contracts, runner failure and lifecycle/replay scenarios | Passed for mapped local scenarios. |
| AC-11 | Duplicate/missing/unresolvable ID and manifest projection contracts | Passed for the selected registry tests. The full regression aggregate/report-bound path is outside this run. |
| AC-12 | Committed `invalid-task-manifest` input hash is loaded, rejected as `INVALID_TASK_MANIFEST`, and its expected/observed observation is recorded under the linked test ID | Passed for the catalog's one fixture. No mutation score or additional seed classes are claimed. |

## Exact command and environment

Machine: Windows x64, PowerShell. Python 3.14.3, pytest 8.4.2. Exact tested HEAD: `d00985f52e30342350a420f20ad96317be9227e1`.

```powershell
$apiIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.api.test_ids
$seedIds = (Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json).categories.'seeded-failure'.test_ids
python --version
python -m pytest --version
git rev-parse HEAD
python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @apiIds @seedIds
```

The focused category invocation selected 74 required IDs (73 API plus one seeded-failure); parameterized cases produced **94 collected**. Result: **93 passed, 1 skipped, 0 failed** in 31.44 seconds. The installed `pytest-asyncio` plugin emitted one deprecation warning (`asyncio.get_event_loop_policy`); it did not change the result.

The skipped selector was rerun with exact reason on the same HEAD:

```powershell
python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py::test_s4_registry_rejects_symlinked_source_components_before_ast_acceptance
```

It remains `NOT_RUN` on Windows because creating the fixture symlink returned `[WinError 1314] A required privilege is not held by the client`. POSIX symlink behavior requires a supported POSIX runtime; no claim of POSIX acceptance is made here.

## Test correction history

The preceding full run at `3df219e4b4cd1700e80b282c0d08fba8205006f5` had 92 passed, 1 skipped, 1 failed. The only failure was the new idempotent-epoch test leaving its fixture's `owner-a` lease active before acquiring as `owner-b`. The product correctly rejected that live-owner conflict. Change 0178 releases the epoch through the public API before the test; the exact final run above passes that selector. No product code was changed.

## Remaining S4 queue and ownership

The API inventory and required selector mapping are complete; the Windows symlink scenario remains `NOT_RUN` due to the exact OS privilege dependency above. The next ordered test-owner queue is:

1. **Functional denominator / AC-7:** current manifest has eight S3 worker-adapter selectors and is `PARTIAL`; derive accepted S4 functional ID inventory beyond S3 and map falsifiers for valid/invalid contracts, stale evidence, and signatures without duplicating API-primary IDs. Owner: functional-test-reviewer; accountable task owner: operator.
2. **Integration denominator / AC-9:** current manifest has one runner receipt-path selector and is `PARTIAL`; identify the accepted local temp-repository/store/gate journey IDs and missing corrupted receipt/chain/artifact cases. Owner: functional-test-reviewer; report-bound signer/gate remains a separate external runtime dependency.
3. **Seeded-failure breadth / AC-12:** one hash-bound invalid-manifest fixture is mapped and passed. Candidate missing fixture classes are stale head, missing receipt, invalid signature, out-of-scope change, skipped test ID, and artifact digest mismatch. Add only fixtures whose unchanged-product rejection can be stably induced and observed; mutation injection stays excluded by AC-13. Owner: functional-test-reviewer.
4. **E2E / AC-9–10:** seven mapped selectors have prior Windows/WSL evidence, but the broader signed sandbox path remains `NOT_RUN`; continue only when signer socket, run-specific manifest and provisioned WSL boundary are available. Owner: e2e-runner / runner evidence workstream; technical service owner remains unknown in project records.
5. **Regression/signing gate / AC-11, AC-14–15:** full aggregate regression and report-bound signer, receipt, authoritative gate remain `NOT_RUN`; these require the named WSL runner/signing environment and are not proven by this local category test run.
