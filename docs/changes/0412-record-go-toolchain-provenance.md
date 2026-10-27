# Change 0412: record Go toolchain release provenance metadata

## What changed

- Added a read-only evidence record for the official Go `1.26.10` Linux amd64 download digest and reproducible-build report.
- Linked the evidence from the S3 backlog, phase state, and bilingual continuation report.
- Regenerated the document registry and conformed both HTML reports.

## Why

The accepted G03 design pins an official Go toolchain and records its expected SHA-256, but the authoritative public download and rebuild pages had not been reconciled into the active S3 evidence package. This narrows the provenance record without acquiring the archive or authorizing a build.

## Affected paths

- `docs/sdlc/evidence/s3-go-toolchain-release-provenance-screen-20261027.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `core/DECISION_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated from the staged index)
- `docs/changes/0412-record-go-toolchain-provenance.md`

## Provenance and review

- Starting HEAD: `b3082a5cb7cc7954e7ca120ddf297c90ab02e31b`, branch `s4-canonical-continuation`.
- Evidence is read-only metadata from `https://go.dev/dl/` and `https://go.dev/rebuild`.
- No toolchain archive was downloaded, installed, executed, or locally hash-verified. No Temporal candidate was acquired, built, installed, or executed.
- No source code, project tests, CI, migration, push, PR, merge, or sprint-specific worktree/fork occurred.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Verification and acceptance

- The document registry was regenerated from the staged index.
- Both HTML reports were conformed and the reports directory was checked with `report_conform.py`.
- Public Go metadata reports the design-pinned digest and a reproducible-build pass; local archive integrity and Temporal server build provenance remain `NOT_VERIFIED` / `NOT_RUN`.
- S2 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: continue read-only provenance/compatibility audit; keep all runtime claims gated.
2. Operator: authorize legal/acquisition prerequisites before any archive retrieval or server build.
3. GPT-PM: adjudicate changed architecture or the final delivery head after acceptance evidence exists.
