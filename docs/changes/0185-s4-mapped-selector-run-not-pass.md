# 0185 — Record S4 mapped functional/integration/seeded run as NOT_PASS

## Run identity

- Candidate HEAD: `126b67f3a969a067ac1643bebab2ac669a821eaa`
- Worktree: `D:\Repo\Virtual_scrum_team-s4`, branch `s4-native-qa-runner`
- Shell: Windows PowerShell
- Python: `Python 3.14.3`
- Command: `$manifest = Get-Content docs/qa/categories.json -Raw | ConvertFrom-Json; $ids = @($manifest.categories.functional.test_ids) + @($manifest.categories.integration.test_ids) + @($manifest.categories.'seeded-failure'.test_ids); Write-Output "HEAD=$(git rev-parse HEAD)"; Write-Output "PYTHON=$(python --version 2>&1)"; Write-Output "SELECTOR_COUNT=$($ids.Count)"; python -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin @ids`
- Selected denominator: 27 selectors (functional 14, integration 6, seeded-failure 7).
- Result: **NOT_PASS — 24 passed, 3 failed, 0 skipped**, 82.62 seconds. One pytest-asyncio deprecation warning was emitted; it did not change exit status.

## Exact failures

1. `tests/qa/test_s4_registry_contracts.py::test_s4_seeded_failure_rejects_invalid_manifest_and_records_observation` — `registry.load_seeded_failure_catalog` raised `ContractError: seeded-failure fixtures must map exactly to registered test IDs`. The committed test constructed a synthetic category containing only its own ID while the committed catalog contained seven fixture IDs. This is a test/catalog fixture mismatch. Test-only correction in 0184 now loads the committed full registry/catalog and selects its own fixture.
2. `tests/qa/test_s4_seeded_failures.py::test_seeded_stale_head_rejects_current_gate_decision` — assertion expected `STALE_HEAD`, observed `NO_REJECTION` at `_record`. The fixture passed current epoch 1 while signed receipts from `tests/vst/e1e4_helpers.py` use epoch 2. Inference from those exact fixture values: the test did not isolate stale-head rejection because the epoch also differed. Test-only correction in 0184 sets the current epoch to 2 and recomputes the fixture hash.
3. `tests/qa/test_s4_seeded_failures.py::test_seeded_out_of_scope_diff_fails` — `_fixture()` failed during `registry.load_registry` with `ContractError: QA category 'e2e' source_head is missing, stale, or outside candidate history`. After the run, direct command `git merge-base --is-ancestor 452c8ea8da5545bdce0f584a6b51662b93a33abf 126b67f3a969a067ac1643bebab2ac669a821eaa` returned exit code 0 (`ANCESTOR_EXIT=0`). Thus the registry outcome and direct ancestry evidence conflict. Root cause is **UNKNOWN / NOT_VERIFIED**; no category/source change was made. Coordinator assigned source investigation of bounded `_git_commit_is_ancestor` behavior to the implementation engineer.

## Category observations

All 14 functional selectors and all six integration selectors passed. Of the seven seeded selectors, the committed invalid-manifest test and stale-head and out-of-scope tests failed; the other four seeded tests passed. No API or E2E selector was run by this command. Product code was not changed.

## Follow-up status

Commit `8b5178b1ae021aef4d966fd8bfec48b266273a1c` contains test-only corrections for failures 1 and 2, plus the standard change record/logs/document registry. This record documents the original run and is not evidence that those corrections pass. Per coordinator direction, do not rerun until the registry ancestry investigation is resolved. Keep the exact mapped set `NOT_PASS` until the complete affected denominator is rerun on a committed exact HEAD.

Executor: Codex
