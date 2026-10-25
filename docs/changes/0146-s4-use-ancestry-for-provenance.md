# 0146 S4 use ancestry query for provenance

## What changed

- Removed the separate `git cat-file` existence gate from top-level and category provenance validation.
- Kept full lowercase SHA syntax validation, then use the bounded `git merge-base --is-ancestor` query as the single commit-existence/history proof.
- Changed valid-but-missing, stale, or out-of-history provenance failures to state those causes together.
- Retained `_git_commit_exists` only because existing focused tests monkeypatch its private symbol; no live provenance path calls it.
- Updated the S4 plan/backlog and decision/lesson records; regenerated the document registry.

## Why

The latest functional evidence at test HEAD `64b8bb1` recorded two committed-registry failures: valid source-head SHAs were rejected by the separate existence query, while direct `git cat-file` commands later confirmed those commits existed. That helper maps both timeout and nonzero exit to `False`, so the reported “not a full SHA” diagnosis was inaccurate. The plan already requires ancestry to the exact candidate; that query also proves the object exists and preserves fail-closed behavior on timeout or command error.

## Affected contracts and paths

- `tools/qa/registry.py`: top-level/category source provenance syntax and ancestry validation.
- `core/BACKLOG.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: current regression/fix state.
- `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`: single-query provenance decision and diagnosis rule.
- `governance/DOCUMENT_REGISTRY.md`: generated index.

## Decisions and ownership

- Preserve lowercase 40-character SHA validation before invoking Git.
- Treat missing object, non-ancestor, timeout, and Git invocation failure as a provenance rejection with a clear stale/missing/outside-history message.
- Keep the private existence helper symbol for existing test monkeypatch compatibility, but do not call it from `load_registry`.
- Accountable task owner: operator under delegated S4 continuation; executor: Codex. The project does not name a technical service owner for this registry.

## Verification state

- This coding pass ran no tests, checks, builds, CI, migrations, or runtime probes.
- The test agent's prior exact-head result remains 14 passed, 1 skipped, 1 failed twice at `64b8bb1`; the failure was the committed-registry provenance path. Evidence: `docs/sdlc/evidence/s4-bounded-registry-source-64b8bb1.md` and change 0145.
- Focused functional regression must rerun on the resulting committed head before this defect can be marked fixed.
