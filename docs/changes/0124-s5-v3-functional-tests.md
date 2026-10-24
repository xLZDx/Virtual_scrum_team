# 0124 S5 v3 functional contract coverage

## What changed

- Added focused S5 tests for v1/v2 golden compatibility, strict v3 manifests and receipts, exact rule-status partitions, typed findings, analyzer trust/signature separation, gate binding and resolver behavior, and bounded deterministic source-tree hashing.
- Included explicit negative gate cases for stale heads, changed manifest/policy/digests, wrong epoch, replayed attempts, missing/raising resolvers, and artifact digest mismatch.
- Added a symlink-boundary test. It is skipped on this Windows host because creating symlinks requires an unavailable privilege; the exact WinError is recorded.

## Why

S5 makes VST accept an opt-in v3 analyzer receipt while preserving v1/v2 signed bytes. The focused suite is designed to falsify compatibility, coverage, signature-domain, provenance, gate, and source-digest guarantees without executing AEVE or modifying product code.

## Affected contracts and paths

- `tests/vst/test_s5_v3_evidence.py`: contract, gate, and source-tree API tests mapped to S5 acceptance criteria.
- `tools/vst/contracts.py`, `tools/vst/gate.py`, `tools/vst/signing.py`, and `tools/vst/source_tree.py`: exercised interfaces; no product source was edited by this test task.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- Golden v1/v2 fixtures pin manifest SHA-256, receipt SHA-256, and signature hex for an existing v1 manifest/receipt and an existing v2 manifest/TestRun receipt.
- Symlink denial is not claimed as verified on this host. The source-tree symlink test is `SKIPPED` with WinError `1314`, errno `22`.
- No AEVE source identity, executable, attestor provisioning, or sandbox capability is inferred.

## Preliminary verification state

- Source HEAD: `8961ea0cc5a1fc3baba75aaa25cedc7e5cb070d2`.
- The worktree had only the newly authored test file untracked before the test run; product code was at the clean committed HEAD above.
- Command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_evidence.py`.
- Result: **39 passed, 1 skipped, 0 failed** (40 total collected cases).
- Environment: Windows PowerShell, Python `3.14.3`, pytest `8.4.2`.
- Warning: one deprecation warning from the globally installed `pytest-asyncio` plugin. No asyncio tests are in this module.
- This is preliminary authoring evidence. The required final result must be rerun after the test file is committed.

## Follow-up

1. Commit this test file and change record, then rerun the focused module on the exact clean committed HEAD.
2. Record final per-test acceptance mapping and execution evidence in a separate S5 evidence/detail commit.
3. Keep actual AEVE execution, read-only adapter enforcement, sandbox limits, network denial, and Windows symlink behavior `NOT_RUN` or `UNSUPPORTED` as appropriate.
