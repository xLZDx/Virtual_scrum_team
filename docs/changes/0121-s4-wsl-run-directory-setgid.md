# 0121 S4 create run directory with inherited setgid mode

## What changed

- Set the receiver umask before creating a run directory.
- Request mode 2710 during `mkdir` under the validated setgid snapshot root, then verify owner, group, and mode without a post-creation chmod.
- Update S4 backlog, decision/lesson logs, and generated document registry.

## Why

The bounded transfer at clean HEAD `3ba2f35b724da8f2ea5429d781710bbed6612af3` returned `snapshot run directory did not receive mode 2710` and no run metadata. Source inspection found that the receiver attempted to set SGID with `chmod` after creating a directory. An unprivileged owner outside the worker group may have that bit cleared. This cause is plausible but was not observed directly; the run directory was not inspected after the transfer returned.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: run-directory creation mode and inherited group boundary.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: exact attempt state and next action.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for WSL provisioning/transfer: `UNKNOWN` in repository records.
- Do not inspect, clean, or delete an unidentified partial run. A fresh bounded attempt must return its run ID before any run-scoped permission probe.

## Verification state

- The exact mode-check failure and no-metadata boundary are in record 0119 and linked evidence.
- Source correction is implemented but runtime-unverified. No tests or checks were run for this change.
- Worker read/write boundary, native pytest/report, signer receipt, and gate acceptance remain `NOT_RUN`.

## Next steps

1. Commit the mode-at-creation correction and document registry.
2. Have the E2E owner make one bounded transfer attempt on the resulting clean HEAD.
3. On success, verify exact head/digest/size and read-only worker permissions for that returned run only.
4. Resolve signer provisioning separately before native report/signature/gate acceptance.
