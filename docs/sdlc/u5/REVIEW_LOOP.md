# U5-4: review-loop driver

Module: `tools/vst/review_loop.py` (`run_review_loop`). Tests: `tests/vst/test_u5_review_loop.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint, so no result is claimed; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-4): the loop resubmits with `iteration_of` until local checks are clean for the declared coverage or an iteration cap is reached; the cap result is BLOCKED, never a pass.

## What the driver is

A decision loop for one worker attempt. It applies nothing and starts nothing: every external action is injected.

| Injected | Contract |
|---|---|
| `submit(ReviewRequest)` | runs ONE local review of the current candidate and returns the parsed `uc.role-result.v1` document (`tools/uc/contracts.py`, the output of `tools/uc/router.py review`). The request carries `request_id`, `head`, `iteration_of`, `declared_coverage`, `local_index`, `iteration_index`. |
| `verify_report(doc)` | says whether the report's integrity (signature or digest) was verified. Only the exact value `True` counts; `False`, any other value or a raise means unverifiable. Required: there is no default that skips verification. |
| `fixer(FixContext)` | optional. Returns a `Candidate` (new head, changed paths, diff bytes, isolation context) for the open findings. The driver never applies it. |
| `gate(**kwargs)` | default `worker_gate.gate_worker_change` (U5-1). Called for every fixer candidate; the verdict is recorded with `PipelineState.record_diff_gate` and must be `ACCEPTED` to continue. A fake may replace it in tests; it must still return a `WorkerGateVerdict`. |
| `clock()` | finite, non-decreasing seconds. Used for `started_at` / `finished_at` and the optional `max_total_seconds` deadline. |
| `on_iteration(summary)` | optional; called after each recorded iteration so the caller can persist the summary for a later `resume`. |

## Declared coverage

`declared_coverage` is an input: the required set of executor ids (strings matching the contract token pattern `[a-z0-9][a-z0-9_.-]{0,63}`; the ids of `executors[].id` in the report). A required rule set must be mapped to executor ids by the caller (the role table maps roles to executors); the driver compares executor ids only. The set is non-empty, unique and sorted; it is also stored per iteration in `pl_review_iterations.coverage_declared`.

Reported coverage of a report is the set of executor ids whose status is `COMPLETE` in every role that lists them. Reported coverage equals or exceeds the declaration when the declared ids are a subset of it (extra executors do not hurt).

## Per-iteration judgement (`judge_report`)

A report that is not a valid `uc.role-result.v1` (also a `uc.blocked.v1` envelope, `None`, a wrong shape, an exit code that disagrees with the roles) is UNUSABLE: the loop ends BLOCKED (`BAD_REPORT`, `SUBMIT_BLOCKED`) and nothing is recorded, because no judgeable report exists (a transient failure must not leave a permanent dead end in the store). Otherwise the iteration gets these reasons, in this order, for every rule that applies:

| Reason | When |
|---|---|
| `REQUEST_MISMATCH` | the report's `request_id` is not the request's |
| `HEAD_MISMATCH` | the report's `base_revision` is not the head that was submitted |
| `REPORT_STALE` | the report's `iteration_id` was already seen in this loop (a replayed old report) |
| `SIGNATURE_UNVERIFIED` | `verify_report` did not return exactly `True` |
| `FINDINGS_OPEN` | at least one finding in any role |
| `MODEL_RESIDUAL_OPEN` | any role has a non-empty `model_residual` |
| `COVERAGE_PARTIAL` | any role is PARTIAL, NOT_COVERED, NOT_RUN or BLOCKED, or lists uncovered tokens |
| `DECLARED_EXECUTOR_MISSING` | a declared executor id is not covered (missing, partial, blocked or not run) |
| `EXIT_NOT_ZERO` | the report's exit code is not 0 |

Verdict of the iteration (the `PipelineState` vocabulary): any of the first four reasons gives `BLOCKED` (the report cannot be trusted, so its findings are not trusted either); otherwise findings give `FINDINGS`; otherwise any other reason gives `PARTIAL`; no reason gives `CLEAN`. CLEAN therefore means: findings empty, residual empty, every role CLEAN with nothing uncovered, every declared executor COMPLETE, the right request and head, a fresh iteration id, verified integrity. Partial or unsupported coverage can never be CLEAN, because a CLEAN role in the contract needs complete executors, no residual and nothing uncovered, and the gap reasons above are checked again by the driver.

## Loop

```
iteration i (1-based inside the attempt):
  guard: story exists, epoch equals the story epoch, story not stopped      (before every external action)
  deadline check (only when max_total_seconds is set)
  submit with iteration_of = id of iteration i-1 (None for i = 1), head = current candidate
  judge, record with record_review_iteration (step id rl-a<attempt>-i<index>)
  CLEAN                       -> result CLEAN (only after the row was recorded)
  i >= cap                    -> BLOCKED ITERATION_CAP
  same head and same finding set as iteration i-1 -> BLOCKED NO_PROGRESS   (both are listed when both apply, cap first)
  FINDINGS                    -> no fixer: BLOCKED NO_FIXER
                                 fixer -> Candidate (same head as given: BLOCKED NO_PROGRESS)
                                 gate -> record_diff_gate (step rl-a<attempt>-i<index>-gate, id rl-a<attempt>-g<index>)
                                 not ACCEPTED: BLOCKED GATE_REFUSED / GATE_BLOCKED / GATE_NOT_ACCEPTED; else continue
  PARTIAL or BLOCKED          -> the same head is reviewed again (nothing to fix; bounded by NO_PROGRESS and the cap)
```

The result verdict is only `CLEAN` or `BLOCKED`. `ReviewLoopResult` refuses at construction a CLEAN without a CLEAN last iteration that covers the declaration, without reasons and without findings, and a BLOCKED without a reason, so no code path can upgrade a verdict. The cap result is BLOCKED `ITERATION_CAP` even when the last report looks clean but is unverifiable.

Result fields: `verdict`, `reasons` (code, ASCII-escaped detail), `iteration_count`, `iterations` (per iteration: id, `iteration_of`, head, findings count and the findings, finding-set digest, coverage, missing coverage, verdict, reasons, replayed, started_at, finished_at), `cap_requested`, `cap_effective`, `cap_clamped`, `final_head`, `submit_calls`, `fixer_calls`, `gates`. `to_dict()` is JSON-serialisable.

## Bounds

Cap: an `int` (not a bool) of at least 1, else `BLOCKED CAP_INVALID` and nothing runs. A cap above `MAX_ITERATIONS` (10) is clamped to 10 and `cap_clamped` is true. Every pass of the loop either ends or adds one iteration, so one call submits at most 10 times. `max_total_seconds` adds an optional wall-clock bound (`DEADLINE`).

## Stop, epoch, failures

- Stop path: the story is checked before every submit and every fix; a stop between the check and the record is caught by the record (`StoreError kind='stopped'`), so a clean report that arrives after a stop is never a pass. Result `BLOCKED STOPPED`, no further submit.
- Epoch: the guard compares the caller's epoch with the story's before every external action, and every recorded step is epoch-checked again by `PipelineState`. `BLOCKED EPOCH_STALE`.
- An exception from `submit`, `fixer`, `gate`, `clock`, `on_iteration` or the store becomes BLOCKED with a stable code and an ASCII-escaped, 300-character detail (non-printable and non-ASCII characters become `\xNN`, `\uNNNN`, `\UNNNNNNNN`); an unexpected error is `INTERNAL_ERROR`. A `BaseException` that is not an `Exception` (a process death) propagates on purpose and leaves the recorded rows for a replay.
- Invalid input (`state` not a `PipelineState`, malformed ids or heads, empty or malformed declaration, missing callables) is `BAD_INPUT`; nothing runs.

## Idempotency and replay

Step ids depend only on the attempt and the story-level iteration index, so the same call after a crash writes the same ids and `PipelineState` replays them (same id and payload returns the stored result, nothing is written twice). The story is the scope key of the step table, so the story id is not repeated inside the id.

Iterations already recorded for the attempt are not submitted again. The pipeline tables do not hold the AEVE iteration id, the head or the findings, so the driver needs them back: the caller passes the earlier summaries as `resume` (it gets each from `on_iteration` or from an earlier result's `iterations`). The driver cross-checks every summary with the recorded row (index, step id, verdict, finding count, declared coverage, `iteration_of` of the row and the chain of ids, first head, no repeated id, a CLEAN summary with reasons or missing coverage is refused). Any difference is `RESUME_MISMATCH`; fewer summaries than recorded rows is `RESUME_REQUIRED`; a cap smaller than the recorded count is `ITERATION_CAP`. After replay the loop continues from the last summary: a replayed CLEAN returns CLEAN without any call; a replayed non-clean iteration goes through the same decision (cap, no progress, fixer). The fixer is called again for the last replayed iteration if it still needs a fix; the gate step replays when the candidate and verdict are identical and is a `STORE_ERROR conflict` (BLOCKED) when they are not.

`iteration_of` has two forms, both kept: the AEVE `iteration_of` sent to `submit` is the previous report's `iteration_id` inside the attempt (None for the first iteration of an attempt); the pipeline row's `iteration_of` is the previous story-level index (required by the table for every index above 1). The request id is `rl-` plus the first 40 hex of sha256(story id, NUL, attempt number), constant for an attempt, which matches the router's rule that a request id is bound to one reviewed root and one content per `iteration_of`.

## Limits

- All tests are NOT_RUN; nothing was executed. `tools/uc` and AEVE are not called by the driver; the real submit (router plus adapter) is a caller's wiring that this task does not provide.
- `verify_report` is an injected predicate. The `uc.role-result.v1` contract carries no signature, so what "verified" means (for example a receipt signature or a digest check by the caller) is outside this module.
- Staleness is detected by repeated `iteration_id`, by head and by request id; the report has no timestamp, so there is no age check beyond the optional total deadline.
- No-progress is literal: the same head and the same finding set twice. The same findings at a new head (a fixer that changes the head without fixing anything) are not no-progress; that case ends at the cap.
- `resume` summaries are trusted only as far as the recorded rows confirm them (see above); the iteration id, head and findings come from the caller.
- Concurrent drivers for one story are refused by the store (consecutive index rule, one STARTED attempt), not coordinated here.
- Test evidence of the fixer's candidate (U5-5), receipts and the package are not part of this task.
