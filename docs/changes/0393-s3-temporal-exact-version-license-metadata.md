# Change 0393: distinguish S3 exact-version and repository-level license metadata

## What changed

- Added a bounded read-only evidence note comparing the visible license metadata for the pinned `nexus-proto-annotations@v0.1.0` repository with exact-tag contents and existing package metadata.
- Preserved the legal status as `NOT_VERIFIED`; no rights conclusion or acquisition approval is claimed.

## Why

The official repository overview displays an MIT badge, while prior exact-tag and package-metadata evidence did not identify a license. The distinction is relevant to S3-G01 and should remain explicit for the operator's legal disposition.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-exact-version-license-metadata-20261027.md`
- `docs/changes/0393-s3-temporal-exact-version-license-metadata.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Read-only official web review only; no source/artifact acquisition, download, build, install, test, or candidate execution.
- A `git diff --cached --check` command was issued during document review; its exit status was not preserved, so it is not treated as verification evidence.
- No policy-restricted S4 selector was run; all 53 remain `NOT_RUN`.
- This documentation-only change does not close S3 legal/provenance gates or S2/S4 acceptance.
- Protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not modified.

## Decision

Treat the GitHub repository-level MIT badge as metadata only, not as proof of exact-version rights. Keep S3-G01 open and require operator legal disposition before any acquisition.
