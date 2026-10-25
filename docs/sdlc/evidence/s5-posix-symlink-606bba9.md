# S5 POSIX symlink selector evidence

## Acceptance mapping

- S5 AC-6, bounded source-path behavior: `test_source_tree_digest_rejects_symlink_scope` verifies that a source-tree digest request rejects a symlinked path.
- This is a unit-level source-digest contract test. It does not test an AEVE adapter, immutable runtime snapshot, timeout/output bound, subprocess denial, network denial, analyzer trust, or sandbox deployment.

## Exact source and environment

- Branch: `s5-bounded-aeve-evidence`.
- Exact HEAD: `606bba9a5c3563b195eee7b5dd11f0dd243c44a5`.
- Test file: `tests/vst/test_s5_v3_evidence.py`.
- Windows and staged WSL SHA-256: `97367e96750cb7025ffd56d6b9367086f7145e74ad5132938472e7e05588654c`.
- Environment: Ubuntu-24.04 WSL2, Python 3.12.3, pytest 7.4.4.
- Tracked source was staged from `git archive --format=tar HEAD` into a unique temporary WSL directory. The test-file hash matched on both sides. No archive-level hash was recorded. The temporary staging directory was removed.

## Execution

- Command: `wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /tmp/vst-s5-symlink-606bba9 && python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_evidence.py::test_source_tree_digest_rejects_symlink_scope"`.
- Result: **1 passed, 0 failed, 0 skipped** in 0.27 seconds.
- No source or test files changed.
- An incidental `wsl.exe -l -q` environment-list command was invoked before execution; it was not followed by further distribution enumeration or configuration changes. The test itself used the explicitly pinned `Ubuntu-24.04` distribution.

## Remaining acceptance and ownership

This closes only the focused symlink rejection selector. The actual AEVE adapter and runtime isolation are still `NOT_RUN`; technical analyzer owner is `UNKNOWN` in the repository. Operator is accountable for the delegated S5 task; Codex coordinates execution. Next: obtain an authorized AEVE identity/source and adapter interface, then run remaining bounded-runtime scenarios through the designated test agents.
