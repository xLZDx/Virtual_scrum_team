# U5-1: worker output through the diff gate

Module: `tools/vst/worker_gate.py`. Tests: `tests/vst/test_u5_worker_gate.py` (written, **NOT_RUN**: pytest is forbidden by the operator for this sprint, so no result is claimed).

Isolation model: Windows-local without WSL (operator decision 2026-11-08). The WSL path (`worker_exec.c`, the WSL bundle files) is not used and not extended.

## Public API

- `gate_worker_response(response, *, manifest_sha256, base_head, allowed_paths, protected_paths, diff_bytes, isolation, symlink_paths=(), rename_pairs=()) -> WorkerGateVerdict` takes a `WorkerResponse` from `tools/vst/worker_adapter.py`. Anything that is not a `WorkerResponse`, a state other than SUCCEEDED, or a manifest digest that differs is BLOCKED.
- `gate_worker_change(*, manifest_sha256, base_head, candidate_head, changed_paths, allowed_paths, protected_paths, diff_bytes, isolation, ...) -> WorkerGateVerdict` is the core on raw fields. It never raises.
- `IsolationContext(worktree_root, main_checkout_root, network_requested, pinned_base_head, worktree_head=None, lstat, realpath)`: the caller states the isolation setup; the proof checks what it can.
- `build_isolation_proof(...)`, `proof_is_honest(proof)`, `path_hazards(path)`, `parse_diff_paths(diff_bytes)`.
- Constants: `DEFAULT_PROTECTED_COMPONENTS`, `DEFAULT_PROTECTED_BASENAMES`, `DEFAULT_PROTECTED_PREFIXES`, `REQUIRED_PROPERTIES`, `CALLER_ONLY_PROPERTIES`, `NOT_VERIFIED_PROPERTIES`, `MAX_DIFF_BYTES`, `MAX_HEADER_LINE`, `MAX_CHANGED_PATHS`.

The worker adapter reports `changed_paths` and `candidate_head` but no diff text, so the caller supplies `diff_bytes` (the collected `git diff` base..candidate).

## Verdicts

| Verdict | Meaning |
|---|---|
| ACCEPTED | diffgate PASS, no hazard, no protected path, all paths in scope, diff text is valid git grammar and agrees with declared paths, every required isolation property VERIFIED or (where only a caller value exists) CALLER_ASSERTED |
| REFUSED | a definite violation: out of scope, protected path, path trick, link/submodule/non-standard mode, diff/paths mismatch, an isolation property FAILED, diffgate FAIL |
| BLOCKED | no decision possible: malformed or missing input, worker not SUCCEEDED, diffgate missing or broken, unparsable or oversized diff, required isolation property NOT_VERIFIED, any unexpected exception |

If both a refusal and a block reason exist the verdict is REFUSED (the more informative one) and both are listed; neither accepts. Reasons are `(code, detail)` pairs. Reason details echo paths as `ascii(path)` cut to 200 characters.

## What is reused from the diff gate

`diffgate.check_diff` decides the final PASS/FAIL and produces the evidence; `diffgate.is_blocked_path` is applied to every hazard-free touched path; `diffgate.normalize_path` runs inside `check_diff`. The gate is not changed. Hazardous `allowed_paths` entries are never passed to it and never match a change. `worker_adapter.is_canonical_repo_path` is not used: it rejects any `.git` component, which would turn a protected path into a malformed one; `.git` is handled as a protected path instead.

## What the diff gate cannot express (added here, fail closed)

1. A protected path that is also listed as allowed: `check_diff` passes it. Here it is REFUSED (`PROTECTED_PATH`), at any depth for the default names.
2. Case-insensitive scope: `check_diff` compares exactly. Here a case variant of an allowed path is REFUSED with its own code.
3. Windows aliases: 8.3 names (`~N`), trailing dots or spaces, reserved device names (CON, NUL, COM1..9 incl. superscripts, with extensions), NTFS streams (`:`), UNC (`//`, double backslash), drive letters, backslashes, `..`, control characters, NFKC compatibility forms, over-long components. Each is REFUSED with `PATH_HAZARD_<kind>`, also when the path is listed as allowed. Protected-name matching strips stream suffixes and trailing dots/spaces, so `AGENTS.md.` and `.git./config` are also `PROTECTED_PATH`.
4. Under-reported paths: the whole diff must be valid git diff grammar and its paths must equal the declared `changed_paths` exactly.
5. Link modes (120000) feed `symlink_paths`, rename lines feed `rename_pairs`, gitlinks (160000) and file modes other than 100644/100755 are REFUSED.

## Protected paths

Defaults (constants in the module): any path component equal to `.git`, `.github`, `.gitlab`, `.hooks`, `.husky`, `.harness`, `.claude`; basename `AGENTS.md`, `CLAUDE.md`, `.gitattributes`, `.gitmodules` at any depth; root prefixes `tools/vst` and `.harness-tools`. All compared case-folded. The caller list adds root-prefix entries (a trailing `/` is allowed). Caller entries get a weak check (non-empty, no backslash, NUL, absolute or drive form, no `.`/`..`/empty component); a bad entry adds a `MALFORMED_INPUT` block reason but never hides a refusal.

## Diff grammar and caps

Accepted: blank lines, then `diff --git a/X b/Y` blocks with extended header lines (mode lines, `index`, `similarity`, `rename`/`copy`), optional `---`/`+++` whose paths must match the header, hunks whose line counts match the `@@` header, or `Binary files ... differ`. Every block must carry a complete change representation, checked at each block boundary and at end of input: at least one complete hunk, or a rename/copy pair, or a mode-only change (`old mode` plus `new mode`), or `new file mode` / `deleted file mode`, or a `Binary files ... differ` line. A header-only block (including one with only an `index` or `similarity` line) is BLOCKED. `GIT binary patch` payloads are unsupported and BLOCKED; a `Binary files ... differ` marker is accepted only as a path-touch, with no content check. Anything else is BLOCKED `DIFF_UNPARSABLE`: preamble text, a stray `---`/`+++` section, `diff --cc`/`--combined`, truncated or over-long hunks, quoted paths, non-UTF-8. Mode lines are read only in the header part of a block. Caps (BLOCKED): diff over 8 MiB, a header line over 4 KiB, more than 128 paths.

## Isolation proof

`build_isolation_proof` returns `{schema, isolation_mode, worktree_head_reported, candidate_head, properties:[{property, status, detail}]}`.

Statuses:

- `VERIFIED`: computed here from the file system or from the data itself.
- `CALLER_ASSERTED`: only a caller-reported value was compared; nothing was read from git or the OS. Allowed for ACCEPTED, always listed with its reason, never promoted to VERIFIED (`proof_is_honest` rejects it).
- `FAILED`: checked and violated; the verdict is REFUSED.
- `NOT_VERIFIED`: not checked, or the check could not complete; a required one makes the verdict BLOCKED.

Required properties for ACCEPTED:

- `worktree_separate_from_main_checkout` (VERIFIED): both roots exist (`lstat`), resolved paths are disjoint (different drives count as disjoint).
- `base_commit_pinned` (CALLER_ASSERTED): the worktree base the caller reports equals the manifest base head.
- `worktree_head_matches_candidate` (CALLER_ASSERTED): the worktree HEAD the caller reports (`IsolationContext.worktree_head`) equals the candidate head; absent or different is NOT_VERIFIED.
- `network_flag_not_requested` (CALLER_ASSERTED): only the request flag; enforcement is not verified.
- `paths_normalized` (VERIFIED): every changed path is free of the hazards above.
- `link_and_reparse_point_check_on_changed_paths` (VERIFIED): an `lstat` walk of every component; every added or modified path must exist (only deleted files and rename sources may be missing, otherwise NOT_VERIFIED); a symlink, a reparse point (junction) or a resolved path outside the worktree is FAILED; no reparse attributes on the platform is NOT_VERIFIED. The detail states how many components were really inspected.

Always NOT_VERIFIED, never promotable: `os_sandbox`, `process_containment`, `network_enforcement`, `worker_identity_separation`, `writes_outside_worktree`, `resource_limits`, `short_name_aliases_on_disk`, `check_time_vs_use_time`, `rename_and_symlink_evidence_completeness`.

## Limits

- This is a path and diff gate plus a point-in-time check, not a sandbox. A worker can still run code, use the network and write outside the worktree on Windows-local without WSL.
- The gate checks consistency of what it is given, not provenance: diff text and `IsolationContext` come from the caller. A consumer must apply exactly the `diff_bytes` it passed here; nothing binds them to a later copy. Signing of the diff evidence (`sign_diff_evidence`) is not done here.
- The link walk is a point-in-time check (time-of-check versus time-of-use).
- Nothing has been executed; all results are NOT_RUN.
