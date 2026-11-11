# U5-2 GPT-PM code review scope

Task: U5-2, apply AEVE patch proposals through the diff gate. Base: U5-1 approved head, head = current HEAD. Review the delta only: tools/vst/patch_proposals.py, docs/sdlc/u5/PATCH_PROPOSALS.md, tests/vst/test_u5_patch_proposals.py (tests are NOT_RUN; judge by reading), tools/qa/build_registry.py (two map lines), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: `apply_proposals` (strict `g6.patch.v1` validation, base check, apply in a throw-away index, candidate commit object, `worker_gate.gate_worker_change` on the real diff, then the only worktree write with rollback), `change_origin_share` and `hunk_counts_from_diff` (share of proposal versus model lines per run), `check_model_changes` (model may not override a proposed patch; explicit recorded override reason). `tools/vst/diffgate.py`, `worker_gate.py` and AEVE are unchanged.

Facts from AEVE origin/main (read-only): the proposal document has no base identity and no bounds field, only `report_sha256` and per-file unified diffs without `a/` `b/` or `diff --git` lines (`src/aeve/repair/patch.py:22-37,143-172,225-248`). No CLI command or executor emits it; `aeve review` runs only diagnosis and dead-code (`src/aeve/review.py:1638-1657`).

Interpretation decisions:
- Input is the JSON document, validated strictly; the adapter in `tools/uc/adapter.py` is not extended because AEVE has no command to call.
- Base identity is enforced on the VST side: caller-reported `proposal_base_head` equals the pinned base, worktree HEAD equals the pinned base, and every patch must apply to the base content with `git apply`. A mismatch is REFUSED `STALE_BASE`.
- Nothing is written to the worktree before the gate accepts: patches go to a throw-away index, a dangling candidate commit object carries the result, and only `git restore --source=<candidate> --worktree` writes, followed by a content check and a rollback from the base head.
- Scope, protected paths and path hazards are decided only by `worker_gate` (once on the claimed diff with a placeholder candidate id before any git call, once on the real diff).
- "Files with only a flagged, no-diff proposal" are free for the model; "patched" means at least one `changed: true` proposal.
- Share is counted per hunk on the real git diff; a file touched by both origins is split by hunk.
- Override of a proposal by the model needs a recorded reason of 10 to 500 characters; it never bypasses `worker_gate`.

Limits: git commands unproven (nothing was run); no file hashes from AEVE so a base differing outside the hunk context is not detected; CRLF and no-final-newline sources fail as `STALE_BASE`; no per-worktree lock; HEAD is not moved; no OS sandbox. Nothing wires the module to a pipeline in this task (U5-3).

Tests: written, NOT_RUN (running tests is forbidden by the operator). Evidence is static reading only.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Review remediation

Three reviewers (python, security, tests) reported on 49bbe61; one batch was applied (static only, tests NOT_RUN). Operator decision: a stale base is guarded on the VST side because AEVE proposals carry no base identity; AEVE is unchanged.
- Recipe label unenforced (security MAJOR): each diff is checked against its recipe before any git call (`RECIPE_MISMATCH`); chaining order enforced; `report_sha256` documented as integrity, not authenticity.
- Repository-local git config trusted (security MAJOR): command-line overrides for attributes, hooks, autocrlf, safecrlf, quotepath; direct scan of config, `config.worktree`, `info/attributes` and `.gitattributes` (`UNTRUSTED_GIT_CONFIG`); git-dir and common-dir derived from `.git` and cross-checked; the worktree is now written by Python (temp file plus `os.replace`) and compared byte for byte with `git cat-file` blobs, so the git checkout-style write and its filters are gone.
- No lock, TOCTOU, rollback by overwrite (security MAJOR): exclusive lock file in the git-dir, journal, re-check of bytes and gate right before the write, compare-and-restore rollback (`ROLLBACK_CONFLICT`), rollback also on `KeyboardInterrupt`; assume-unchanged and skip-worktree paths refused.
- Override too weak (security): `authorized_by` required and recorded, Cc/Cf/Zl/Zp rejected, cap of 16, patched paths bound to the `ApplyResult`.
- Dangling objects (security): scratch object directory with alternates; consequence: `candidate_head` is an identifier only.
- git lookup (security): `find_git` uses absolute PATH entries outside the worktree.
- CRLF, BOM and separators gave a false `STALE_BASE` (python MAJOR): `PATCH_NOT_REPRESENTABLE`; exit-1 mapping split into `STALE_BASE` and `PATCH_DOES_NOT_APPLY`; `GIT_UNSAFE_DIRECTORY`.
- False isolation wording (python MAJOR): the proof is marked `pre_materialize` with the placeholder note, plus `post_materialize_verified`.
- Run record (python): `build_run_record`; `ApplyResult` exposes `partial` and `patched_paths`.
- Tests: the `doc=None` blocker fixed with a sentinel; gate-stage, rollback, lock, config, recipe, exit-code, override, record tests added; real-git tests (skipped without git) added. All NOT_RUN.

Still open: git commands unproven; a base differing only outside the hunk context is not detected; the lock is advisory.

## GPT-PM verification round

GPT-PM returned one MAJOR: `build_run_record` counted `hunks_by_file` as applied proposal lines although `apply_proposals` had returned BLOCKED after the gate accepted the diff (`DIRTY_WORKTREE`, `JOURNAL_UNAVAILABLE`, `MATERIALIZE_FAILED`, `ROLLED_BACK`, `ROLLBACK_CONFLICT`). Fixed (static only, tests NOT_RUN):
- `ApplyResult.hunks_by_file` is now set only for ACCEPTED after the verified write; the pre-write counts are `attempted_hunks_by_file` (also in `to_dict`).
- `build_run_record` counts proposal lines only when the verdict is ACCEPTED and `post_materialize_verified` is true, even if a caller builds an inconsistent result; it adds `applied`, `attempted_proposal_hunks` and `attempted_proposal_lines`, which never enter the fractions.
- Regression tests with hand-computed numbers (attempted 2 lines, applied 0, model 3, total 3, fractions 0.0 and 1.0): blocked before the write, failed write with rollback, rollback conflict (state UNKNOWN), journal denied, a forged inconsistent result; the accepted case stays 2 proposal and 4 model lines of 6.
