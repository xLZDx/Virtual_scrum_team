# 0058 S2 final Windows E2E run and signer setup diagnostic

## What changed

- Added the final exact-head five-file S2 Windows test execution to `docs/sdlc/evidence/s2-e2e-acceptance-280e2d0.md`.
- Recorded all 22 explicit `NOT_RUN` skip IDs and reasons, Windows/Python/pytest versions, command, exit code, duration, and warning.
- Recorded the bounded real signer service setup retry and its exact permission failure class without persisting key contents or machine-local key paths.
- Regenerated `governance/DOCUMENT_REGISTRY.md` using `tools/build_document_registry.py`.

## Why

The previous E2E evidence commit preceded the final five-file Windows run. This record links the exact committed test revision to its result and keeps platform-gated or prohibited scenarios visibly `NOT_RUN`. The signer diagnostic documents why real runner signing could not proceed without changing key permissions or weakening the service boundary.

## Verification state

- Tested HEAD: `d70b6b7530eabc25097b9e43f0aeebf2dab2cc10`.
- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py`.
- Environment: Windows 11 build `10.0.26300-SP0`, Python 3.14.3, pytest 8.4.2.
- Result: exit 0; 144 passed, 22 skipped, 1 pytest-asyncio deprecation warning; 7.95 seconds.
- The signer service retry failed before socket creation: `PermissionError: [Errno 13] Permission denied` from `os.open` in `_key_is_private`; root-owned `0700` parent directories blocked signer traversal. No client request or signature was made. No operator key was accessed.
- No tests/source code changed in this documentation-only follow-up.

## Ownership and next action

- Accountable task owner: operator.
- Executor: E2E runner (`gpt-6-luna`).
- Technical owner for signer credential delivery is not established in the repository records.
- Recommended next action: provision a least-privilege credential delivery/path boundary for the dedicated runner-signer service, then assign a separately scoped real-socket integration run. Do not broaden key directory access or use the operator key.

## Related evidence

- [Final E2E acceptance evidence](../sdlc/evidence/s2-e2e-acceptance-280e2d0.md).
