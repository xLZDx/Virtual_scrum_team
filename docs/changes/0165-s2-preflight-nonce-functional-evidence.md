# Change 0165: Record S2 preflight nonce functional evidence

## What changed

- Added exact-head functional evidence for the S2 `collect_inventory` nonce behavior.
- Updated the S2 backlog, decision log, and test change record with the run's scope and limits.

## Why

Change 0162 altered input validation and 0163 added cases. Acceptance requires evidence on the committed implementation and test heads, with run counts and environment captured.

## Verification

- Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_sandbox_probe.py -k "collect_inventory_generates_nonce_only_when_omitted or collect_inventory_preserves_explicit_nonce or collect_inventory_rejects_invalid_explicit_nonce_before_probing"`
- Result: 4 passed, 22 deselected, 0 failed; 1 pytest-asyncio deprecation warning; 1.20 seconds.
- Environment: Windows, CPython 3.14.3, pytest 8.4.2.
- Product source HEAD: `6ee97cb06b52900c3c2ab2a9b1b415ae117a7932`.
- Test/evidence basis HEAD: `deed6abe34eeaa8620593442bcdb1413d846f798`.
- Full command and limitations are preserved in `docs/sdlc/evidence/s2-preflight-nonce-functional-run.md`.

## Ownership and next step

- Accountable task owner: operator.
- Test author/executor: functional-test-reviewer.
- Next: continue non-test S2/S3/S4/S5 work and retain platform/prohibited acceptance as separate open criteria.
