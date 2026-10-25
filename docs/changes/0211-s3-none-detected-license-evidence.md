# Change record 0211: Clarify the exact-version Go license metadata result

## What changed

- Updated the S3 plan, VST-028 backlog row, bilingual status report, logs, and generated document registry with the exact-version metadata for `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`.
- Corrected the previous aggregate description: one retrievable pkg.go.dev page explicitly says `License: None detected`; the package version's license remains `UNKNOWN`/`NOT_VERIFIED`.

## Why

The first scan described the page as lacking a license section. A low-rate follow-up could retrieve the exact-version page and distinguish an explicit “none detected” result from an HTTP lookup failure. The current upstream `main` license cannot be attributed to the older `v0.1.0` tag.

## Evidence and limits

- Read-only audit by `security-reviewer`, GPT-6 Luna, medium effort; no repository files or source packages were downloaded or modified by the reviewer.
- Exact version page: https://pkg.go.dev/github.com/nexus-rpc/nexus-proto-annotations@v0.1.0?tab=licenses — HTTP 200 and `License: None detected`.
- Exact tag license path: https://github.com/nexus-rpc/nexus-proto-annotations/blob/v0.1.0/LICENSE — HTTP 404.
- Current upstream repository `main` is marked MIT, but that is not evidence for the exact older version. A third-party policy infers MIT from sibling repositories; it is not package-version primary evidence.
- The other 106 module/version lookups from the 223-entry Go scan remain unresolved after HTTP 429. No source archive, package, binary, or candidate was downloaded; no install/build/run occurred. Full Go dependency license closure remains open.

## Ownership and next step

- Accountable task owner: operator for the delegated S3 sprint.
- Audit executor: Codex; the agent performed a read-only source check.
- Candidate selection and acquisition authorization remain operator-owned. The technical service owner is not identified in the inspected canonical project sources.
- Next: retry the 106 exact-version metadata lookups at a controlled rate, preserve the precise `None detected` status for this version, then define the selected runtime/build profile only after candidate choice.

## Verification state

Documentation-only reconciliation. `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and regenerated the registry; the named `report_conform.py` command exited 0 and refreshed both HTML reports; `git diff --check` exited 0. No test/build was run.
