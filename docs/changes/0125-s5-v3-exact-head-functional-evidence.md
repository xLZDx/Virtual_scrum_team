# 0125 S5 v3 exact-head functional evidence

## What changed

- Recorded the final clean-head result for the 39-case focused S5 v3 functional module.
- Mapped each test function to its S5 acceptance criteria and documented unsupported runtime boundaries.
- Recorded the Windows symlink skip as an unavailable host capability with its exact WinError/errno.

## Why

S5 acceptance depends on truthful evidence for version compatibility, analyzer trust, coverage, gate binding and source-tree hashing. The report distinguishes local VST contract evidence from the unavailable AEVE adapter/sandbox path.

## Affected contracts and paths

- `tests/vst/test_s5_v3_evidence.py`: 19 focused test functions, including parameterized cases.
- `docs/sdlc/evidence/s5-v3-functional-0dbb662.md`: exact candidate, command, runtime, test mapping, outcome, warning, skip and limitations.
- `core/DECISION_LOG.md`: dated exact-head evidence entry.
- `governance/DOCUMENT_REGISTRY.md`: regenerated for this evidence and detail record.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- The symlink test remains skipped on this Windows host because `os.symlink` raised WinError `1314`, errno `22`; no other S5 test was skipped.
- No real AEVE runtime, external repository, provider, or sandbox acceptance is claimed.

## Verification state

- Exact clean HEAD: `0dbb66293fbf9df946b1b1cb5cc9b841d7b9d1ed`.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_evidence.py`.
- Result: **39 passed, 1 skipped, 0 failed**; 40 collected, `1.51s`.
- Environment: Windows PowerShell, Python `3.14.3`, pytest `8.4.2`.
- One deprecation warning from global `pytest-asyncio`; this module has no async tests.
- Actual analyzer runtime, sandbox and Windows symlink behavior remain `NOT_RUN` / `UNSUPPORTED` as described in the evidence file.

## Follow-up

1. Keep AEVE execution, sandbox restrictions and capability coverage open until the in-scope analyzer identity and isolated adapter are established.
2. Re-run the symlink case on an environment with authorized symlink creation before claiming that path runtime-proven.
