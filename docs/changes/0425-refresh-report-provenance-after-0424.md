# Change 0425: refresh report provenance after 0424

## What changed

- Refreshed the generated Git provenance header in all twelve HTML status reports to the verified 0424 commit `5ad25ca`.
- Regenerated the document registry to include this change record.

## Why

The 0424 generated-only provenance commit changed HEAD after the S2 checkpoint reports were written. This refresh keeps all report headers aligned with the latest verified repository state and does not change any S2–S5 acceptance claim.

## Affected paths

- All twelve HTML status reports under `reports/` (generated provenance headers only)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0425-refresh-report-provenance-after-0423.md`

## Provenance and review

- Starting HEAD: `5ad25caf21957332923b20056b2c5db74fbadef7`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status showed only protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; no bytes were changed, staged, or removed by this refresh.
- All twelve report headers referenced prior report baseline `c7b3205`; all now reference `5ad25ca`.
- No project code, acceptance tests, builds, CI, migrations, candidate acquisition/execution, push, PR, merge, or worktree operation occurred.
- This generated provenance change does not advance S2–S5 acceptance.

## Verification and acceptance

- Documentation hygiene passed: `python tools/build_document_registry.py`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, `git diff --cached --check`, and `python tools/build_document_registry.py --check` all succeeded. A repository search confirmed all twelve report headers now use `5ad25ca` and no prior `c7b3205` header remains.
- This mechanical header refresh reuses the substantive evidence review recorded in change 0421 and requires no additional local agent review.

## Ordered next steps and owners

1. Codex: finish documentation hygiene and commit this local provenance refresh.
2. GPT-PM: return the S3 architecture adjudication request `c91fcd58-8ab7-4bf5-994b-c3ea8f1c4713`; its current PM Bridge state is uncertain after the wait deadline and must be resolved before a correlated verdict can be recorded.
