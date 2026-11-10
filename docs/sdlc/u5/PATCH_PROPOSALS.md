# U5-2: apply AEVE patch proposals through the diff gate

Module: `tools/vst/patch_proposals.py`. Tests: `tests/vst/test_u5_patch_proposals.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint, so no result is claimed; no code was executed while writing this).

Decision OD-8 (operator, 2026-11-08): AEVE's repair lab proposes bounded patches and never applies one; VST applies them in the isolated worktree and the diff gate checks them; the model writes code only for what AEVE proposed no patch for. Depends on U5-1 (`tools/vst/worker_gate.py`) and U1-5 (`tools/uc/adapter.py`).

## What AEVE really provides (AEVE origin/main, read-only via git)

- `src/aeve/repair/patch.py:22` `SCHEMA_VERSION = "g6.patch.v1"`; `:225` `propose_patches_report(snapshot)` builds the document.
- Document keys: `schema_version`, `proposals`, `proposal_count`, `llm_calls` (always 0), `executed_project_code` (always false), `note`, optional `status: "PARTIAL"` and `uncovered`, and `report_sha256` (sha256 of the canonical JSON without that key: `json.dumps(..., ensure_ascii=True, sort_keys=True, separators=(",", ":"))`, `patch.py:245-248`).
- One proposal (`patch.py:25-37`): `{file, recipe, detail, diff, changed}`. Recipes: `trailing-whitespace` and `final-newline` carry a diff and `changed: true`; `unused-import`, `unsupported-language`, `encoding-skip`, `parse-error` are notes with `changed: false` and an empty diff. Several proposals for one file are chained: the second diff is computed on the output of the first (`patch.py:196-208`).
- The diff is a per-file unified diff made by `difflib` (`patch.py:143-172`): headers `--- <file>` and `+++ <file>` without `a/`, `b/` and without a `diff --git` line, three context lines, no trailing newline, secrets redacted to `[REDACTED]`.
- **No base identity**: the document has no head, no file hash and no snapshot hash. **No bounds field**: the only bounds are the hunks themselves. The repair package (`src/aeve/repair/__init__.py`) states it never applies patches.
- **No CLI**: `aeve review` runs only the `g6.python-diagnose` and `g6.python-deadcode` executors (`src/aeve/review.py:1638-1657`); no command or executor emits `g6.patch.v1`. The adapter `tools/uc/adapter.py` (`run_review`) therefore cannot obtain proposals and was not extended. This module takes the JSON document as input (bytes or parsed object) and validates it against the schema above. When AEVE gains a command, only the producer of that document changes.

## Public API

- `apply_proposals(*, document, manifest_sha256, base_head, proposal_base_head, allowed_paths, protected_paths, isolation, git_runner=default_git_runner, timeout=30.0) -> ApplyResult`. Never raises.
- `ApplyResult`: `verdict`, `reasons`, `stage`, `worktree_state` (`UNCHANGED`, `MODIFIED`, `UNKNOWN`), `candidate_head`, `changed_paths`, `diff_bytes`, `diff_sha256`, `report_sha256`, `hunks_by_file`, `no_patch_paths`, `gate` (the `WorkerGateVerdict`), `to_dict()`.
- `validate_proposal_document(doc) -> ProposalSet`, `parse_proposal_json(raw)`, `git_patch_bytes(proposal)`; errors are `ProposalError(code, detail)`.
- `change_origin_share(proposal_lines_by_file, model_lines_by_file) -> dict`, `hunk_counts_from_diff(diff_bytes) -> {path: [(added, deleted), ...]}`.
- `check_model_changes(*, proposal_patched_paths, model_changed_paths, override_reasons=None) -> ModelChangeVerdict`.
- `GitResult`, `default_git_runner`, `build_git_env` (the git seam; tests inject a fake runner).

## Verdicts

| Verdict | Meaning |
|---|---|
| ACCEPTED | document valid, base matches, patches applied, the real resulting diff passed `gate_worker_change`, the worktree holds exactly the candidate |
| REFUSED | `STALE_BASE` (see below), out-of-scope or protected path or any other gate refusal, `DIFF_PATH_MISMATCH`, model change on a patched path (`MODEL_OVERRIDES_PROPOSAL`, `OVERRIDE_REASON_INVALID`) |
| BLOCKED | malformed, oversized or hash-mismatching document, no patch in the document, git failure or timeout, dirty worktree, wrong worktree root, no effect, write failure (rolled back), any exception |

## Flow and where the worktree is touched

1. `VALIDATE`: strict schema check. Unknown keys, wrong schema version, `llm_calls != 0`, `executed_project_code != false`, count mismatch, hash mismatch, non-canonical or glob paths (`worker_gate.path_hazards`), unknown recipe, a note with a diff, a patch recipe without one, headers not naming the file, hunk line counts not matching the `@@` header, a `[REDACTED]` marker (the diff cannot match the real file), NUL, duplicate patch recipe per file, duplicate JSON keys, NaN: all BLOCKED. Caps: document 4 MiB, 256 proposals, 512 KiB per diff, 4 MiB of diffs, 128 patched files.
2. `BASE_HEAD`: `proposal_base_head` (the head AEVE analysed, caller-reported, for example the `head` of the AEVE review response of the same run) must equal `base_head`, else REFUSED `STALE_BASE`.
3. `PRESCREEN`: the claimed diff (canonical `diff --git` form of the proposals) goes through `worker_gate.gate_worker_change` with a derived placeholder candidate id. A REFUSED or BLOCKED answer ends the run before any git call. Scope, protected paths and path hazards are therefore decided by the U5-1 gate, not re-implemented.
4. `WORKTREE_CHECK`: `git rev-parse --show-toplevel` must equal the isolation worktree root, `HEAD` must equal `base_head` (else REFUSED `STALE_BASE`), and the paths to patch must have no uncommitted change (else BLOCKED `DIRTY_WORKTREE`).
5. `BUILD`: a throw-away index (`GIT_INDEX_FILE` in a private temp directory outside the worktree) is filled with `git read-tree <base>`, then each patch is applied in document order with `git apply --check --cached` followed by `git apply --cached` (`--include=<file>` restricts each run to its own file). A patch that does not apply is REFUSED `STALE_BASE` (the context and removed lines differ from the real base content; this is the content-level base check); a patch git calls corrupt is BLOCKED. `git write-tree` and `git commit-tree -p <base>` (fixed identity and dates, no signing) create the candidate commit object; `git diff <base> <candidate>` (no renames, no external diff or textconv) yields the diff bytes and the changed paths. HEAD, the branch, the real index and the working files are untouched.
6. `GATE`: `gate_worker_change` runs on the real diff and the candidate id. Anything but ACCEPTED ends the run; the worktree was never written.
7. `MATERIALIZE`: the only write: `git restore --source=<candidate> --worktree` for the changed paths (index and HEAD unchanged), then `git diff --quiet <candidate> -- <paths>` must show no difference. Any failure restores the paths from `<base>`; a failed restore reports `worktree_state = UNKNOWN` and the caller must discard the worktree.

Every git call: `shell=False`, absolute git executable, `cwd` = worktree, explicit timeout (default 30 s), a fixed minimal environment (`build_git_env`: no inherited variables except `SystemRoot`, `GIT_CONFIG_NOSYSTEM`, null global config, no prompts, `HOME` and `TEMP` in the private scratch directory), literal pathspecs, fsmonitor off. Output is capped at 16 MiB. The scratch directory is removed in every case.

Rollback and failure cases: a failure before `MATERIALIZE` leaves the worktree byte-identical because nothing was written. A crash during `MATERIALIZE` leaves some paths modified; the next call sees them dirty and is BLOCKED `DIRTY_WORKTREE`, so a retry never stacks changes. Two concurrent calls on one worktree are not serialised here; the caller must hold a per-worktree lock. A retry after ACCEPTED is BLOCKED `DIRTY_WORKTREE`.

After ACCEPTED the caller decides how to record the change. `git reset --mixed <candidate_head>` in the worktree moves HEAD to the candidate and leaves the working files as they are; this module does not move HEAD. The `worktree_head_matches_candidate` isolation property is set by this module to the candidate id because the verified working-file content equals that commit's content; it stays `CALLER_ASSERTED`, never `VERIFIED`.

## What is reused from worker_gate

`gate_worker_change` (twice: claimed diff and real diff), `IsolationContext`, `path_hazards`, `parse_diff_paths` (grammar of the real diff, also inside `hunk_counts_from_diff`), `MAX_CHANGED_PATHS`, the verdict constants. `tools/vst/diffgate.py` and `worker_gate.py` are not changed. Not reused because private or absent: the protected-path matcher (it is reached only through `gate_worker_change`), and a way to gate a diff before a candidate commit exists (hence the placeholder candidate in `PRESCREEN`).

## Share of change by origin

`change_origin_share(proposal_lines_by_file, model_lines_by_file)`: each argument maps a path to a list of hunks, each hunk an `(added, deleted)` pair. Result: `proposal` and `model` blocks with `added`, `deleted`, `lines` (= added + deleted), `hunks`, `files`; `total_lines`; `proposal_fraction` and `model_fraction` (lines over total, `None` for an empty change); `files_touched_by_both`, `proposal_only_paths`, `model_only_paths` (model paths with no proposal). Rule: attribution is by hunk; each hunk belongs to one origin, so a file touched by both contributes its proposal hunks to the proposal and its model hunks to the model; hunks must be disjoint. Paths match case-insensitively. Invalid input raises `ValueError`. Proposal hunks come from `ApplyResult.hunks_by_file` (counted on the real git diff, not on AEVE's claim); model hunks from `hunk_counts_from_diff` of the model diff. Recording the result in the run record is the job of the pipeline store (U5-3).

## The model may not override a proposal

`check_model_changes` refuses a model change on any path with a patch in the document (`MODEL_OVERRIDES_PROPOSAL`). Paths that AEVE only flagged (`changed: false`) have no patch and are free for the model. An explicit override needs `override_reasons[path]` (10 to 500 characters, no control characters); it is returned in `overrides` as `{path, reason}` and as a `MODEL_OVERRIDE_RECORDED` reason, so it is recorded, never silent. An invalid reason keeps the refusal; an override for a path that is not in conflict is BLOCKED (`OVERRIDE_WITHOUT_CONFLICT`). An override only lifts this rule: the model change still goes through `worker_gate` for scope and protected paths.

## Limits (not verified or not covered)

- Nothing was run. The git commands (`apply --cached`, `commit-tree`, `restore --pathspec-from-file` which needs git 2.25 or newer, `GIT_CONFIG_GLOBAL` set to the null device on Windows) are written from the git documentation and unproven here.
- A stale base is detected by head comparison (caller-reported) and by `git apply` content matching. Because AEVE gives no file hashes, a base that differs only outside the hunk context is not detected; the stricter check needs a hash field in AEVE.
- Files with CRLF or bare CR line ends, or with no final newline, produce AEVE diffs (built on `splitlines`) that `git apply` rejects; they surface as `STALE_BASE`. Diffs with redacted secrets are BLOCKED.
- No OS sandbox or process containment, same as U5-1; a model change set is not applied by this module.
- AEVE has no command that emits the document; its production and transport are outside this task.
