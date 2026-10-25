# Change record 0213: Resolve Go license-page misses at pinned source revisions

## What changed

- Added a supplemental TSV mapping all 11 pkg.go.dev 404 module/version rows to raw upstream `LICENSE` or `LICENSE.md` files at the commit suffix in each pinned pseudo-version.
- Reconciled the S3 plan, VST-028 backlog, bilingual status report, and logs with the exact-revision source findings.

## Why

An unavailable pkg.go.dev page does not mean that a package has no license. Pinned pseudo-version commit suffixes allowed exact-revision checks of upstream legal files without downloading candidate source or archives.

## Evidence and limits

- Read-only security review by GPT-6 Luna, medium effort. The agent fetched only raw `LICENSE`/`LICENSE.md` text and GitHub commit/tree metadata; it did not write repository files or download source/package archives.
- Ten rows have text classified from the exact revision's legal file: three BSD-3-Clause, two MIT, five Apache-2.0 (the two genproto submodules share the same exact repo revision and file).
- `cactus/go-statsd-client@cb0885a1018c` uses `LICENSE.md`, not `LICENSE`; exact raw URL and GitHub recursive tree confirmed it. Its body matches the MIT permission/notice/warranty template; this is explicitly a text-based inference because it has no SPDX label.
- `planetscale/vtprotobuf@0393e58bdf10` has a three-condition BSD-style LICENSE. Whitespace-normalized text differs from the canonical SPDX BSD-3-Clause text; record as `BSD-3-Clause-like (SPDX unverified)`, not exact BSD-3-Clause metadata.
- After this follow-up, only `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0` lacks license evidence: its pkg.go.dev page says `License: None detected`, and its exact tag LICENSE path returns 404. Keep it `UNKNOWN`/`NOT_VERIFIED`; this does not establish that it is unlicensed.
- The full Go graph includes indirect/build/test dependencies and does not define a selected runtime profile or complete legal notice closure. No candidate was acquired, installed, built, or run.
- Raw source URLs, commit suffixes, response codes and classifications are in `docs/sdlc/evidence/s3-temporal-server-go-license-source-followup-2026-10-25.tsv`.

## Ownership and next step

- Accountable task owner: operator for delegated S3 completion.
- Audit executor: Codex; security-reviewer agent performed read-only source checks.
- The named technical candidate/runtime service owner is not present in canonical repository records. The operator owns candidate choice and acquisition authorization.
- Next: resolve exact-version evidence for the one `None detected` dependency where available; after candidate choice, define runtime/build profile and finish source-linked notice/provenance review. Do not acquire/run before explicit authorization and a fresh S2 probe.

## Verification state

This is a documentation and evidence-only update. Registry generation, bilingual report conformance, and `git diff --check` are recorded as part of this commit. No tests/build were run.
