# Change 0431: decode cass_os3 upstream test artifacts

## What changed

- Downloaded and decoded the listed cass_os3 shard-2 test-summary and JUnit artifacts through the connected read-only GitHub artifact tool.
- Verified both downloaded ZIP SHA-256 values against GitHub's listed artifact digests.
- Added a bounded evidence record separating interrupted `RUN/PAUSE` entries from explicit failure diagnostics and mapping newly visible error families to the proposed VST profile.
- Updated upstream artifact, failure-detail, S3 risk-disposition, backlog, state and decision records; the earlier unknown-content status is superseded.

## Why

GPT-PM's prior S3 adjudication noted that cass_os3 failure details were unavailable and that artifact metadata alone could not support impact classification. The artifacts were accessible through the authorized read-only GitHub connector, so Codex recovered the content instead of leaving that evidence gap unresolved. Newly revealed failures require a separate focused architecture review; no candidate is executed.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-cassos3-artifact-detail-20261027.md`
- `docs/sdlc/evidence/s3-temporal-upstream-ci-artifact-metadata-20261027.md`
- `docs/sdlc/evidence/s3-temporal-upstream-ci-failure-detail-20261027.md`
- `docs/sdlc/evidence/s3-temporal-upstream-ci-risk-disposition-20261027.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `docs/changes/0431-decode-cassos3-upstream-test-artifacts.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting HEAD: `90c8f810548ec89e1ee82d1fb82fdf31ed7e119b` on branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status contained only the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not modified, staged or removed.
- GitHub run `37665870783`, failed job `112946311769`, exact Temporal Server SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- Summary artifact `11505227999`: 14,568 ZIP bytes; listed/local SHA-256 `a626dc457d9c7a39571a7af0f2ca0ac132f0626c70b396377a0279635fe0bc60`.
- JUnit artifact `11505437566`: 122,301 ZIP bytes; listed/local SHA-256 `919df4fb8ce68b78316690f84e022ffbc00038894d1bea2f97dec21572693e56`.
- Extracted artifacts were inspected read-only under the task's temporary directory and not copied into the repository. No candidate source or executable was acquired.
- No local acceptance tests, tests/checks, builds, CI reruns, migrations, network probes, restricted selectors, candidate execution, push, PR, merge, or worktree operations occurred.

## Verification and acceptance

- Focused read-only `code-reviewer` pass (GPT-6 Luna, low effort) at HEAD `90c8f810548ec89e1ee82d1fb82fdf31ed7e119b` found no actionable finding. The review confirmed that RUN/PAUSE-only rows remain incomplete reporter entries, aggregate counts are not treated as distinct defects, and each profile classification preserves its runtime boundary. No tests/checks were run; the protected S2 file was untouched.
- Documentation hygiene passed: `python tools/build_document_registry.py --check`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, and `git diff --cached --check` all succeeded.
- Upstream cass_os3 remains **FAILED**. 657 of the 675 summary rows marked `Failed` show only `RUN/PAUSE` entries; these are not counted as distinct completed failure diagnostics. Explicit callback/schedule failures are mapped outside the current G07 API scope; versioning/task-forward failures remain unresolved; activity timeout/goroutine behavior requires future qualification.
- The source-only S3-CI-N01 verification predates this newly recovered artifact detail. This supplemental impact mapping is not yet GPT-PM adjudicated. Root cause/reproducibility remain unknown; no runtime or S3 acceptance is claimed.

## Ordered next steps and owners

1. Codex: complete the focused documentation review and hygiene; commit this evidence with its detail record.
2. GPT-PM: adjudicate only the newly recovered cass_os3 failure families and their mapping to the proposed VST profile at the exact committed documentation state.
3. Codex: preserve upstream failure status and unresolved runtime qualifications; do not run the CI or local candidate tests.
