# Change 0418: record pinned Temporal workflow-run outcomes

## What changed

- Added read-only GitHub Actions API results for all four runs attached to the exact pinned Temporal Server commit.
- Distinguished successful Build and Publish / Release runs from the separate failed All Tests run.
- Recorded the remaining provenance limitation: workflow status does not bind a published archive digest to a specific build artifact.
- Reconciled the S3 evidence screen, state, backlog, append-only decision log, and Russian/English continuation reports.
- Regenerated the document registry and report provenance after the final review.

## Why

The prior source screen documented the pinned GoReleaser configuration but had not checked whether public workflow runs existed for the exact pinned source SHA. The API query adds source-level process evidence while preserving the distinction between a successful workflow and verified source-to-binary artifact provenance.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-server-build-profile-source-screen-20261027.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- All twelve HTML status reports under `reports/` (two continuation reports updated with S3 run outcomes; generated provenance refreshed for all twelve)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0418-record-temporal-pinned-workflow-runs.md`

## Provenance and review

- Starting HEAD: `4878bd4bb41519469fc4c5f6b89c1e0234496e30`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Read-only public GitHub Actions API query filtered by exact `head_sha` returned four runs: Build and Publish `37665870819` (success), All Tests `37665870783` (failure), Release `37850182088` (success), and Trigger version-info-service release `37850182398` (success). The response metadata did not include job-level failure detail, and linked logs/artifacts were not retrieved.
- This workflow result does not prove release-asset/build-artifact identity or independently verify any asset digest. No external assets, logs, or build artifacts were downloaded.
- Actual `code-reviewer` agent review on the staged documentation diff: GPT-6 Luna, low effort; no actionable findings. The reviewer confirmed exact-SHA workflow outcomes, the explicit release-asset provenance limit, RU/EN alignment, and preservation of the protected untracked S2 evidence.
- No source code, acceptance tests, policy selectors, candidate acquisition/build/install/execution, push, PR, merge, or per-sprint worktree/fork occurred.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains protected and unstaged.

## Verification and acceptance

- `python tools/build_document_registry.py --check`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, and `git diff --cached --check` completed successfully after review. These are documentation hygiene checks, not sprint acceptance tests.
- The S3 source audit gained exact-SHA workflow outcome evidence, but release-asset provenance, runtime compatibility, legal/acquisition disposition, and candidate comparison remain open.
- S2 remains NOT APPROVED. S4 remains INCONCLUSIVE and all 53 policy selectors remain NOT_RUN. S5 remains gated.

## Ordered next steps and owners

1. Codex: complete the focused documentation review and hygiene checks, then commit this coherent record locally.
2. Operator: decide legal/acquisition authority before any Temporal artifact retrieval or execution.
3. GPT-PM: adjudicate architecture when the evidence set and exact decision scope are presented; this workflow screen is not an architecture or runtime approval.
