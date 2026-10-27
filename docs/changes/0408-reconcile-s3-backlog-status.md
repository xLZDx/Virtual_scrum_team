# Change 0408: align the S3 backlog with accepted G03 design status

## What changed

- Updated VST-028 to distinguish the accepted G03 toolchain/lifecycle/network design from still-unverified exact-pair runtime, artifact provenance and selected dependency closure.
- Preserved operator ownership of legal/acquisition disposition and the prohibition on candidate acquisition/build/runtime work until its separate gates close.
- Regenerated the document registry from the staged index.

## Why

VST-028 said that full G03 compatibility remained open without distinguishing the design findings, which GPT-PM accepted at exact HEAD `77b319367b575b9f4c0a193e91405df507c886e6`, from the exact server/SDK compatibility that remains `NOT_VERIFIED`. The backlog should identify the remaining runtime evidence accurately.

## Affected paths

- `core/BACKLOG.md`
- `governance/DOCUMENT_REGISTRY.md` (generated from staged index)
- `docs/changes/0408-reconcile-s3-backlog-status.md`

## Provenance and review

- Starting HEAD: `4d42210bc07cf784917915fba0f23c8996528abe`, branch `s4-canonical-continuation`.
- The accepted design decision is recorded in correlated GPT-PM request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / reply `14aedf85-c52b-5d64-b84b-40baf9a99455`; no implementation/runtime acceptance is inferred.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.
- No code, project test, build, CI, migration, acquisition, installation, candidate execution, network probe, push, PR, or merge occurred.

## Verification and acceptance

- Regenerate `governance/DOCUMENT_REGISTRY.md` from the staged index and run its `--check`.
- Run the report-format check; no HTML content changes are included.

## Ordered next steps and owners

1. Codex: commit this backlog wording correction and its linked record.
2. Codex: continue permitted read-only S2/S3 evidence only; exact runtime/provenance remains open.
3. Operator: decide legal/acquisition disposition when reached; this wording correction does not make that decision.
