# S4 E2E platform-aware oracle verification

## Scope and provenance

- Exact HEAD: `630c5cf13e7f5cec7248e4bcd8820953c5ea9d00`.
- The working tree was clean before execution.
- The committed test correction is in change 0126 and makes the snapshot refusal assertion platform-aware: exact POSIX host guard on POSIX, exact wrong-distro guard on Windows.
- This is a local Windows run. It does not update or rerun the immutable `e43329f` WSL snapshot used by native evidence 0122.

## Command and result

Commands:

```text
git rev-parse HEAD
git status --short --branch
python --version
python -m pytest --version
python -m pytest -q tests/qa/test_s4_qa_e2e.py
```

Environment: Windows PowerShell, Python 3.14.3, pytest 8.4.2.

Result: **2 passed, 0 failed** in 5.98 seconds. Pytest emitted one existing `pytest-asyncio` `DeprecationWarning` for `asyncio.get_event_loop_policy`, with Python 3.16 listed as the removal version.

This corrects the test-oracle defect locally; it does not prove the corrected test on Ubuntu. A new clean snapshot is required before another native E2E run. Native report/signing/gate remain outside this evidence.
