# U5-1: worker output through the diff gate

Module: `tools/vst/worker_gate.py`. Tests: `tests/vst/test_u5_worker_gate.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint, so no result is claimed).

Isolation model: Windows-local without WSL (operator decision 2026-11-08). The WSL path (`worker_exec.c`, the WSL bundle files) is not used and not extended.

## Public API

- `gate_worker_response(response, *, manifest_sha256, base_head, allowed_paths, protected_paths, diff_bytes, isolation, symlink_paths=(), rename_pairs=()) -> WorkerGateVerdict` takes a `WorkerResponse` from `tools/vst/worker_adapter.py`. Anything that is not a `WorkerResponse`, a state other than SUCCEEDED, or a manifest digest that differs is BLOCKED.
- `gate_worker_change(*, manifest_sha256, base_head, candidate_head, changed_paths, allowed_paths, protected_paths, diff_bytes, isolation, ...) -> WorkerGateVerdict` is the core on raw fields. It never raises.
- `IsolationContext(worktree_root, main_checkout_root, network_requested, pinned_base_head, lstat, realpath)`: the caller states the isolation setup; the proof checks what it can.
- `build_isolation_proof(...)`, `proof_is_honest(proof)`, `path_hazards(path)`, `parse_diff_paths(diff_bytes)`.

The worker adapter reports `changed_paths` and `candidate_head` but no diff text, so the caller supplies `diff_bytes` (the collected `git diff` base..candidate).

## Verdicts

| Verdict | Meaning |
|---|---|
| ACCEPTED | diffgate PASS, no hazard, no protected path, all paths in scope, diff text agrees with declared paths, every required isolation property VERIFIED |
| REFUSED | a definite violation: out of scope, protected path, path trick, link/submodule change, diff/paths mismatch, an isolation property FAILED, diffgate FAIL |
| BLOCKED | no decision possible: malformed or missing input, worker not SUCCEEDED, diffgate missing or broken, unparsable diff, required isolation property NOT_VERIFIED, any unexpected exception |

If both a refusal and a block reason exist the verdict is REFUSED (the more informative one); neither accepts. Reasons are `(code, detail)` pairs.

## What is reused from the diff gate

`diffgate.check_diff` decides the final PASS/FAIL and produces the evidence; `diffgate.is_blocked_path` is applied to every touched path; `diffgate.normalize_path` runs inside `check_diff`. The gate is not changed. `worker_adapter.is_canonical_repo_path` is the last-resort canonical form check.

## What the diff gate cannot express (added here, fail closed)

1. A protected path that is also listed as allowed: `check_diff` passes it. Here it is REFUSED.
2. Case-insensitive scope: `check_diff` compares exactly. Here a case variant of an allowed path is REFUSED with its own code.
3. Windows aliases: 8.3 names (`~N`), trailing dots or spaces, reserved device names (CON, NUL, COM1..9 incl. superscripts, with extensions), NTFS streams (`:`), UNC (`//`, double backslash), drive letters, backslashes, `..`, control characters, NFKC compatibility forms, over-long components. Each is REFUSED with `PATH_HAZARD_<kind>`.
4. Under-reported paths: the diff text headers are parsed and must give exactly the declared `changed_paths`; link modes (120000) feed `symlink_paths`, rename lines feed `rename_pairs`, gitlinks (160000) are REFUSED. Quoted or ambiguous headers are BLOCKED.
5. Default protected list (`DEFAULT_PROTECTED_PATHS`) plus the caller list, matched by case-folded path prefix.

## Isolation proof

`build_isolation_proof` returns `{schema, isolation_mode, properties:[{property, status, detail}]}`. Status is VERIFIED, FAILED or NOT_VERIFIED.

Checked (all five must be VERIFIED for ACCEPTED; FAILED means REFUSED, NOT_VERIFIED means BLOCKED):

- `worktree_separate_from_main_checkout`: resolved roots are disjoint (not equal, not nested).
- `base_commit_pinned`: the base commit the caller says the worktree was created at equals the manifest base head. It is caller-reported; git is not read here.
- `network_flag_not_requested`: only the request flag is checked.
- `paths_normalized`: every changed path passes `path_hazards`.
- `link_and_reparse_point_check_on_changed_paths`: an `lstat` walk of each existing path prefix under the worktree; symlink or `FILE_ATTRIBUTE_REPARSE_POINT` (junction) is FAILED; a platform without reparse attributes, or an unreadable root, is NOT_VERIFIED.

Always NOT_VERIFIED, never promotable: `os_sandbox`, `process_containment`, `network_enforcement`, `worker_identity_separation`, `writes_outside_worktree`, `resource_limits`, `short_name_aliases_on_disk`, `check_time_vs_use_time`, `rename_and_symlink_evidence_completeness`. `proof_is_honest` returns False if any of them is not NOT_VERIFIED.

## Limits

- This is a path and diff gate plus a point-in-time check, not a sandbox. A worker can still run code, use the network and write outside the worktree on Windows-local without WSL.
- The link walk is a point-in-time check (time-of-check versus time-of-use).
- Diff text and `IsolationContext` come from the caller; the module checks consistency, not provenance. Signing of the diff evidence (`sign_diff_evidence`) is not done here.
- Nothing has been executed; all results are NOT_RUN.
