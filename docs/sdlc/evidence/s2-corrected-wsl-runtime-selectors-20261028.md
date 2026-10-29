# S2 corrected WSL runtime selectors — 2026-10-28

## Scope and source identity

- Active sprint: S2 only.
- Repository documentation HEAD before this evidence update: `067045d` (`d500179` source/test tree
  plus documentation-only commits).
- Exact source/test revision executed: `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- WSL: Ubuntu 24.04; Python 3.12.3; pytest 7.4.4; test process ran as root in the prepared test
  environment.
- Three test-file SHA-256 values matched Git at the source/test revision:
  - `tests/vst/test_s2_store_lifecycle.py` — `243ae4105e7e752ce0028c9a5a9edf9ec844fd1de1a69a09151a6c6d8ffcf52e`
  - `tests/vst/test_s2_runner_lifecycle.py` — `f4abf50c7558fd7fde805a95ee33e1e9be7e7a185e00ee5f74b621cd601a1d9d`
  - `tests/vst/test_s2_sandbox_probe.py` — `66440069c6a267f8fcbae2ba9fad0c2552d74fd801fffcbebd0e0c4a9c1fbd8c`

Only the eight corrected selectors below were run. They use temporary database, anchor, key,
socket, worktree and SQLite fixtures. Existing test identities were used; no identity, credential,
capability, service, root configuration, E5 signature, or production setting was provisioned or
changed.

## Corrected focused selection

The exact selector set was:

```text
tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork
tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline
tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes
tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation
tests/vst/test_s2_store_lifecycle.py::test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append
tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed
tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file
tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Initial corrected batch command (the root shown was a unique disposable archive root):

```text
python3 -m pytest -q -rs -p no:cacheprovider --rootdir=/tmp/vst-s2-corrected-1793208079803-420467 --basetemp=/tmp/vst-s2-corrected-1793208079803-420467/pytest-basetemp tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork tests/vst/test_s2_store_lifecycle.py::test_anchor_append_separates_valid_tail_without_final_newline tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation tests/vst/test_s2_store_lifecycle.py::test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: **11 passed, 1 failed**, exit 1, 2.90 seconds. The sole failure was harness setup: the
temporary archive root was mode `0700`, so the reviewer child could not import `tools` and raised
`ModuleNotFoundError`. It was not a product assertion failure. No source/test file changed.

Targeted rerun after changing only that disposable archive root to mode `0755`:

```text
python3 -m pytest -q -rs -p no:cacheprovider --rootdir=/tmp/vst-s2-corrected-rerun-1793208128604-457450 --basetemp=/tmp/vst-s2-corrected-rerun-1793208128604-457450/pytest-basetemp tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture
```

Result: **1 passed**, exit 0, 0.37 seconds. `functional-test-reviewer` independently confirmed the
same 12 unique cases are covered: 10 E3 cases and two synthetic identity cases. Acceptance result
for these eight selectors is therefore **12 passed, 0 failed** after the scoped harness correction;
the initial setup failure remains recorded above.

Both temporary roots were confirmed absent after execution. A first archive launch failed before
pytest because PowerShell expanded an inline bash variable, leaving an empty extraction path
(`tar` exit 2). A second malformed-selector launch was interrupted; pytest output and result are
unknown. Neither is counted as test evidence. The runner confirmed no orphan pytest/archive process
or leftover temporary root remained.

## Limits and acceptance

The results provide corrected focused evidence for VST-012/E3, the synthetic POSIX worker key/socket
boundary under VST-011/E2, and the synthetic POSIX reviewer write boundary under VST-015/E6. They
do not prove access control for a real signing key, persistent service behavior, the capability
drop/timeout selectors, complete Windows/POSIX containment, current-run E5, production coordinator
integration, E8, or overall S2 acceptance. `S2-DISPATCH-M01` remains MAJOR/OPEN; S2 remains NOT
APPROVED; S3 remains blocked.

Execution owner: designated `e2e-runner`. Coverage adjudication: `functional-test-reviewer`.
Coordination and durable evidence: Codex.
