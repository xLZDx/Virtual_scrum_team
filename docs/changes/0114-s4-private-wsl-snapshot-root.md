# 0114 S4 private WSL snapshot root provisioning

## What changed

- Prepared a separate S4 snapshot destination in the named `Ubuntu-24.04` WSL2 distribution, owned by the unprivileged runner and dedicated worker group with mode `2710`.
- Confirmed the distribution has WSL automount and interop disabled, the worker identity is distinct from the runner, and the observed nftables input/output policies default to drop with loopback allowed.
- Regenerated the document registry after the final S4 functional and local E2E evidence records.

## Why

The operator selected dedicated WSL2 provisioning to enable the sandbox/POSIX acceptance path. S4 source transfer requires a runner-owned private root shared only for worker traversal; the pre-existing protected S2 root was not reused.

## Affected contracts and paths

- Private WSL environment: S4-specific destination root, runner/worker ownership and mode. The exact POSIX path and identity values are intentionally withheld from committed records per `docs/S4_WSL_SNAPSHOT_TRANSFER.md`.
- `governance/DOCUMENT_REGISTRY.md`: generated index now includes the final S4 test records through 0113.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, and `core/LESSONS_LOG.md`: provisioning state and remaining runtime gates.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The already available `Ubuntu-24.04` WSL2 instance was used; no new distribution, package installation, VM, or host firewall change was made.
- The runner account and worker group were observed in the named distribution. Exact values remain only in the local provisioning context, not public repository evidence.
- The observed local nftables ruleset is not a fresh signed sandbox probe or proof of all OS resource limits. The transfer command and signer socket remain separate gates.
- Technical provisioning service owner is `UNKNOWN` in canonical project records.

## Verification state

- Read-only WSL inventory confirmed WSL version 2, automount disabled, interop disabled, distinct `vst-runner`/`vst-worker` identities and a default-drop local input/output ruleset with loopback accepted.
- The S4 destination root was created and its owner/group/mode verified as `2710`; parent traversal was inspected.
- No source transfer, analyzer/QA command, test, build, check, package install, migration, CI, or signer operation was run by Codex.
- Exact-head bundle transfer, cloned HEAD/hash, worker read-only access, report signing and gate acceptance remain `NOT_RUN`.

## Follow-up

1. Have e2e-runner execute the bounded `tools.qa.wsl_snapshot` transfer from the clean committed S4 candidate using private provisioning values.
2. Record exact returned run ID, candidate head, bundle digest/size and permission result without publishing the private POSIX path or identity values.
3. Resolve a distinct authorized S4 signer socket before native report/signature/gate execution; absent that socket, those acceptance items remain `NOT_RUN`.
