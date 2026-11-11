# U5-4: review-loop driver

Module: `tools/vst/review_loop.py` (`run_review_loop`). Tests: `tests/vst/test_u5_review_loop.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint, so no result is claimed; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-4): the loop resubmits with `iteration_of` until local checks are clean for the declared coverage or an iteration cap is reached; the cap result is BLOCKED, never a pass.

## What the driver is

A decision loop for one worker attempt. It applies nothing and starts nothing: every external action is injected.

| Injected | Contract |
|---|---|
| `submit(ReviewRequest)` | runs ONE local review of the current candidate and returns the parsed `uc.role-result.v1` document (`tools/uc/contracts.py`, the output of `tools/uc/router.py review`). The request carries `request_id`, `head`, `iteration_of`, `declared_coverage`, `local_index`, `iteration_index`. |
| `verify_report(doc)` | receives a deep copy of the validated report (it cannot alter what is judged) and says whether the report's integrity (signature or digest) was verified. Only the exact value `True` counts; `False`, any other value or a raise means unverifiable. Required: there is no default that skips verification. |
| `fixer(FixContext)` | optional. Returns a `Candidate` (new head, changed paths, diff bytes, isolation context) for the open findings. The driver never applies it. |
| `gate(**kwargs)` | default `worker_gate.gate_worker_change` (U5-1). Called for every fixer candidate; the verdict is recorded with `PipelineState.record_diff_gate` and must be `ACCEPTED` to continue. A fake may replace it in tests; it must still return a `WorkerGateVerdict`. |
| `clock()` | finite, non-decreasing seconds. Used for `started_at` / `finished_at` and the optional `max_total_seconds` deadline. |
| `on_iteration(summary)` | optional; called after each recorded iteration (a progress hook; resume does not depend on it). |

## Declared coverage

`declared_coverage` is an input: the required set of executor ids (strings matching the contract token pattern `[a-z0-9][a-z0-9_.-]{0,63}`; the ids of `executors[].id` in the report). A required rule set must be mapped to executor ids by the caller (the role table maps roles to executors); the driver compares executor ids only. The set is non-empty, unique and sorted; it is also stored per iteration in `pl_review_iterations.coverage_declared`.

Reported coverage of a report is the set of executor ids whose status is `COMPLETE` in every role that lists them. Reported coverage equals or exceeds the declaration when the declared ids are a subset of it (extra executors do not hurt).

## Per-iteration judgement (`judge_report`)

A report that is not a valid `uc.role-result.v1` (also a `uc.blocked.v1` envelope, `None`, a wrong shape, an exit code that disagrees with the roles) is UNUSABLE: the loop ends BLOCKED (`BAD_REPORT`, `SUBMIT_BLOCKED`) and nothing is recorded, because no judgeable report exists (a transient failure must not leave a permanent dead end in the store). Otherwise the iteration gets these reasons, in this order, for every rule that applies:

| Reason | When |
|---|---|
| `REQUEST_MISMATCH` | the report's `request_id` is not the request's |
| `HEAD_MISMATCH` | the report's `base_revision` is not the head that was submitted |
| `PURPOSE_NOT_RECEIPT` | the report's `purpose` is not `receipt` (an advisory report is never CLEAN) |
| `PATHS_MISMATCH` | the report's `changed_paths_sha256` is not the expected digest given to the loop (`changed_paths_sha256`, from `uc.contracts.changed_paths_sha256`) |
| `REPORT_STALE` | the report's `iteration_id` was already seen in this loop (a replayed old report) |
| `SIGNATURE_UNVERIFIED` | `verify_report` did not return exactly `True` |
| `FINDINGS_OPEN` | at least one finding in any role |
| `MODEL_RESIDUAL_OPEN` | any role has a non-empty `model_residual` |
| `COVERAGE_PARTIAL` | any role is PARTIAL, NOT_COVERED, NOT_RUN or BLOCKED, or lists uncovered tokens |
| `DECLARED_EXECUTOR_MISSING` | a declared executor id is not covered (missing, partial, blocked or not run) |
| `EXIT_NOT_ZERO` | the report's exit code is not 0 |

Verdict of the iteration (the `PipelineState` vocabulary): any of the first six reasons (request, head, purpose, paths, stale, signature) gives `BLOCKED` (the report cannot be trusted, so its findings are not trusted either); otherwise findings give `FINDINGS`; otherwise any other reason gives `PARTIAL`; no reason gives `CLEAN`. CLEAN therefore means: findings empty, residual empty, every role CLEAN with nothing uncovered, every declared executor COMPLETE, the right request and head, a fresh iteration id, verified integrity. Partial or unsupported coverage can never be CLEAN, because a CLEAN role in the contract needs complete executors, no residual and nothing uncovered, and the gap reasons above are checked again by the driver.

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

Result fields: `verdict`, `reasons` (code, ASCII-escaped detail), `iteration_count`, `iterations` (per iteration: id, `iteration_of`, head, findings count and the findings, finding-set digest, coverage, missing coverage, verdict, reasons, replayed, started_at, finished_at), `cap_requested`, `cap_effective`, `cap_clamped`, `final_head`, `submit_calls`, `fixer_calls`, `gates`, `replayed`, `changed_paths_sha256` (U6-0). `to_dict()` is JSON-serialisable.

`changed_paths_sha256` is the digest of the sorted reviewed paths every report was checked against: the loop input, or, for a result rebuilt from the store, the digest stored in the review facts (which the replay has already cross-checked against the input; a difference is `RESUME_MISMATCH`). A CLEAN `ReviewLoopResult` cannot be constructed without a 64 lowercase hex value; a BLOCKED one carries it when the input was valid and `None` otherwise (for example `BAD_INPUT`). `tools/vst/final_package.py` compares it with the digest of its own `changed_paths` (`REVIEW_PATHS_MISMATCH`).

## Bounds

Cap: an `int` (not a bool) of at least 1, else `BLOCKED CAP_INVALID` and nothing runs. A cap above `MAX_ITERATIONS` (10) is clamped to 10 and `cap_clamped` is true. Every pass of the loop either ends or adds one iteration, so one call submits at most 10 times. `max_total_seconds` adds an optional wall-clock bound (`DEADLINE`).

## Stop, epoch, failures

- Stop path: the story is checked before every submit and every fix; a stop between the check and the record is caught by the record (`StoreError kind='stopped'`), so a clean report that arrives after a stop is never a pass. Result `BLOCKED STOPPED`, no further submit.
- Epoch: the guard compares the caller's epoch with the story's before every external action, and every recorded step is epoch-checked again by `PipelineState`. `BLOCKED EPOCH_STALE`.
- An exception from `submit`, `fixer`, `gate`, `clock`, `on_iteration` or the store becomes BLOCKED with a stable code and an ASCII-escaped, 300-character detail (non-printable and non-ASCII characters become `\xNN`, `\uNNNN`, `\UNNNNNNNN`); an unexpected error is `INTERNAL_ERROR`. A `BaseException` that is not an `Exception` (a process death) propagates on purpose and leaves the recorded rows for a replay.
- Invalid input (`state` not a `PipelineState`, malformed ids or heads, empty or malformed declaration, missing callables) is `BAD_INPUT`; nothing runs.

## Idempotency and replay

Step ids depend only on the attempt and the story-level iteration index, so the same call after a crash writes the same ids and `PipelineState` replays them (same id and payload returns the stored result, nothing is written twice). The story is the scope key of the step table, so the story id is not repeated inside the id.

The loop's facts live in the store, in the same transaction as the row. `PipelineState.record_review_iteration` and `record_diff_gate` take an optional `facts` object (additive; no schema change: it is part of the step payload digest and of the stored step result, read back with `get_step`):

- review step `rl-a<attempt>-i<index>`: AEVE iteration id, the iteration_of id, the reviewed head, coverage, missing coverage, finding-set digest, findings count, the findings (first 200) with a `findings_truncated` flag, reasons and the expected paths digest;
- gate step `rl-a<attempt>-i<index>-gate`: base head, candidate head, diff sha256, verdict and reason codes.

A repeated call rebuilds every summary from the store (`list_review_iterations` plus `get_step`); nothing that only existed in memory is needed, so a crash between the row and `on_iteration` leaves nothing unresumable. Rebuilt facts are checked: the finding digest is recomputed from the stored findings when they are not truncated, the finding count and verdict must equal the row, the declared coverage and the paths digest must equal the current ones, the iteration chain, the first head (the initial head), the head continuity (after a FINDINGS iteration the next head must be the stored ACCEPTED gate's candidate head) and the absence of repeated iteration ids are checked, and a CLEAN iteration must have no reasons and cover the declaration. Any difference is `RESUME_MISMATCH`. A recorded row without these facts (not written by this driver) is also `RESUME_MISMATCH`. A replayed iteration is never submitted again, and `final_head` is always a head that is stored (a reviewed head or a stored gate candidate). `ReviewLoopResult.replayed` is true when the whole result came from the store with no new submit and no fixer call.

The optional `resume` argument is only a cross-check: when given it must have one summary per recorded iteration and each must equal the rebuilt one (ignoring timestamps and the replayed flag); otherwise `RESUME_MISMATCH`.

A recorded gate is not run again. If the last iteration has open findings and its gate step exists, the stored decision is adopted: ACCEPTED continues with the stored candidate head and does not call the fixer; REFUSED or BLOCKED is reported again (`GATE_REFUSED`, `GATE_BLOCKED`) without calling the fixer. A fixer that did run but whose gate record never happened is simply run again (its output was never accepted).

Concurrent loops for one attempt: if a freshly submitted iteration or gate step turns out to be already recorded (same step id, same payload: `replayed` true, or another payload: conflict) the loop ends `BLOCKED RESUME_MISMATCH`; the store's consecutive-index rule decides which loop owns the iteration.

`iteration_of` has two forms, both kept: the AEVE `iteration_of` sent to `submit` is the previous report's `iteration_id` inside the attempt (None for the first iteration of an attempt); the pipeline row's `iteration_of` is the previous story-level index (required by the table for every index above 1). The request id is `rl-` plus the first 40 hex of sha256(story id, NUL, attempt number), constant for an attempt, which matches the router's rule that a request id is bound to one reviewed root and one content per `iteration_of`.

## Inputs added by the remediation

- `changed_paths_sha256` (required, 64 hex): the digest of the sorted reviewed paths that every report must carry. It is fixed for the loop: the reviewed path set is the declared scope of the change; a fixer candidate that touches other paths is a gate matter (scope), not a digest change.
- `manifest_sha256` is required (64 lowercase hex) whenever a fixer is given, otherwise `BAD_INPUT`.
- `FixContext.truncated` tells a fixer that only the first 200 findings were kept; the finding digest always covers all findings.

## Limits

- All tests are NOT_RUN; nothing was executed. `tools/uc` and AEVE are not called by the driver; the real submit (router plus adapter) is a caller's wiring that this task does not provide.
- `verify_report` is an injected predicate. The `uc.role-result.v1` contract carries no signature, so what "verified" means (for example a receipt signature or a digest check by the caller) is outside this module.
- Staleness is detected by repeated `iteration_id`, by head and by request id; the report has no timestamp, so there is no age check beyond the optional total deadline.
- No-progress is literal: the same head and the same finding set twice. The same findings at a new head (a fixer that changes the head without fixing anything) are not no-progress; that case ends at the cap.
- The facts in the store are written by the driver itself; a person with write access to the database can still forge them. They are consistency-checked (digest recomputed, chain, head continuity), not signed.
- The facts step and the row are one transaction; a crash can lose only the submit whose record never happened, and that submit is run again on replay.
- The paths digest is one value per loop; a loop whose scope changes per iteration needs a new attempt.
- Concurrent drivers for one story are refused by the store (consecutive index rule, one STARTED attempt), not coordinated here.
- Test evidence of the fixer's candidate (U5-5), receipts and the package are not part of this task.
