# 0296 S4 timeout selector policy correction

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch before change:** `s4-reproducible-qa-automation`  
**Observed non-approving matrix candidate:** `e1a427884b9c954d58114ca8d281f38a07da1851`

## Problem

The QA registry generator's `POLICY_NOT_RUN` map did not include `tests/vst/test_s2_runner_lifecycle.py::test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`. The full-category Windows integration invocation at `e1a4278` included this selector, despite the active S4 continuation prohibiting timeout-selector execution. The test name and report establish it as a timeout-recovery scenario. The precise category-run command and concrete traceback are not established in the evidence currently available to this change; do not infer a product defect from its reported failure.

## Change

- Add the exact selector to `tools/qa/build_registry.py` `POLICY_NOT_RUN` with reason: timeout recovery is prohibited for this S4 run.
- Regenerate `docs/qa/categories.json` from the committed source. The selector remains in the total inventory but moves out of assigned runnable categories and into policy `NOT_RUN`.
- Update the backlog, state, decision log, lessons log and document registry with the policy correction and its evidence limits.

## Evidence and verification

- The e2e-runner reported Windows functional `PASS` (90/90 selectors), API `PASS` (688/688), E2E `PASS` (55/55), and integration `FAIL` (36/42 selectors; six exact failure IDs). The reported IDs in `tests/vst/test_s2_runner_lifecycle.py` are `test_bounded_source_preflight_rejects_before_pack_or_index_writer`, `test_cumulative_target_storage_cap_rejects_before_pack_process_starts`, `test_hook_free_publication_transfers_source_only_commit_without_running_pre_push`, `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`, `test_source_object_alternates_are_rejected_before_pack_or_index_writer`, and `test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs`. The report artifacts are `D:\Temp\vst_s4_acceptance_e1a4278_20261025T\docs\sdlc\evidence\qa\integration.report.jsonl`, `integration.stdout.txt`, and `integration.stderr.txt`. The agent reported only summary output, so root causes for these six failures are not yet verified. These observations come from the delegated agent report; the entire run is excluded from S4 acceptance because it included the prohibited selector.
- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`. Its result is recorded after execution below.
- No tests, checks, or category runners were run for this change.
- Generator result: exit 0, wrote `docs/qa/categories.json`. The regression inventory remains 935 selectors: 883 assigned runnable plus 52 policy `NOT_RUN` (previously 884 plus 51). The separate seeded-failure category has 3 selectors, so the complete `tests` list contains 938 entries.
- The pre-existing untracked file `docs/sdlc/evidence/s2-functional-test-run.md` is preserved and is not part of this change.

Documentation index generation: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 after this record was added and indexed 252 Markdown documents. This is documentation inventory generation only.

## Acceptance and next action

The registry policy now protects the execution boundary. All reports at `e1a4278` remain non-approving. Regenerate and commit the registry, then rerun the full assigned matrix at the corrected exact head; do not invoke the timeout-recovery selector. Preserve all 52 policy `NOT_RUN` rows.
