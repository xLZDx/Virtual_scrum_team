# Change 0426: record `cass_os3` upstream artifact metadata

## What changed

- Added GitHub-listed test-summary and JUnit artifact identifiers/digests for the failed `cass_os3` shard 2 in the pinned Temporal upstream CI run.
- Clarified that the summary ZIP was retrieved to a temporary file reference but its contents were not inspected; the JUnit ZIP was not downloaded.
- Updated the S3 backlog and RU/EN continuation report to distinguish artifact metadata from decoded failure evidence.

## Why

The workflow-job-logs connector returned empty content for this failed shard. GitHub's artifact metadata provides a traceable source for a later read, but it does not reveal which tests failed until the artifact contents are decoded.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-upstream-ci-artifact-metadata-20261027.md`
- `docs/sdlc/evidence/s3-temporal-upstream-ci-failure-detail-20261027.md`
- `core/BACKLOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0426-record-cass-os3-artifact-metadata.md`

## Provenance and decisions

- Starting HEAD: `88cefab96ba297c3c21b3d3edc4a1182e1b829d0`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status showed only protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; no contents or bytes were changed, staged, or removed as part of this evidence update.
- The GitHub artifact-list API tied artifact IDs `11505227999` (test summary) and `11505437566` (JUnit) to failed job `112946311769`, run `37665870783`, and pinned SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- The summary ZIP retrieval returned a temporary file reference, not inspected contents. No artifact copy was stored in the repository and no locally computed archive digest is claimed.
- This is upstream metadata only, not a local test/build or candidate acceptance result. No code, project test, policy selector, build, CI, migration, acquisition, candidate execution, push, PR, merge, or worktree operation occurred.

## Verification and acceptance

- Documentation hygiene passed after the RU/EN report correction: `python tools/build_document_registry.py`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, `git diff --cached --check`, and `python tools/build_document_registry.py --check` all succeeded.
- Review: actual read-only `code-reviewer`, GPT-6 Luna, low effort. The reviewer verified the artifact IDs, sizes, GitHub-listed digests, run, and pinned SHA against the artifact API and found the distinction between metadata, opaque ZIP retrieval, and unread contents accurate. It initially found one MINOR mismatch: this change record claimed both reports had changed, while the report text had not yet been updated. The RU/EN report paragraphs and links are now corrected; the focused recheck result follows.
- Focused recheck: all corrected. Both RU/EN reports link the artifact-metadata evidence and state that the summary ZIP reference was not decoded. The change-record paths match the final diff, and the initial finding/fix is described accurately. No tests or checks were run by the reviewer.
- S3 remains provisional; this metadata does not establish a failure cause. S2/S4 restrictions remain in force.

## Ordered next steps and owners

1. Codex: complete documentation hygiene and commit this evidence clarification locally.
2. GPT-PM: return the existing S3 architecture adjudication; do not create a second request while the first is unresolved.
3. Codex: inspect the `cass_os3` summary only if an authorized artifact reader becomes available and the details can affect the adjudication.
