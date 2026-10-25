# Change 0257: Keep ACL preflight selectors portable

## What changed

- Made the synthetic ACL xattr monkeypatch work on Python platforms where `os.getxattr` is not defined, while keeping the fail-closed helper under test.

## Why

The test must be able to inject deterministic ACL evidence across developer Python platforms; the production QA runner still refuses when the real ACL inspection API is unavailable.

## Decisions and ownership

- Only the test fixture's monkeypatch target is made optional; the production ACL inspector remains fail-closed.
- Test owner: `functional-test-reviewer`; accountable task owner: operator; coordinator: Codex.

## Affected contracts and paths

- `tests/qa/test_s4_worker_boundary_contracts.py`
- S4 functional category selectors mapped by change 0256.

## Verification state

- Interim command: `C:\Python314\python.exe -m pytest -q tests\qa\test_s4_worker_boundary_contracts.py -k qa_preflight`.
- Interim result: **5 passed, 7 deselected**, one unrelated pytest-asyncio deprecation warning, 6.59 seconds.
- Interim run was on repository HEAD `eb5187b` with this test-only portability adjustment dirty. Repeat on the clean committed test HEAD before treating as exact-head evidence.

Executor: Codex
