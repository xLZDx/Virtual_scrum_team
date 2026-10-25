# Change record 0214: Check the exact Nexus annotation tag for legal files

## What changed

- Extended the S3 source-follow-up TSV with the exact GitHub tree result for `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`.
- Updated the S3 plan, VST-028 backlog, bilingual report, and logs to record that no common legal-file path exists in the complete exact-tag tree.

## Why

The versioned pkg.go.dev page says `License: None detected`, and the exact `v0.1.0/LICENSE` path returned 404. Checking the complete tag tree for alternate legal filenames tests whether another in-scope primary license file was missed.

## Evidence and limits

- Exact GitHub tree URL: `https://api.github.com/repos/nexus-rpc/nexus-proto-annotations/git/trees/v0.1.0?recursive=1`; HTTP 200, resolves tag to commit `e558d6edaf84e280dddfc87b5b8ce1662f66ac8b`, `truncated=false`.
- No path matched `LICENSE`, `LICENSE.md`, `LICENCE`, `COPYING`, `NOTICE`, or `COPYRIGHT`.
- The exact pkg.go.dev v0.1.0 page reports `License: None detected`; the exact root LICENSE URL returns 404. Current upstream `main` MIT metadata and sibling-module policy are not evidence for this tag.
- Keep the version license `UNKNOWN`/`NOT_VERIFIED`; absence of a common license filename is not proof that the package is legally unlicensed. No named package maintainer or license owner is established by repository records.
- Raw/tree source follow-up remains in `docs/sdlc/evidence/s3-temporal-server-go-license-source-followup-2026-10-25.tsv`. No source/package/archive was downloaded; no install, build, run, or test occurred.

## Ownership and next step

- Accountable task owner: operator for delegated S3 completion.
- Audit executor: Codex; the agent performed read-only GitHub metadata lookup.
- Technical license owner/maintainer: UNKNOWN in canonical project records.
- Next: if this package is part of the selected runtime profile, obtain an exact-version license statement from its upstream maintainer; otherwise retain it as unresolved metadata for the broad `go.mod` graph and keep candidate acquisition gated until the selected profile's license closure is satisfied.

## Verification state

The supplemental TSV was read back as 13 rows including its header; the new exact-tag tree row returned HTTP 200. Registry generation, report conformance, and `git diff --check` are recorded by the commit workflow. No test/build was run.
