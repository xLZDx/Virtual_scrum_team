# Change 0427: refresh report provenance after 0426

## What changed

- Refreshed the generated Git provenance header in all twelve HTML status reports to the verified 0426 commit `4e0deef`.
- Regenerated the document registry to include this change record.

## Why

Commit `4e0deef` added upstream artifact metadata and corrected the S3 report. This generated-only follow-up aligns all report baselines without changing their acceptance claims.

## Affected paths

- All twelve HTML status reports under `reports/` (generated provenance headers only)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0427-refresh-report-provenance-after-0426.md`

## Provenance and review

- Starting HEAD: `4e0deef412b1f3fd7c28b58ead95ddd051566e1c`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status showed only protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; this refresh did not alter, stage, or remove it.
- All twelve report headers referenced prior baseline `5ad25ca`; all now reference `4e0deef`.
- No project code, acceptance tests, builds, CI, migrations, candidate acquisition/execution, push, PR, merge, or worktree operation occurred.
- This generated provenance change does not advance S2–S5 acceptance.

## Verification and acceptance

- Documentation hygiene passed: `python tools/build_document_registry.py`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, `git diff --cached --check`, and `python tools/build_document_registry.py --check` all succeeded. A repository search confirmed all twelve report headers now use `4e0deef` and no prior `5ad25ca` header remains.
- This mechanical header refresh reuses the substantive review recorded in change 0426 and requires no additional local review.

## Ordered next steps and owners

1. Codex: finish documentation hygiene and commit this provenance refresh.
2. GPT-PM: return the pending S3 architecture adjudication; Codex records a correlated response only after the bridge confirms generation completion.
