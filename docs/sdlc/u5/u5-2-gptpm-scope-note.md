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
