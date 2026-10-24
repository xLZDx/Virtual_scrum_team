# 0044 S2 signed network-policy attestation and complete socket inventory

## What

- Made a run/spec/nonce-bound operator-root-signed attestation mandatory at the sandbox supervisor boundary. It records environment identity, SHA-256 digests for the enforced policy and private evidence, an empty external allowlist, no container socket, and no unapproved host paths.
- Kept the runner signature separate. The supervisor verifies the operator signature independently and requires an operator key distinct from the runner probe key. The operator key is not passed to the worker.
- Replaced the fixed UID 1000 Podman socket check with known system endpoints, every numeric `/run/user` and `/var/run/user` runtime directory, and `/proc/net/unix` discovery. Discovery errors fail closed.
- Marked the reserved documentation-address connection as a limited smoke probe; it does not prove egress policy.
- Updated the sandbox specification, operator provisioning guide, and S2 plan with the attestation and evidence contract.

## Why

Security review found that the probe reported `empty_external_allowlist=true` without observing a policy and tested only one reserved IP; the signed runner boolean could therefore represent a false claim. It also found that the container socket scan missed runtime sockets for UIDs other than 1000. The new operator attestation provides explicit evidence and an independently verified trust root; incomplete socket enumeration refuses launch.

## Affected contracts and paths

- `tools/vst/preflight.py`: inventory and attestation schema, operator signing helper, complete socket enumeration, fail-closed verification.
- `tools/vst/signing.py`: operator network-policy domain-separation label.
- `tools/vst/supervisor.py`: mandatory independent operator attestation verification before worker start.
- `docs/SANDBOX_SPEC.md`, `docs/S2_SANDBOX_PROVISIONING_GUIDE.md`, `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`: provisioning and acceptance contract.
- All six trust roots remain pairwise distinct; the operator root is not exposed to the worker/analyzer.

## Decisions

- A failed reserved-target connection is not proof that egress is default-deny. Only operator-signed policy/evidence bound to the exact run, spec and nonce satisfies that acceptance property.
- A missing, malformed, mismatched, or invalidly signed attestation blocks sandbox worker start.
- Failure to enumerate a required socket source blocks sandbox worker start.

## Verification state

- Implemented on baseline HEAD `a20c59e4585b16cb2b758fc2b133e3a27d8a9b17`.
- No tests, checks, builds, CI, migrations, or host runtime probes were run, per task instructions. Runtime proof and test-agent updates remain pending.
- Exact diff/source review is implementation evidence only; it does not establish that any host firewall or sandbox has been provisioned.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation-engineer (`gpt-6-luna`).
- Test author/executor: authorized functional/E2E test agents. Host policy/evidence provider: operator; no named infrastructure service owner is established by repository records.
- Next: update probe and supervisor acceptance tests for missing/invalid operator attestations and non-1000 runtime sockets, then run the authorized suite on the committed head. Provisioning evidence remains `NOT_RUN` until provided by the operator.

Agent-Attribution: implementation-engineer (gpt-6-luna); Codex executor
