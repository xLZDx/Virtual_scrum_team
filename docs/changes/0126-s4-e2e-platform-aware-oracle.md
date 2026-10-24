# 0126 S4 E2E platform-aware snapshot oracle

## What changed

- Updated `tests/qa/test_s4_qa_e2e.py` so the snapshot CLI refusal journey asserts the Windows wrong-distro guard on Windows and the earlier POSIX-only host guard on POSIX.
- Preserved an exact assertion for both intended fail-closed guards; no assertion was removed or weakened.

## Why

Native WSL evidence 0122 showed that `transfer_snapshot()` correctly rejects non-Windows execution before checking the requested distro. The prior test asserted only the later Windows wrong-distro result, so it failed on POSIX with a deterministic test-oracle defect.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: existing order is POSIX host precondition followed by Windows distribution allowlist validation.
- `tests/qa/test_s4_qa_e2e.py`: now checks the platform-appropriate exact refusal reason.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory includes this record.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- Platform-specific expected results retain both safety checks. Windows verifies the named-distro allowlist; POSIX verifies that source transfer cannot run from a non-Windows host.
- The old `e43329f` WSL snapshot is immutable/read-only and cannot contain this correction. Any future native rerun requires a new clean snapshot.

## Verification state

- Prior native evidence: snapshot run `a198f0afd1c64dc2b960a08f757eff9c`, candidate `e43329f`; six E2E IDs passed and this test failed because of the platform-order mismatch. See 0122.
- This test correction is intentionally committed before its focused local test run. The post-commit command/result will be recorded separately; do not treat this change record alone as a passing test claim.
- No WSL, signer, report, gate, package installation, or product-source change is included.

## Follow-up

1. After this commit, run `python -m pytest -q tests/qa/test_s4_qa_e2e.py` on the clean committed Windows checkout.
2. Record exact revision, command, environment, count, and warnings in a linked verification record.
3. Create a new clean S4 source snapshot before any corrected native E2E rerun.
