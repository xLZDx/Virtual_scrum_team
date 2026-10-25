# 0264 S4 E2E test fixture corrections

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `e02082396983a5df4178e38fb28516eccce9ff76`

## What changed

- Corrected the E2E helper to locate the loaded locked pytest package rather than deriving the dependency target from `TEMP`, which the bounded runner intentionally replaces with scratch.
- Made the dirty-candidate fixture append bytes so `core.autocrlf` cannot normalize its tracked change away.
- Replaced an ineffective explicit-path `pytest_ignore_collect` fixture with a collection-modification hook that removes the selected item.
- Corrected the duplicate-event assertion to require the runner's actual fail-closed reason and observed collected/executed/passed node accounting.
- Preserved the partial exact-head functional, integration, API and E2E report/stdout evidence and updated current S4 state.

## Why

At exact candidate `e020823`, the E2E category showed 8 failed concrete nodes. A focused traceback run on the five affected selectors passed six of those nodes and isolated two test-fixture/assertion issues. The failures did not establish a product defect.

## Evidence and verification

- Candidate `e02082396983a5df4178e38fb28516eccce9ff76`; Python 3.14.3, pytest 9.0.3, Windows 11 AMD64.
- Full partial-run category outcomes:
  - functional: 58/58 selectors, 113 concrete cases passed; 0 failed/skipped; QA `PASS`.
  - integration: 84 concrete cases, 0 failed, 6 platform skips and 36 policy `NOT_RUN`; QA `FAIL` because those required selectors did not execute.
  - API: 1,492 passed, 0 failed, 5 platform skips and 12 policy `NOT_RUN`; QA `FAIL` because skips and policy rows do not pass acceptance.
  - E2E: 55 selectors, 59 concrete nodes; 51 passed and 8 failed across five selectors; capture complete. Regression and seeded-failure were not run after E2E failed.
- E2E failed selectors: `test_s4_e2e_cli_blocks_dirty_tracked_candidate_before_native_collection`; `test_s4_e2e_cli_fails_closed_on_output_truncation`; `test_s4_e2e_cli_native_collection_binds_candidate_and_repeatable_artifact_chunks`; `test_s4_e2e_cli_preserves_sandbox_dependent_selector_as_not_run`; and parametrized `test_s4_e2e_cli_rejects_uncollected_duplicate_skipped_or_xfailed_selector` cases `[pass-uncollected-uncollected_test_ids]`, `[skip-normal-skipped_test_ids]`, `[xfail-normal-xfail_test_ids]`, `[pass-duplicate-reasons]`.
- Focused diagnostic selected only those five selector IDs (eight concrete cases), with `-vv --tb=long`; it completed `6 passed, 2 failed` in 86.43 seconds. Diagnostic stdout SHA-256: `DB042E89A9CEBDD1E4A2B434469797855737DC4E9AB7A4A1C307CDF42C1C05FC`; stderr was empty with SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`. Raw diagnostic text contains private host paths and is not committed.
- Root cause evidence: bounded runner `tools/qa/run.py` replaces `TEMP`, `TMP`, and `TMPDIR` with the run scratch path. The old E2E helper used `TEMP` to derive the external locked target; under a direct focused invocation it found system TEMP and passed. The full-run discrepancy came from test setup, not runner product behavior.
- Explicit module paths bypass the former `pytest_ignore_collect` hook, so the selector was actually collected and passed. The corrected fixture removes the item during `pytest_collection_modifyitems`.
- The duplicate event was correctly rejected by the runner as `pytest emitted duplicate node IDs`; only the prior assertion string was wrong. The dirty fixture's text rewrite could be normalized clean by `core.autocrlf`; byte append makes the intended Git change deterministic.
- Partial-run evidence was copied from the exact candidate into `docs/sdlc/evidence/qa/` and source/destination hashes matched. SHA-256 values:
  - functional report `1B7390AE775F8678A7ECC1FE6B31522C214F2EDE98C4D9E1BF24EF868B9CE676`; stdout `FEEE141CC4229D541B2C3CF916BA48DFB236BA95DD4A27BADF3E8C801F680340`.
  - integration report `38B4686C90BFC52EF513616CFEE786B7D3FBC4CAF9149CF6436421CB85B2AD1D`; stdout `FEDF3A75BEEC745041208F7DB42BA83B43879DEE18B7D64EF7017D3F4D7B1469`.
  - API report `87C0CD5FC4BA92F4132D0D4179BF112AA6B28EBF043A36DAD95EDE20EAD41C1D`; stdout `016CEE836F5355C6956C7E1522FB319CC3648E4AE682C39B2BB5AE3DE4B6DFD9`.
  - E2E report `DC89B1CA9FA1EBA94DDF6CA73E1293588B62535C845A3D4403619872315172DD`; stdout `8D17830473944889F4C2E821AE964A7FF793593ED7EDAB79D491500A1FC082D7`.
  - All four stderr artifacts were empty for their new output ranges; prior append history is retained. Existing source/destination hashes matched after copying.
- The new E2E fixture changes are included in this change and have not been rerun. No process-kill/timeout selector was selected; policy `NOT_RUN` rows remain intact. Development remains in `D:\Repo\Virtual_scrum_team`; the disposable test-only clone is not a development worktree.

## Acceptance and next steps

- VST-033: corrected helper uses the already-loaded locked pytest package as dependency-target evidence; exact-head behavioral rerun is pending.
- VST-035: integration remains non-approving due to six POSIX/permission skips and policy `NOT_RUN`; E2E test fixtures are corrected but unrun; regression/seeded-failure are still pending.
- VST-037: partial reports and output chunks are retained, but final all-category evidence and gate receipt remain open.
- Accountable task owner: operator under the delegated continuation. Executor: Codex. Test author/executor roles: `functional-test-reviewer` and `e2e-runner`.
- Next: refresh the hash-bound selector manifest after this test-source commit, then rerun all supported categories on a new exact clean candidate. Keep every platform skip and policy `NOT_RUN` non-passing.
