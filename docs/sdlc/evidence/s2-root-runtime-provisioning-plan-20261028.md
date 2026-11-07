# S2 root/runtime provisioning plan — preparation only — revised 2026-10-29

## Purpose and limits

This is a non-secret plan for the selected dedicated `Ubuntu-24.04` WSL2 distribution. It records
the minimum proposed identity and filesystem boundary for a later, separately authorized
provisioning action. It does not create accounts/groups, write `/etc/vst-runner`, create/reuse keys,
apply the Store migration, install runtime files, change policy, enable/start services, or dispatch
work. No secret or key material is included.

GPT-PM reviewed the prior revision as MODIFY with two MAJOR and two MINOR findings. The exact
correlation and each correction are recorded in
`s2-provisioning-plan-adjudication-20261029.md`. This revision resolves the owner-primary-GID
overlap in the proposal, adds the owner service/socket contract and field matrix, and remains
pending exact-plan re-review. It is not yet accepted for provisioning.

GPT-PM authorizes preparation of non-secret maps and config templates, but a reviewed exact
provisioning plan and separate execution authorization are required before creating the missing
service account. The signed-instruction architecture is adjudicated; implementation, mapped
synthetic-key tests and source review remain pending. No real trusted instruction issuer/key has
been evidenced. Production config generation and activation remain disabled until source
acceptance, a real authorized issuer, and current runtime evidence are ready.

## Read-only environment evidence

On 2026-10-29 local time, read-only commands against the named distribution reported:

- Existing accounts: `vst-runner` 997:988, `vst-signer` 995:987,
  `vst-supervisor` 994:986, `vst-worker` 999:989, and `vst-reviewer` 993:985.
- No account/group named `vst-dispatcher`, `vst-dispatch-owner`, or
  `vst-supervisor-client` was returned by `getent`.
- A focused read-only rerun on 2026-10-29 used `/usr/bin/getent`; each of these commands returned
  exit code 1 with empty output: `getent passwd vst-dispatcher`, `getent passwd
  vst-dispatch-owner`, `getent group vst-dispatcher`, `getent group vst-dispatch-owner`, `getent
  group vst-supervisor-client`, `getent passwd 980`, `getent passwd 981`, `getent group 982`,
  `getent group 983`, and `getent group 984`. This is an observation only, not a reservation;
  repeat immediately before any separately authorized creation.
- `vst-supervisor.service`, `vst-signer.service`, `vst-runner.service`, and
  `vst-dispatcher.service` reported `inactive`.
- `/etc/vst-runner` and `/run/vst-runner` do not exist. `/var/lib/vst` and
  `/var/lib/vst/keys` are `root:root` mode `0700`.
- `/opt/vst-runtime` is a symlink to
  `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. The target directory is
  `root:root` mode `0755`. The symlink's reported `0777` mode is not the target's permission; no
  chmod or ownership change was made.

The exact focused read-only identity lookups were run separately:

```sh
wsl.exe -d Ubuntu-24.04 -- getent passwd vst-dispatcher
wsl.exe -d Ubuntu-24.04 -- getent passwd vst-dispatch-owner
wsl.exe -d Ubuntu-24.04 -- getent group vst-dispatcher
wsl.exe -d Ubuntu-24.04 -- getent group vst-dispatch-owner
wsl.exe -d Ubuntu-24.04 -- getent group vst-supervisor-client
wsl.exe -d Ubuntu-24.04 -- getent passwd 980
wsl.exe -d Ubuntu-24.04 -- getent passwd 981
wsl.exe -d Ubuntu-24.04 -- getent group 982
wsl.exe -d Ubuntu-24.04 -- getent group 983
wsl.exe -d Ubuntu-24.04 -- getent group 984
```

The exact read-only path command was:

```sh
wsl.exe -d Ubuntu-24.04 -- sh -lc 'stat -c "%U:%G %a %F %n" /etc/vst-runner /run/vst-runner /var/lib/vst /var/lib/vst/keys /opt/vst-runtime /opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976 2>&1 || true'
```

The focused identity command exited 0 and reported the listed users/groups, empty numeric lookups,
and four inactive services. The path command exited 0 and reported the listed missing paths and
owners/modes. An earlier broad command printed harmless shell warnings for its section labels; it
was superseded by the focused reruns above. No key contents were read.

## Proposed identity map (not provisioned)

| Purpose | Proposed identity | Proposed numeric ID | Group membership and boundary |
|---|---|---:|---|
| Shared Supervisor socket access | `vst-supervisor-client` group | GID 984 | Only explicitly approved Supervisor peers; never `vst-worker` |
| Dispatcher service | `vst-dispatcher` user/group | UID 981 / primary GID 983 | Supplementary `vst-supervisor-client`; fixed cgroup `/system.slice/vst-dispatcher.service`; no assignment or signing authority |
| Dispatch-owner service | `vst-dispatch-owner` user and primary group | UID 980 / GID 982 | Supplementary shared socket GID 984; fixed cgroup `/system.slice/vst-dispatch-owner.service`; no dispatcher membership; root Supervisor peer maps principal `Codex` |

The numeric IDs are candidates based on read-only observations, not reservations. Before creation,
repeat numeric and named `getent` checks and stop on any collision or changed identity. Do not
silently allocate replacements; update and re-review this plan first. The dispatch-owner primary
GID is deliberately distinct from shared socket GID 984; the prior proposal that assigned both
roles GID 984 is superseded because it collapsed the identity boundary.

## Proposed socket and service boundaries

- Supervisor socket proposal: `/run/vst-supervisor/supervisor.sock`; parent root-owned,
  `vst-supervisor-client` group, mode `0710`; socket root-owned, same group, mode `0660`.
- Owner ingress is systemd socket-activated at `/run/vst-supervisor/dispatch-owner.sock`, mode
  `0660`, owner root and group `vst-supervisor-client`. It accepts one bounded signed envelope per
  connection and forwards it to the fixed Supervisor socket; it has no queue, spool, retry, task
  selection, signing key, Store path, or runner-socket access. See
  `s2-dispatch-owner-service-contract-20261029.md` for the source contract.
- Runner socket and runtime directory must follow the existing Runner contract and template; their
  owner/group/mode must be derived from the exact accepted root config and verified from live
  service state. Do not copy a guessed value into `/etc`.
- Dispatcher service uses only its fixed unit identity and `AF_UNIX` address family. It consumes
  Supervisor-filtered intents, forwards the exact authorized intent/grant, and does not enumerate
  or select tasks.
- Dispatch-owner peer is pinned by UID, GID, exact unit cgroup, kernel peer credentials, and the
  root-owned Supervisor peer map. A JSON principal or UID is never trusted from request input.
- The owner service fails closed when the pinned public trust registry or a valid signed
  instruction is absent. The production trust registry and real issuer/key remain unavailable.

## Configuration readiness

No complete `/etc/vst-runner` configuration can be generated yet. Required source/runtime digests,
current E5 run identity, genuine probe output, independently authorized egress evidence, and
service-generation/key-custody values are unavailable or not verified for the current source.
Values must come from the exact committed source, accepted configuration schema, and actual
environment; do not insert placeholders or values copied from an older runtime.

Before provisioning, prepare and review a separate configuration bundle covering Supervisor,
Runner, signer, dispatcher, owner service, peer UID/GID/cgroup maps, socket paths/modes, generation
records, manifest digests, key paths/trust roots and ownership. The bundle must contain no private
keys and must explicitly mark unavailable values rather than inventing them. Key generation/reuse,
schema migration application, runtime installation, service activation, real dispatch, and E5
operator attestation remain outside this plan.

## Field-level configuration inventory

`UNAVAILABLE` means the environment does not currently provide a verified value; it is not a
placeholder to install. Source schema references are the loaders in `tools/vst/` at the current
source revision. All files below are prospective root-controlled artifacts, not observed files.

| Component | Exact source fields | Source of truth and expected access | Current availability / validation |
|---|---|---|---|
| Supervisor | `store_path`, `anchor_path`, `event_key_path`, `startup_supervisor_key_path`, `execution_grant_key_id`, `execution_grant_private_key_path`, `execution_grant_trust_keys`, `openssl_path`, `dispatch_instruction_trust_registry_path`, `run_id`, `probe_nonce`, `preflight_record_path`, `probe_key_path`, `operator_key_path`, `execution_grant_audience`, `generation_record_path`, `runner_unit_name`, `runner_control_group`, `runner_lock_path`, `systemctl_path`, `model_provenance`, `socket_path`, `socket_gid`, `peers`, `allow_schema_upgrade` | Exact schema in `load_supervisor_service`; secret key files root-owned `0600`; config root-controlled; socket peers/cgroups from reviewed identity map | `/etc/vst-runner` absent in latest inventory. Paths, keys, run/nonce, signed probe, policy attestation, generation record, model digests, trust registry and IDs are `UNAVAILABLE`; validate exact source schema, signed current probe/policy, ownership/modes, and collision-free peer identities before any authorization. `allow_schema_upgrade=false` unless separately approved. |
| Runner | `socket_path`, `runtime_dir`, `supervisor_socket`, `generation_record_path`, `unit_name`, `socket_gid`, `dispatcher_uid`, `dispatcher_gid`, `dispatcher_cgroup`, `daemon_uid`, `daemon_gid`, `service_cgroup`, `audience`, `runner_id`, `repository_root`, `signer_socket`, `openssl_path`, `grant_trust_keys`, `worker_uid`, `worker_gid`, `worker_exec_helper_head`, `worker_exec_helper_source_sha256`, `worker_exec_helper_binary_sha256`, `worker_exec_helper_path`; optional `max_request_bytes`, `max_response_bytes`, `timeout_sec`, `deadline_sec`, `max_output_bytes` | `RunnerServiceConfig` and helper manifest from exact committed runtime/build; config root-owned/read-only; worker helper root-owned fixed digest | No `/etc/vst-runner/runner-service.json` observed. Current-source head/helper build digest, runtime root, generation and signer/grant key inputs are `UNAVAILABLE`; fixed identities must agree with current reviewed map and helper contract; bounded optional values must satisfy source limits. |
| Signer | `socket_path`, `key_path`, `ledger_path`, `runner_uid`, `runner_gid`, `runner_cgroup`, `grant_trust_keys`, `openssl_path`, `grant_audience`, `supervisor_socket` | `SignerServiceConfig`; private key and replay ledger signer-owned; root-controlled config; runner-only peer | No `/etc/vst-runner/signer-service.json` observed. Private key, ledger, trust ring and current generation are `UNAVAILABLE`; no key creation/reuse is authorized. |
| Dispatcher | `supervisor_socket`, `runner_socket`; optional `idle_poll_sec`, `rpc_timeout_sec` | `DispatcherServiceConfig`; exact Supervisor/Runner socket contracts and dispatcher-only Runner peer | No `/etc/vst-runner/dispatcher-service.json` observed. Runner socket path and peer map are `UNAVAILABLE`; validate fixed AF_UNIX paths, peer IDs/cgroups and timeouts. |
| Dispatch owner | `principal`, `openssl_path`; shared public registry `/etc/vst-runner/dispatch-instruction-trust.json`; fixed Supervisor socket/systemd socket FD; persistent admission fence `/etc/vst-runner/dispatch-owner-admission-blocked.json` | `DispatchOwnerServiceConfig`, exact service/socket templates, root `ExecStopPost` helper and service contract `s2-dispatch-owner-service-contract-20261029.md`; config root-owned, group `vst-dispatch-owner`, mode `0640`; shared registry root-owned mode `0644`; latch root:root mode `0644`; no private key | Neither service config, public registry nor latch exists in the selected WSL inventory. Real trusted key and source issuer are `UNAVAILABLE`; config must bind principal `Codex`, the shared trust-registry path, `/usr/bin/openssl`, and Supervisor socket. On every service termination the helper first synchronously stops the socket and confirms `ActiveState=inactive`, with bounded per-call timeouts and capped retries; only then does it inspect/persist the latch. `TimeoutStopSec=infinity` prevents systemd from killing the helper while admission is unconfirmed. If latch persistence fails after the listener is confirmed inactive, the socket is inactive at that point, but no latch guards a later explicit start and cross-reboot safety is not established; healthy durable root-controlled `/etc` is required before any later start/reboot. Reopening needs exact Store/request-ID reconciliation and separately authorized root recovery. Runtime behavior remains unverified. |
| Identity and sockets | Proposed users/groups above; supervisor socket `/run/vst-supervisor/supervisor.sock`; owner socket `/run/vst-supervisor/dispatch-owner.sock`; dispatcher Runner socket follows accepted Runner config | Fresh numeric/name lookups and exact root-controlled systemd units, peer maps, socket modes and cgroups | Proposed names and UIDs 980/981, GIDs 982/983/984 were absent in the 2026-10-29 read-only lookup only; values are not reserved. `/run/vst-runner` and `/etc/vst-runner` absent; runtime owner socket not present. Recheck all names/IDs immediately before any separately authorized creation. |

Owner service and Supervisor now read one fixed root-owned public registry file. The Supervisor
config schema requires that exact registry path, so no copied key maps need reconciliation. The
registry and all public-key files remain `UNAVAILABLE` and were not created by this plan.

## Ordered prerequisites

1. Codex completes the signed verifier, one-frame owner-service contract, persistent fail-stop
   fence, resolves the distinct owner primary GID and exact systemd socket/service unit, then records
   the exact revised plan.
2. Once all S2 coding is complete, `functional-test-reviewer` authors mapped synthetic-key tests;
   `e2e-runner` executes them. Fresh relevant specialist reviews and exact-head GPT-PM code gate
   follow. Keep production submission closed and M01 open because no real issuer/key is evidenced.
3. Codex binds all config inputs to the final accepted source and current non-secret runtime
   evidence; independently record current E5/probe prerequisites and unavailable fields.
4. GPT-PM reviews the exact non-secret provisioning/configuration plan at its exact revision.
5. The operator separately authorizes privileged account/configuration provisioning and any
   credential or policy actions that truly require that authority. This plan itself is not that
   authorization.
6. After authorized provisioning, the designated test/runtime agents execute only allowed mapped
   scenarios; restricted selectors remain `NOT_RUN`, and genuine E5 evidence is still required.

## Ownership

Codex owns plan/config preparation and evidence collection; GPT-PM owns architecture/config
adjudication; the operator owns any independently required privileged execution, instruction
signer identity authorization/private-key custody, or signed network-policy attestation.
Assignments do not claim that any such action or approval has occurred.
