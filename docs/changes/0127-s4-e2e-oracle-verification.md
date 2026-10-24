# 0127 S4 E2E platform-aware oracle verification

## What changed

- Added `docs/sdlc/evidence/s4-e2e-oracle-630c5cf.md` with the exact focused local run after test correction 0126.
- Updated the S4 backlog and lesson to distinguish the old native-snapshot failure from the corrected local test and the new-snapshot dependency.

## Why

The E2E test correction was committed first as requested, then run on a clean committed HEAD. Its exact command, environment, count, duration, and warning need durable evidence before a new snapshot is authorized.

## Affected contracts and paths

- `tests/qa/test_s4_qa_e2e.py`: platform-aware snapshot refusal oracle.
- `docs/sdlc/evidence/s4-e2e-oracle-630c5cf.md`: local committed-head proof.
- `core/BACKLOG.md` and `core/LESSONS_LOG.md`: local fix status and native rerun dependency.
- `governance/DOCUMENT_REGISTRY.md`: generated document inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- The old WSL snapshot from `e43329f` remains immutable; this local run does not upgrade its native result.
- A new source transfer is required before testing the corrected code under the read-only WSL worker.

## Verification state

- Exact HEAD `630c5cf13e7f5cec7248e4bcd8820953c5ea9d00`; worktree clean before the run.
- Command: `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Environment: Windows PowerShell, Python 3.14.3, pytest 8.4.2.
- Result: 2 passed, 0 failed in 5.98 seconds; one `pytest-asyncio` deprecation warning for `asyncio.get_event_loop_policy` (removal listed for Python 3.16).
- Native WSL corrected-snapshot rerun remains pending; signer/report/gate remain `NOT_RUN`.

## Follow-up

1. Transfer the current clean committed HEAD with the existing private provisioning inputs.
2. If transfer returns metadata, run the exact mapped E2E selectors as read-only worker with bounded temp/cache settings, then verify that only that snapshot remains clean.
3. Keep signer socket, report, receipt, and gate as separate gates.
