# Change 0572: bind S2-1 recovery evidence to the task commit

## Why

The focused S2-1 WSL rerun executed the corrected test in the worktree before its source commit. The task sequence requires verifying the committed test blob and reconciling the backlog and evidence packet before the exact-head approval and push.

## What changed

- Read `tests/vst/test_s2_store_backed_pubsub.py` back from commit `dcb5d63c19eeb63f2f17fce0add510937688e819` and verified its Git blob and SHA-256 against the successful run record.
- Updated S2-1 backlog, test-plan and verify-evidence entries to distinguish committed source/test evidence from unproven installed runtime behavior.
- Preserved the initial failing run as historical evidence and linked the passing rerun and exact commit binding.
- Updated the generated document registry for the additional evidence record.

## Verification

- Committed test blob: `da70c3b9a01c697bec8011f2814c4217fdf6688b`.
- Read-back SHA-256: `435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7`, matching the successful 130-passed run evidence.
- Documentation diff passed `git diff --cached --check` before this documentation commit.
- No tests were run for this documentation-only reconciliation.

## Remaining task delivery

The S2-1 source/test task still requires exact-head GPT-PM approval and a normal push through the enforced pre-push hook. No S2-2 work is included.
