# 0259 S4 semantic report digest

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this change:** `s4-reproducible-qa-automation` / current QA source candidate `d1bd2cf32b998ff16f15ab054b844382d0e7e55b`

## What changed

- Excluded `artifact_digests` and `artifact_sizes` from the normalized cross-run semantic digest.
- Kept both fields in serialized report rows; the runner still verifies each exact SHA-256 and byte size against the captured stdout/stderr range.
- Updated the QA design and S4 plan to distinguish semantic outcome identity from exact per-run output integrity.

## Why

The repeated E2E fixture ran the same synthetic selector twice. Pytest stdout includes elapsed time, so the exact output chunk may differ between equivalent runs. The report's normalized digest included that run-specific chunk hash and size, making semantic digests differ even though selectors and outcomes matched. The exact chunks still need independent integrity verification; they do not need to be part of the cross-run semantic digest.

## Evidence and verification

- At exact test candidate HEAD `d1bd2cf32b998ff16f15ab054b844382d0e7e55b`, all six categories ran. The E2E suite included two repeated synthetic runs and failed `test_s4_e2e_cli_native_collection_binds_candidate_and_repeatable_artifact_chunks`. The agent's static read correlated the failure with timing-bearing pytest output and the existing digest projection. The runner's stdout showed elapsed-time summaries; the exact assertion trace was not retained because the runner uses `--tb=no --no-summary`.
- The `functional-test-reviewer` authored a test using differently sized raw captures; it verifies each captured range against its stored digest and size while requiring equal semantic digests. The E2E author retained per-run exact range/hash validation and semantic digest equality.
- Tests were not run after this code/test change. Product and test changes remain uncommitted at this record's preparation point; runtime confirmation is pending.
- The pre-existing untracked S2 evidence file remains untouched. Development stayed in `D:\Repo\Virtual_scrum_team`; no worktree was created or used.

## Acceptance and next steps

- VST-037: exact per-run hash and size integrity remains in the report and is verified against bytes; cross-run semantic normalization no longer depends on raw output timing.
- VST-033–036: runtime confirmation of this fix and the accompanying stale-test corrections remains pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Test authors/executor: `functional-test-reviewer` and `e2e-runner`.
- Next: commit the product fix, commit corrected test sources, regenerate `docs/qa/categories.json`, and rerun the six-category suite on the new exact head.
