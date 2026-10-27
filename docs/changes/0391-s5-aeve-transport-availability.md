# Change 0391: record S5 AEVE transport availability

## What changed

- Recorded that no AEVE MCP tool is present in the host tool registry and the `aeve` CLI is unavailable.
- Classified the S5 routing attempt as `NOT_COVERED: AEVE_PROFILE_TRANSPORT_UNAVAILABLE` under the `aeve-router` contract.
- Updated the S5 backlog and current state without inspecting another repository.

## Why

The current S5 task requires AEVE provenance/interface evidence, but the skill's permitted MCP/CLI transport paths are absent and the canonical repository inventory contains no AEVE source.

## Affected paths

- `docs/sdlc/evidence/s5-aeve-in-scope-source-inventory-20261026.md`
- `core/BACKLOG.md`
- `core/STATE.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- `ALL_TOOLS` contained no AEVE MCP tools.
- `Get-Command aeve -ErrorAction SilentlyContinue` returned no command.
- No external checkout was searched, no AEVE profile was claimed retrieved, and no source was read.
- S5 runtime remains `NOT_RUN`; S2/S4 gates remain open.

## Decision

Do not bypass the documented AEVE router or search sibling repositories for a fallback. Resume only when the host exposes AEVE transport or the operator makes a specific source in-scope.
