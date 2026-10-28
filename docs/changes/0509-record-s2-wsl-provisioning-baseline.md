# Change 0509 — Record current S2 WSL provisioning baseline

Date: 2026-10-28

## What changed and why

Captured a read-only inventory of the dedicated Ubuntu-24.04 WSL2 after the operator directed
Codex to prepare the coordinator and fresh E5 evidence. This reconciles the user's clarification
with older E5 evidence and separates current-host state from historical runs.

## Evidence and affected records

- Exact read-only inventory: `docs/sdlc/evidence/s2-wsl-provisioning-baseline-20261028.md`.
- Current summary: `core/STATE.md`.
- Ordered S2 blockers: `core/BACKLOG.md`.
- Generated registry: `governance/DOCUMENT_REGISTRY.md`.
- Coordinator design/amendment: `docs/sdlc/evidence/s2-coordinator-architecture-proposal-20261028.md`.

The WSL distribution has automount/interoperability disabled and installed unit templates matching
the repo, but the service configurations and current runtime manifest are absent; services are
disabled/inactive and the installed helper is from an older source head. Existing separated key
files and historical private E5 inventory are present with restrictive metadata; no secret values
were read. Historical E5 records do not establish current-head acceptance.

## Architecture and authorization state

GPT-PM's correlated decision on request `dd7175f5-40f3-4714-932d-dc44dca55cc2` / reply
`c064e8f2-eb6d-5945-97e1-f6f6c71d6b92` allows the coordinator direction conditionally but requires
request-provenance approval before implementation. The amendment request
`9fcaec9d-c344-4388-b79a-1392fb6f4cb4` is uncertain; no completed correlated reply was available
when this record was written. Root-owned service configuration/key preparation is conditional on
reviewed configuration/custody. The decision does not authorize service activation or use of
Codex-generated signatures as independent operator attestation.

## Verification state

- Only bounded, read-only PowerShell/WSL metadata and file-hash queries were executed; exact
  commands and outputs are recorded in the evidence file.
- No test, check, build, migration, source installation, key read/generation, configuration write,
  service start/enable, network-policy change, E5 probe, or dispatch was performed.
- The operator's pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains
  untouched.

## Ownership and next steps

Codex owns finishing the trust-boundary amendment, coordinator implementation, and safe WSL
preparation under approved custody. GPT-PM owns architecture adjudication and exact-head review.
The operator is not asked to find a nonexistent external coordinator or send secrets. If fresh E5
requires an independent operator attestation after host controls are evidenced, the operator owns
that attestation; Codex must not sign as the operator. Next: obtain the correlated amendment result,
implement only the approved scope, finish source review, then delegate permitted evidence execution.
Keep restricted scenarios `NOT_RUN`, runtime disabled until separately authorized, and S3 blocked
until S2 closes.
