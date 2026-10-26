# Fresh permitted S2 runtime evidence at repository HEAD `4fe150326a36faf401b045cfa1b9a2e64d89436b`

## Scope and source identity

This record covers four bounded S2 selectors: two Windows contract checks and two unprivileged WSL external-anchor checks. It is partial runtime evidence, not full S2 acceptance or process-containment proof.

- Exact canonical candidate HEAD: `4fe150326a36faf401b045cfa1b9a2e64d89436b`.
- Exact S2 code/test content identity: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- `git diff --name-only f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2 HEAD -- tests/vst tools/vst` returned no paths. `git diff --quiet HEAD -- tests/vst tools/vst` returned exit code 0. Thus the selected S2 source and tests are byte-identical to the documented `f0bbac8` content.
- No source or test files were changed for these runs. The canonical worktree had unrelated modifications before this task; they were not touched.
- The protected pre-existing `docs/sdlc/evidence/s2-functional-test-run.md` remained present with SHA-256 `1273679AC992268BB6FAAC4AC002EDCEDE5D884A7470325314D181E67F6B6B08`.

## Windows focused run

Environment: `C:\Python314\python.exe`, CPython 3.14.3, pytest 8.4.2.

Exact command:

```powershell
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key
```

Result: exit code 0; **2 passed, 1 warning** in 0.83 seconds. The warning was pytest-asyncio's `asyncio.get_event_loop_policy` deprecation warning. No selector skipped or failed.

| Selector | Result | Scope limit |
|---|---|---|
| `test_gate_refuses_caller_supplied_parser_implementation` | PASS | In-memory gate contract; no subprocess or host mutation. |
| `test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key` | PASS | Synthetic signed registry and keys; no production key access. |

## WSL POSIX external-anchor run

The source was streamed from `git archive --format=tar HEAD` into a temporary WSL snapshot at `/tmp/vst-s2-fresh-4fe1503-20261026`. The snapshot had no `.git` directory, was owned by UID/GID `997:988`, and was removed after execution. Runtime: Ubuntu-24.04 WSL, Python 3.12.3, pytest 7.4.4. Tests ran unprivileged through `setpriv` with supplementary groups cleared.

Exact pytest command, from the snapshot working directory:

```sh
setpriv --reuid=997 --regid=988 --clear-groups /usr/bin/python3 -m pytest -q -rs -p no:cacheprovider \
  tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork \
  tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes
```

Result: exit code 0; **2 passed, 0 skipped** in 0.22 seconds, no warnings.

The first setup attempt invoked `pytest --version` as UID 997 while its current directory was `/root`; it failed with `PermissionError: [Errno 13] Permission denied: '/root/pytest.ini'` before collecting any selector. The snapshot was recreated and the final command above ran after changing into the snapshot directory. This was an invocation/setup error, not a test failure.

| Selector | Result | Scope limit |
|---|---|---|
| `test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork` | PASS | Uses a temporary external-anchor file to check idempotent append and same-count fork rejection. |
| `test_external_anchor_detects_restored_older_database_and_locks_writes` | PASS | Copies and restores temporary SQLite fixtures against a temporary anchor; no process termination. |

## Exclusions and acceptance boundary

No process-kill or kill-table selector, child-death scenario, crash/resume case, mutation test, timeout termination, process-group cleanup, Job Object descendant cleanup, real sandbox inventory, egress probe, or E8 bake-off was run. Root-only WSL identity selectors and the broader S2 modules were also not run. These results do not close E4 process containment, E8 crash/resume, or full S2 acceptance.

The selected POSIX cases exercise disposable anchor and database fixtures only. The selected Windows cases exercise in-memory contract inputs only. Neither platform result establishes production signer isolation, a real sandbox boundary, or worker-process containment.
