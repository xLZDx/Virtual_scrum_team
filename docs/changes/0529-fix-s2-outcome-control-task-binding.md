# Change 0529: match S2 outcome controls to Store control-note records

## Why

The first WSL execution of the focused suite found that the new dispatch-history validator expected
the control event's `task_id` to equal its `event_id`. The existing Store control-note contract
instead writes `task_id="__control__"` and binds the unique control identity in the payload's
`event_id` field. The incorrect check rejected every valid pending/acknowledgement history.

## What changed

- Changed the dispatch pending/acknowledgement history validator to require the established
  `__control__` task ID and independently verify the exact payload `event_id`.
- No other control-note contract or event identity was changed.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- `e2e-runner` executed the exact command
  `python -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py`
  at HEAD `1f02b39048bf8c3f0c90a1c8d443abca02824a7c` in the canonical checkout mounted at
  `/mnt/d/Repo/Virtual_scrum_team`, Ubuntu 24.04, Python 3.12.3, pytest 7.4.4. Result: **110 passed,
  8 failed**, exit code 1. Every failure followed the same incorrect task-ID expectation.
- The agent made no file changes and did not create a worktree or project copy. This source fix has
  not yet been rerun; the next exact-head run belongs to `e2e-runner`.
- The first Windows collection attempt at that same head did not reach test execution because
  Windows Python 3.14.3 lacks `socket.AF_UNIX`; it is recorded as an unavailable platform path, not a
  test failure.
- M03 remains OPEN until the focused suite passes, fresh specialist reviews complete, and GPT-PM
  adjudicates the exact final source/test head.
