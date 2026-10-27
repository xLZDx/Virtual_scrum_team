# Change 0413: record pinned Go dependency license-source follow-up

## What changed

- Added read-only source observations for the pinned `vtprotobuf` LICENSE and unresolved `nexus-proto-annotations` source files.
- Reconciled S3 state, backlog and bilingual continuation reports with the exact limits of those observations.
- Regenerated the document registry and conformed the reports.

## Why

The existing Go dependency follow-up had recorded a BSD-style but noncanonical `vtprotobuf` license and `UNKNOWN` for `nexus-proto-annotations`. Direct inspection of the exact pinned source files narrows the facts available to the audit without making an SPDX/legal determination or acquiring dependencies.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-go-license-detail-followup-20261027.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `core/DECISION_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0413-record-go-dependency-license-source-followup.md`

## Provenance and review

- Starting HEAD: `cddc91e`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Primary evidence is the exact pinned upstream raw files linked from the evidence screen; the recursive Nexus tree and package metadata claims are attributed to the existing in-repository TSV record.
- This is technical source evidence only. Nexus license terms remain `UNKNOWN`; the broader dependency inventory and legal/acquisition decision remain open.
- No source code, dependency acquisition, build, install, candidate execution, project tests, policy selectors, push, PR, merge, or sprint-specific worktree/fork occurred.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Verification and acceptance

- The evidence is bounded to the exact revisions already recorded by the S3 audit.
- `python C:/Users/koros/.claude/tools/report_conform.py reports/S2_S5_CONTINUATION_2026-10-27.ru.html reports/S2_S5_CONTINUATION_2026-10-27.html` refreshed both reports; the directory `--check` reported `all reports carry the mandated block`.
- `python tools/build_document_registry.py --check` reported `DOCUMENT_REGISTRY.md is current`; `git diff --cached --check` exited successfully with no output.
- S2 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: continue only bounded read-only S3 source/provenance reconciliation; keep unknown terms unknown.
2. Operator: decide whether the remaining legal/acquisition evidence is sufficient or provide the required disposition.
3. GPT-PM: adjudicate architecture separately from legal acceptance; no duplicate design request is implied.
