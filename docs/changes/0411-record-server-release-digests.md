# Change 0411: record published Temporal Server release digests

## What changed

- Added a bounded read-only evidence record for the official Temporal Server `v1.32.1` release assets metadata.
- Recorded the published SHA-256 values for `checksums.txt` and `temporal_1.32.1_linux_amd64.tar.gz` without claiming byte-level verification.
- Reconciled current S3 state and VST-028 to the correlated G03 design acceptance and the new partial provenance evidence.
- Updated the bilingual S2–S5 handover with the new artifact-metadata boundary and corrected the stale current G03 status in `core/STATE.md`.
- Regenerated the document registry and conformed both HTML reports.

## Why

The official pinned release page exposes useful digest metadata without downloading the candidate. Recording it narrows the provenance gap while preserving the separate acquisition and runtime gates.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-server-release-provenance-screen-20261027.md`
- `core/BACKLOG.md`
- `core/STATE.md`
- `docs/sdlc/STATE.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `core/DECISION_LOG.md`
- `governance/DOCUMENT_REGISTRY.md` (generated from the staged index)
- `docs/changes/0411-record-server-release-digests.md`

## Provenance and review

- Starting HEAD: `dc19a7fc0f246968d1e82b89afa06f5ab43fa626`, branch `s4-canonical-continuation`.
- Evidence is a read-only view of [the official expanded release assets page](https://github.com/temporalio/temporal/releases/expanded_assets/v1.32.1), cross-linked with [the exact release page](https://github.com/temporalio/temporal/releases/tag/v1.32.1).
- No asset bytes or checksum file were downloaded. No source code, project tests, build, CI, migration, acquisition, installation, candidate execution, push, PR, merge, or sprint-specific worktree/fork occurred.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Verification and acceptance

- The document registry was regenerated from the staged index.
- Both HTML reports were conformed and the reports directory was checked with `report_conform.py`.
- Published digests are metadata only; independent checksum verification and source-to-binary provenance remain open. S2 stays `NOT APPROVED`; S4 stays `INCONCLUSIVE` with 53 selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: continue read-only S3 provenance and compatibility work; do not acquire or execute the candidate.
2. Operator: decide the exact-version legal/acquisition disposition before authorizing artifact retrieval.
3. GPT-PM: adjudicate changed architecture or the exact delivery head after acceptance evidence exists.
4. Codex: resume S5 only after S2/S4 closure and an identified/authorized in-scope AEVE source.
