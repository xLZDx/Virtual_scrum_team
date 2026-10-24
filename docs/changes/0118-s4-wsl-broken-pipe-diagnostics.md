# 0118 S4 retain bounded WSL receiver diagnostics

## What changed

- On a broken pipe, stop the Git bundle producer, close receiver input, wait briefly for the WSL receiver, and capture its bounded stderr before returning a failure.
- Redact the private snapshot root, runner account, and worker GID from receiver diagnostics.
- Keep timeout and other transport failures fail-closed, and update the S4 backlog, decision/lesson logs, and generated document registry.

## Why

The second bounded transfer on clean HEAD `895d9f6b5cd96a32b94963987d7aca67fe18a9f5` returned only `[Errno 32] Broken pipe`; no receiver diagnostic or run metadata was retained. The failure handler killed the receiver immediately, potentially discarding the reason it closed the stream. Better bounded diagnostics are needed before a new transfer can be evaluated safely.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: broken-pipe cleanup and bounded diagnostic capture.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: transfer status and next action.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for WSL provisioning/transport: `UNKNOWN` in repository records.
- An unidentified partial destination remains untouched. No retry, WSL inspection, cleanup, or deletion is included in this source change.

## Verification state

- The prior broken-pipe result and lack of run metadata are in record 0117 and its linked evidence.
- This code change is implemented but runtime-unverified. No tests or checks were run for it.
- A fresh clean-head transfer is needed to exercise the changed receiver-error path. Without returned run metadata, clone permissions and worker read/write acceptance remain `NOT_RUN`.
- Signer socket, native report, signature, and gate acceptance remain `NOT_RUN`.

## Next steps

1. Commit the bounded diagnostic change and document registry.
2. Have the E2E owner make one fresh transfer attempt on the resulting clean HEAD.
3. If it fails, use only the redacted receiver diagnostic to correct the next code issue; if it succeeds, inspect only the returned run-scoped clone and verify head/digest/mode/read-write boundaries.
4. Resolve signer provisioning separately before native report/signature/gate acceptance.
