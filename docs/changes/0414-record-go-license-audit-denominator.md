# Change 0414: reconcile Go dependency license metadata denominator

## What changed

- Recorded the row count and disposition of every metadata-gap row in the existing S3 Go license inventory.
- Updated the S3 backlog, phase state, decision log, and RU/EN continuation report to use the same counts and caveats.
- Regenerated the document registry and conformed both HTML reports.

## Why

The prior source-only audit resolved specific upstream facts but did not state the denominator of the existing Go license tables. Reconciliation shows that every metadata-gap row is represented in the source follow-up, while preserving the remaining SPDX and legal uncertainty.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-go-license-detail-followup-20261027.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `docs/sdlc/STATE.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0414-record-go-license-audit-denominator.md`

## Provenance and review

- Starting HEAD: `b2237628b597ec7885e2a8c714d3fd6e6f22cc6b`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Read-only row counts came from the two in-scope TSV files. The 12 follow-up entries comprise 10 source-text/template classifications, one noncanonical BSD-style entry without verified SPDX, and one `UNKNOWN` Nexus entry. A `code-reviewer` agent (GPT-6 Luna, low effort) independently reviewed the staged denominator and RU/EN reconciliation and reported no actionable findings.
- This reconciles only the recorded table; it does not prove complete transitive dependency closure, legal acceptability, or acquisition approval.
- No source code, dependency acquisition, candidate build/install/execution, acceptance test, policy selector, push, PR, merge, or sprint-specific worktree/fork occurred.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Verification and acceptance

- Both tables were parsed and cross-compared read-only: 223 metadata rows, 12 flagged rows (11 HTTP 404 and one `NONE_DETECTED`), and 12 follow-up rows. The set comparison found no flagged row missing from or extra in the follow-up list.
- `python C:/Users/koros/.claude/tools/report_conform.py reports/S2_S5_CONTINUATION_2026-10-27.ru.html reports/S2_S5_CONTINUATION_2026-10-27.html` refreshed both reports; `reports --check` reported `all reports carry the mandated block`. `python tools/build_document_registry.py --check` reported `DOCUMENT_REGISTRY.md is current`; `git diff --cached --check` completed successfully with no output.
- S2 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: continue only if another concrete read-only S3 source question is identified; do not infer legal conclusions.
2. Operator: decide whether the remaining license/acquisition evidence is sufficient or provide the required disposition.
3. GPT-PM: adjudicate architecture separately from legal acceptance.
