# Change 0422: refresh report provenance after 0421

## What changed

- Refreshed the generated Git provenance header in all twelve HTML status reports to the verified 0421 commit `8efba69`.
- Regenerated the document registry to include this change record.

## Why

Commit `8efba69` changed the repository after the previous report baseline. Updating only report provenance keeps every existing report tied to the same verified source head; it does not change their acceptance claims.

## Affected paths

- All twelve HTML status reports under `reports/` (generated provenance headers only)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0422-refresh-report-provenance-after-0421.md`

## Provenance and review

- Starting HEAD: `8efba69486b34e542a50357ee1be9ce6feb55487`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status showed only the protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; its contents were not read, changed, staged, or removed.
- The twelve report provenance headers referenced the prior report baseline (`ed2f011` or `c014333`); all now reference `8efba69`.
- No project code, acceptance tests, builds, CI, migrations, candidate acquisition/execution, push, PR, merge, or worktree operation occurred.
- This change is generated provenance only and does not advance S2–S5 acceptance.

## Verification and acceptance

- Documentation hygiene passed: `python tools/build_document_registry.py`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, `git diff --cached --check`, and `python tools/build_document_registry.py --check` all succeeded. A repository search confirmed all twelve report headers now use `8efba69` and no old `ed2f011`/`c014333` header remains.
- No local agent review is needed for this mechanical generated-header refresh; substantive evidence and report-content review is recorded in change 0421.

## Ordered next steps and owners

1. Codex: finish documentation hygiene and commit this local provenance refresh.
2. GPT-PM: return the requested S3 adversarial architecture adjudication; Codex verifies and records the correlated response.
