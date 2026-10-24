# 0116 S4 WSL transfer boundary correction

## What changed

- Keep mode 2710 on each transfer run root so cloned descendants inherit the provisioned worker group.
- Launch the WSL receiver with `/` as its explicit initial working directory.
- Update S4 backlog and decision/lesson records with the failed attempt, correction, and remaining runtime acceptance.

## Why

The single bounded transfer at clean HEAD `ea008c9ecfdf93dc689614ace957d6dfb7693627` returned no metadata. WSL reported `chdir(/nonexistent) failed`, and the receiver rejected the source snapshot owner/group. Source inspection identified clearing setgid before cloning as a plausible group mismatch cause. Actual destination state was not inspected, so the exact cause remains unconfirmed.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: WSL launch context and group inheritance on the private per-run root.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: current partial acceptance and follow-up.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for WSL provisioning/transfer boundary: `UNKNOWN` in repository ownership records.
- Preserve mode 2710 on the per-run root; the worker receives traversal only. The clone remains expected to be runner-owned, worker-readable, and not worker-writable.
- No retry, partial-tree inspection, cleanup, package install, signer use, or native test/report run is authorized by this code change.

## Verification state

- The one observed transfer failure is documented in `docs/sdlc/evidence/s4-wsl-transfer-ea008c9.md`.
- This source correction is implemented but runtime-unverified. No tests or checks were run in this change.
- A fresh clean-head transfer must return a run ID, exact candidate HEAD, bundle digest, and byte size before any run-scoped permission probe can be performed.
- Signer socket, native report, signature, and gate acceptance remain `NOT_RUN`.

## Next steps

1. Commit this source correction and generated registry.
2. Have the E2E owner make one bounded transfer attempt on the resulting clean HEAD.
3. If metadata returns, verify exact HEAD/hash/size and worker read access plus write denial for that identified snapshot.
4. Resolve signer provisioning separately before native report/signature/gate acceptance.
