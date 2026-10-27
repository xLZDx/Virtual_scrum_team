# Change 0420: refresh report provenance after 0419

## What changed

- Refreshed the generated Git provenance header in all twelve HTML status reports from base `f26e789` to the verified repository HEAD `ed2f011`.
- Regenerated the document registry to include this change record.

## Why

Commit `ed2f011` completed the 0419 source-evidence report update after the reports had been generated against its parent `f26e789`. This follow-up aligns the generated report provenance with that final pre-change-record source baseline without changing the reports' acceptance claims.

## Affected paths

- All twelve HTML status reports under `reports/` (generated provenance only)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0420-refresh-report-provenance-after-0419.md`

## Provenance and review

- Starting HEAD: `ed2f0113d0b5867af54daf5d903eccc464acb4d3`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Initial `git status --short` showed only the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; that protected evidence was not modified or staged.
- The report headers showed `s4-canonical-continuation @ f26e789` while `git rev-parse HEAD` returned `ed2f0113d0b5867af54daf5d903eccc464acb4d3`.
- No acceptance tests, policy selectors, builds, CI, migrations, acquisition, candidate execution, push, PR, merge, or worktree creation occurred.

## Verification and acceptance

- The registry freshness check passed before edits. Run report conformance, registry freshness, and staged whitespace checks after regeneration.
- This is generated documentation provenance only; it does not change S2–S5 acceptance status.

## Ordered next steps and owners

1. Codex: run the specified documentation-hygiene checks and commit this local provenance follow-up.
2. Codex: resume the ordered S2–S5 queue at the next permitted source/evidence step; preserve the protected untracked S2 evidence.
