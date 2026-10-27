# Change 0417: record pinned Temporal Server build-profile metadata

## What changed

- Added a source-only screen of the pinned server's Go version and GoReleaser build/checksum configuration.
- Linked the screen from S3 state, backlog, and both continuation reports.
- Regenerated the document registry and conformed the reports.

## Why

The S3 audit had publisher-provided release digests and Go-toolchain release metadata, but did not record the exact pinned server source's declared build matrix and checksum configuration. This narrows the provenance question without claiming that the release archive was produced by the configuration.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-server-build-profile-source-screen-20261027.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `docs/sdlc/STATE.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0417-record-temporal-server-build-profile.md`

## Provenance and review

- Starting HEAD: `3467945f0a3f10b9292b182d23ae7d5191f7f2e2`; branch `s4-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
- Primary evidence is read-only file content at the already pinned source commit; public workflow execution logs and release artifacts were not acquired. A `code-reviewer` agent (GPT-6 Luna, low effort) reviewed the staged source claims and RU/EN wording and reported no actionable findings.
- This is source configuration metadata only. It does not prove actual release invocation, toolchain patch version, reproducibility, artifact/source identity, or runtime compatibility.
- No source code, candidate acquisition, build, install, execution, acceptance tests, policy selectors, push, PR, merge, or new worktree/fork occurred.
- The protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Verification and acceptance

- Both pinned files were inspected read-only at commit `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- `python C:/Users/koros/.claude/tools/report_conform.py reports --check` reported `all reports carry the mandated block`; `python tools/build_document_registry.py --check` reported `DOCUMENT_REGISTRY.md is current`; `git diff --cached --check` completed successfully with no output.
- S2 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: continue only bounded source-level provenance checks; do not infer release execution from configuration.
2. Operator: decide legal/acquisition disposition before any artifact retrieval.
3. GPT-PM: review architecture separately; exact artifact/runtime gates remain open.
