# 0050 S2 Windows external-anchor coordinator hardening

## What changed

- `tools/vst/lifecycle.py`: public `FileExternalAnchor.compare_and_append()` now acquires the same cross-process sidecar coordinator lock used by Store operations. Its JSONL CAS reread and append stay within that lock, and the separate `msvcrt` byte lock on the JSONL file was removed. Nested Store calls use the existing per-thread/path reentrancy. Windows skips POSIX-style `chmod(0o600)` calls on both anchor and coordinator files. Sidecar open and Windows lock acquisition failures are reported as `AnchorError`.
- `tools/vst/store.py`: `Store.__init__` closes its SQLite connection and raises a typed integrity `StoreError` if coordinator acquisition prevents schema initialization or startup reconciliation.
- S2 anchoring contract, decision/lesson logs and document registry were updated.

## Why

The designated E2E agent reran the focused suite at code HEAD `8df8db70649f3f45e75f34c9f717b060d292497b`: 75 passed, 2 failed, 21 skipped. Both failures reported persisted `external anchor unavailable: [Errno 13] Permission denied`, during first genesis checkpoint creation and concurrent writers. The previous JSONL byte-lock change did not fix the Windows access failure. Using one sidecar lock for every public CAS is consistent with the established Store serialization boundary and removes the second Windows file-lock/open interaction. Separate review also found that an `msvcrt` lock acquisition `OSError` could escape construction while the SQLite connection remained open.

## Verification state

No tests, checks, builds, CI, migrations or runtime probes were run for this change. E2E must rerun genesis anchoring, standalone CAS, and concurrent anchored Store scenarios on the resulting exact head. The prior E2E run is recorded evidence for the pre-fix head only; it is not proof of this change.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: rerun the focused Windows anchor scenarios and report exact commands, head and results.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
