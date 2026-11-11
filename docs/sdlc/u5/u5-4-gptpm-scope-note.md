# U5-4 GPT-PM code review scope

Task: U5-4, review-loop driver. Base: U5-3 approved head, head = current HEAD. Review the delta only: tools/vst/review_loop.py, docs/sdlc/u5/REVIEW_LOOP.md, tests/vst/test_u5_review_loop.py (tests are NOT_RUN; judge by reading), tools/qa/build_registry.py (two map lines), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: `run_review_loop`, a decision loop for one worker attempt with every external action injected (`submit`, `verify_report`, optional `fixer`, `gate`, `clock`, `on_iteration`). It resubmits with `iteration_of` (the previous report's iteration id, None for the first), records each iteration with `PipelineState.record_review_iteration` under step ids derived from attempt and story-level iteration index, judges each `uc.role-result.v1` report, and returns CLEAN or BLOCKED. CLEAN needs no findings, no residual, every role CLEAN, every declared executor COMPLETE, the right request and head, a fresh iteration id and a verified report. The cap result is BLOCKED `ITERATION_CAP`, never CLEAN. Also: `NO_PROGRESS`, `STOPPED`, `EPOCH_STALE`, exceptions as BLOCKED with ASCII-escaped details, a hard cap maximum of 10, replay after a crash that does not resubmit recorded iterations. Fixer candidates go through `worker_gate.gate_worker_change` (U5-1) and the verdict is recorded with `record_diff_gate`; the driver applies nothing. `tools/vst/pipeline_state.py`, `worker_gate.py`, `patch_proposals.py`, `store.py`, `tools/uc/*` and AEVE are unchanged (the new code only imports them).

Interpretation decisions:
- The report is the validated `uc.role-result.v1` document (router output); declared coverage is a set of executor ids. A rule set must be mapped to executors by the caller.
- Report integrity is an injected `verify_report` predicate, required, and only the exact value `True` counts, because the contract has no signature field.
- An unusable report (not valid, blocked envelope) or a failure of submit, fixer, gate or clock ends the loop BLOCKED and records no iteration: no judgeable report exists, and a transient failure must not become a permanent dead end in the store.
- A valid report that is stale, for another head or request, or unverifiable is recorded as a `BLOCKED` iteration and the same head is reviewed again; the loop still ends at the cap or at `NO_PROGRESS`. Its findings are not trusted and not given to the fixer.
- PARTIAL and BLOCKED iterations have nothing to fix; they resubmit the same head, bounded by `NO_PROGRESS` and the cap.
- No-progress is literal (same head and same finding set twice, or a fixer that returns the head it was given). The same findings at a new head run to the cap.
- The pipeline tables hold neither the AEVE iteration id nor the head, so a replay needs the earlier summaries (`resume`, from `on_iteration` or an earlier result); they are cross-checked with the recorded rows and any difference is BLOCKED `RESUME_MISMATCH`.
- The pipeline row `iteration_of` is the previous story-level index (the table requires it above index 1); the review request `iteration_of` is the previous report id inside the attempt.
- The driver adds an optional total deadline (`max_total_seconds`) so the injected clock has a bounding use; it is not required by the acceptance text.

Limits: nothing was run (the SQL path through `PipelineState`, the real worker gate on a minimal input and every test are unproven); no real submit wiring (router plus adapter) is provided; no age check on reports; `verify_report` semantics are the caller's.

Tests: written, NOT_RUN (running tests is forbidden by the operator). Evidence is static reading and `ast.parse` only. `docs/qa/categories.json` was not regenerated (running the registry builder is forbidden), so it does not list the new test file yet.
