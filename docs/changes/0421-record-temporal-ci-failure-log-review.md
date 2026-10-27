# Change 0421: record Temporal upstream CI failure-log review

## What changed

- Added a bounded read-only evidence note for the three failed SQLite shards in the pinned Temporal Server `All Tests` run.
- Updated the S3 backlog entry, decision log, current state, and Russian/English continuation reports to distinguish the newly inspected upstream logs from local acceptance evidence.

## Why

The previous status only recorded failed job metadata and explicitly said the failure logs had not been inspected. The connected GitHub tool made the three SQLite job logs readable. Recording their partial counts and observed messages improves the S3 risk audit without treating upstream failures as local proof or inferring a root cause.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-upstream-ci-failure-detail-20261027.md`
- `docs/sdlc/evidence/s3-temporal-server-build-profile-source-screen-20261027.md` (clarified the historical status and linked the later log review)
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `docs/sdlc/STATE.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0421-record-temporal-ci-failure-log-review.md`

## Provenance and decisions

- Starting HEAD: `c014333a9c26c76d4c201ea430393d9b395691f9`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status was clean except for protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; its contents were not read, changed, staged, or removed. The evidence/report edits below were made in this turn after that baseline.
- Historical upstream run: `37665870783`, exact Temporal Server SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- The connected GitHub workflow-job-logs tool returned readable logs for SQLite shards 0/1/2: their partial summaries report 49/52/59 shard failures respectively, followed by the 39-minute runner timeout. Observed messages include worker-versioning lookup failures, a SQLite `workflow_type_name` length constraint failure, and context deadlines. These are per-shard counts, not unique defect counts; no common root cause or reproducibility was established.
- The `cass_os3` shard 2 log request returned empty content, so its failure detail remains unknown. No raw log archive or test-summary artifact was saved.
- This is upstream CI history, not a local test, build, candidate execution, or acceptance result. No code, test, policy selector, build, CI, migration, acquisition, installation, push, PR, merge, or worktree operation was performed.
- Decision: preserve Temporal as provisional only; provide the full S3 candidate decision and bounded CI evidence to GPT-PM for adversarial architecture adjudication. Operator legal/acquisition authority remains reserved.

## Verification and acceptance

- Documentation hygiene commands succeeded after the corrections: `python tools/build_document_registry.py`; `python C:/Users/koros/.claude/tools/report_conform.py reports --check`; `git diff --cached --check`; `python tools/build_document_registry.py --check`.
- Review: actual read-only `code-reviewer` agent, GPT-6 Luna, low effort. Initial review found three MINOR documentation issues: the build-profile screen did not identify itself as the earlier status; STATE did not date the earlier “logs not inspected” statement; and VST-028 duplicated the SQLite summary. All three were corrected. The focused read-only recheck confirmed all three resolved and found no new issues. No tests or acceptance checks were run by the reviewer.
- S2 remains partially evidenced; prohibited acceptance scenarios remain `NOT_RUN`. S3 remains provisional and read-only. S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`. S5 remains blocked by S2/S4 and source authorization. Sprint tests/reviews, exact-head GPT-PM approval, and PR/merge remain deferred.

## Ordered next steps and owners

1. Codex: complete documentation hygiene and local commit for this evidence record.
2. GPT-PM: adjudicate the complete provisional S3 candidate decision in light of the exact pinned source and upstream CI evidence; Codex verifies and records the correlated response.
3. Codex: continue permitted S2 evidence collection and S3 read-only audit; keep prohibited tests/selectors and unauthorized acquisition/execution unrun.
4. Operator: provide any required legal/acquisition decision, exact S4 waiver if desired, and an in-scope AEVE source only after S2/S4 prerequisites close.
