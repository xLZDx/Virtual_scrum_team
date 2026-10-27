# Change 0429: disambiguate proposed S5 subtasks from canonical VST IDs

## What changed

- Replaced proposed `VST-038`–`VST-042` identifiers in the S5 plan with provisional `S5-P01`–`S5-P05` decomposition keys under canonical backlog item `VST-041`.
- Clarified that S5-P keys are not backlog IDs and do not allocate canonical IDs before S5 formally starts.
- Assigned Codex ownership for resolving the missing AEVE source/service identity evidence instead of leaving that dependency ownerless.

## Why

The S5 plan's proposed VST identifiers collided with canonical S4 IDs in `core/BACKLOG.md` and included IDs already used by S4. The current S5 backlog is represented by VST-041; provisional subtasks must not create ambiguous ownership or alter the canonical backlog sequence prematurely.

## Affected paths

- `docs/S5_AEVE_GATE_PLAN_2026-10-24.md`
- `docs/changes/0429-disambiguate-proposed-s5-subtasks.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting HEAD: `0a9a70bd5d80a64bba4c7d6e9f8ae7f47dd24ac6`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status contained only protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not modified, staged or removed.
- This is a documentation-only clarification. No source/test code, tests, builds, CI, migrations, candidate acquisition/execution, restricted selector, push, PR, merge, or worktree operation occurred.

## Verification and acceptance

- Focused read-only document review by `code-reviewer` (GPT-6 Luna, low effort) at HEAD `0a9a70bd5d80a64bba4c7d6e9f8ae7f47dd24ac6` found one MINOR ownership-terminology issue: it described test and implementation roles as task owners. Codex corrected the plan to retain project ownership with Codex/operator while identifying test/implementation roles as execution roles. The reviewer rechecked only the corrected S5 plan and this record, confirmed the MINOR closed, and found no further issue. No test or check was run; the protected S2 untracked file was not touched.
- Canonical backlog IDs are unchanged; the change only avoids using them for provisional S5 decomposition.

## Ordered next steps and owners

1. Codex: complete documentation registry generation/freshness and HTML report conformance; commit this clarification.
2. Codex: keep S5 `NOT_RUN` until S2/S4 gates close and an authorized in-scope AEVE source/interface is identified.
