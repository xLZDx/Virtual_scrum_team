# MAJOR-002 Implementation guide: Exact code locations and changes

## File: tools/vst/pilot.py

### Step 1: Add helper method before line 786 (resume method)

~~~python
    def _check_resume_epoch_advanced(self, epoch_operation_key: str) -> bool:
        \"\"\"Check if resume has already durably advanced the epoch.
        
        Used to detect half-applied resume state on retry.
        Returns True if s3_resume_epoch operation is COMPLETED.
        \"\"\"
        try:
            result = self.fixture.store.lookup_idempotent_operation(
                epoch_operation_key, operation="s3_resume_epoch"
            )
            return result is not None and result.get("state") == "COMPLETED"
        except Exception:
            return False
~~~

### Step 2: Modify resume() method around line 873

**Current code (BEFORE):**
~~~ 
    epoch_operation_key = _derived_key("resume-epoch", request.operation_key)
    expected_new_epoch = request.prior_epoch + 1
    if new_request.epoch != expected_new_epoch:
~~~

**Changed code (AFTER):**
~~~
    epoch_operation_key = _derived_key("resume-epoch", request.operation_key)
    
    # MAJOR-002 FIX: Early detection of half-applied resume (epoch already advanced).
    # If resume has already durably advanced the epoch but failed post-epoch,
    # retry must not re-validate against stale prior epoch.
    if self._check_resume_epoch_advanced(epoch_operation_key):
        return _response(new_request, WorkerState.INCONCLUSIVE, error=WorkerError(
            WorkerErrorCode.RECONCILIATION_REQUIRED,
            f"resume epoch {expected_new_epoch} already advanced; "
            "prior work may be half-completed; operator review needed"))
    
    expected_new_epoch = request.prior_epoch + 1
    if new_request.epoch != expected_new_epoch:
~~~

### Step 3: Make prior_fence_request validation conditional (around line 875)

**Current code:**
~~~
    prior_fence_request = replace(
        new_request, epoch=request.prior_epoch, fence=request.prior_epoch,
    )
    rejected = self._validate_request(prior_fence_request)
    if rejected is not None:
        return _response(new_request, WorkerState.BLOCKED, error=rejected.error)
~~~

**Changed code:**
~~~
    # Only validate prior epoch if we haven't already advanced it.
    # If we reach here, epoch is NOT yet advanced (checked above), so validation is safe.
    prior_fence_request = replace(
        new_request, epoch=request.prior_epoch, fence=request.prior_epoch,
    )
    rejected = self._validate_request(prior_fence_request)
    if rejected is not None:
        return _response(new_request, WorkerState.BLOCKED, error=rejected.error)
~~~

## Testing requirements for MAJOR-002 fix

**Synthetic test cases** (for functional-test-reviewer):
1. **Scenario A**: resume() called, supervisor.stop fails mid-way, resume retried → should return INCONCLUSIVE with correct error, not FENCE_REJECTED
2. **Scenario B**: resume() called, prepare_run fails, epoch already advanced, resume retried → same as A
3. **Scenario C**: resume() completes successfully (baseline) → unchanged behavior

**Evidence to collect:**
- WorkerResponse.state == INCONCLUSIVE for failed retries
- WorkerResponse.error.code == RECONCILIATION_REQUIRED
- Error message contains epoch context
- No FENCE_REJECTED error on retry (regression check)

## Integration checklist
- [ ] Add _check_resume_epoch_advanced helper method  
- [ ] Add early epoch-advance check in resume() before prior_fence_request
- [ ] Verify syntax: python -m py_compile tools/vst/pilot.py
- [ ] Run synthetic test cases (functional-test-reviewer responsibility)
- [ ] Check for regressions in S3-A tests
- [ ] Code review for error message clarity and corner cases
- [ ] Merge to s3-worker-pilot when tests pass
