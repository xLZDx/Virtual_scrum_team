# MAJOR-002 Fix Approach: Retry failure in resume_epoch_idempotent

## Problem
After resume_epoch_idempotent durably advances the epoch, a transient failure (supervisor.stop, prepare_run error, etc.) leaves the epoch held by an owner with no lease and no recorded intent. On retry:
1. prior_fence_request validation fails with FENCE_REJECTED (epoch mismatch)
2. Resume probe check fails (nonce already consumed)
3. Replay check never runs (logic is after epoch advance)
4. Recovery path is disabled; operator sees "stale fence" instead of "half-applied resume"

## Current code flow (pilot.py:786-920)
1. Lines 795-798: Replay check for 's3_resume' operation
2. Lines 808-870: Extensive pre-epoch validation
3. Lines 875: **PROBLEM**: re-validates prior_fence_request BEFORE epoch advance
4. Lines 881-883: resume_epoch_idempotent ADVANCES EPOCH DURABLY
5. Lines 884-920: Post-epoch steps (supervisor start, _execute_attempt, etc.)
   - If any fail, epoch is advanced but work not recorded

## Fix strategy

### Phase 1: Restructure replay detection
- Move the 's3_resume' replay check to BEFORE all pre-epoch validation
- Make it check both 's3_resume' AND epoch-advance idempotency key
- If found, skip validation and return the stored result directly

### Phase 2: Conditional pre-epoch validation  
- After replay check, add: poch_already_advanced = store.has_durable_epoch(epoch_operation_key)
- Make prior_fence_request validation conditional: only run if epoch NOT already advanced
- Same for probe check (only if epoch not advanced)

### Phase 3: Record half-applied state
- Create an 's3_resume_intent' operation record BEFORE any post-epoch step
- Record: epoch, owner, expected_new_epoch, checkpoint, recovery_info
- On post-epoch failure, mark this as PARTIAL/RECONCILIATION_REQUIRED
- On retry, find this record and either resume or roll back safely

### Phase 4: Update error messaging
- If epoch_already_advanced, return specific error: "resume epoch already advanced; awaiting recovery confirmation"
- If resume_intent found in PARTIAL state: "prior resume incomplete at epoch X; will retry from checkpoint"

## Code changes required
- Three new Store methods (or reuse existing):
  - has_durable_epoch(operation_key) → bool
  - lookup_resume_intent(epoch_operation_key) → dict | None
  - record_resume_intent(key, data) → bool

- Refactor resume() method: ~50-100 LOC rearrangement + 20-30 LOC new logic

## Risk assessment
- **MEDIUM complexity**: Core logic restructuring but no new Store operations needed if using existing methods
- **Fail-closed**: All new code paths return INCONCLUSIVE or replay existing states; no new acceptance paths
- **Testing**: Needs synthetic cases for (supervisor.stop after epoch, prepare_run after epoch, etc.)

## Effort estimate
- Implementation: ~2 hours (design, code, local test)
- Test authoring/verification: ~1 hour (functional-test-reviewer)
- Code review: ~30 minutes

## Recommendation
This is a substantial but well-scoped fix. Implement only if S3 completion is gated on MAJOR-002 remediation, or defer as future hardening if operator prefers S3 delivery with this constraint documented.
