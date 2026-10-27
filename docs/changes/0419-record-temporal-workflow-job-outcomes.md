# Change 0419: record pinned Temporal workflow job outcomes

## What changed

- Queried job-level metadata for the exact-SHA `Build and Publish` and `All Tests` GitHub Actions runs.
- Recorded successful Linux amd64/arm64 and Docker build jobs, plus four failed functional-test shards and the failed aggregate status job.
- Preserved the distinction between upstream CI history, local acceptance, and release-asset provenance.
- Updated the S3 evidence screen, state, backlog, append-only decision log, and Russian/English continuation reports.
- Regenerated the document registry and report provenance.

## Why

Change 0418 established workflow-level outcomes but deliberately did not retrieve linked logs. The public job API provides a bounded source-only refinement: it identifies which jobs failed without fetching logs or artifacts or inferring failure causes.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-server-build-profile-source-screen-20261027.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- All twelve HTML status reports under `reports/` (two continuation reports updated with job outcomes; generated provenance refreshed for all twelve)
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0419-record-temporal-workflow-job-outcomes.md`

## Provenance and review

- Starting HEAD: `166ddc3c9f3af6cd17486c5bfb95e7a1c3030edc`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Read-only public GitHub API job responses for Build and Publish run `37665870819` showed `build-binaries (amd64)`, `build-binaries (arm64)`, and `build-and-push-docker` completed successfully.
- All Tests run `37665870783` showed four failed functional-test jobs: SQLite shards 0/1/2 and cass_os3 shard 2; the aggregate `Test Status` job failed. Failure logs were not inspected, so root causes are unknown.
- The exact-pinned release workflow checks out `${{ github.ref }}` and invokes the local Build Binaries action with release mode enabled. The action selects Go from `go.mod` and configures GoReleaser v2.13.1. Release run `37850182088` had successful checkout and Build binaries steps. This strengthens build-invocation evidence without independently binding any published asset bytes or digest to that output.
- No release asset, log bundle, or build artifact was downloaded. No local acceptance test, policy selector, build, installation, or candidate execution occurred.
- A GPT-6 Luna `code-reviewer` (low effort) identified two MINOR documentation issues in the first staged review: omitted skipped jobs and duplicated run links. Both were corrected; a follow-up reviewer confirmed both fixes and reported no new findings. The pinned release-workflow/action evidence was added afterward and is pending one final focused review before commit.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains protected and unstaged.

## Verification and acceptance

- Rerun `python tools/build_document_registry.py --check`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, and `git diff --cached --check` after the final report update; these are documentation hygiene checks, not sprint acceptance tests.
- This strengthens read-only S3 CI/build-invocation evidence only. It does not independently prove that a published asset digest matches the release build output, explain CI failures, satisfy local compatibility/runtime acceptance, or provide legal/acquisition approval.
- S2 remains NOT APPROVED. S4 remains INCONCLUSIVE and all 53 policy selectors remain NOT_RUN. S5 remains gated.

## Ordered next steps and owners

1. Codex: complete the focused review and hygiene checks, then commit this documentation follow-up locally.
2. Codex: continue only source-level audit work that does not require artifact acquisition or runtime execution.
3. Operator: decide legal/acquisition authorization before any candidate artifact retrieval or execution.
4. GPT-PM: adjudicate architecture at the appropriate acceptance gate; this CI metadata is not such an approval.
