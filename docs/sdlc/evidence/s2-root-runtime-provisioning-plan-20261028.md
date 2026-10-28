# S2 root/runtime provisioning plan — preparation only — 2026-10-29

## Purpose and limits

This is a non-secret plan for the selected dedicated `Ubuntu-24.04` WSL2 distribution. It records
the minimum proposed identity and filesystem boundary for a later, separately authorized
provisioning action. It does not create accounts/groups, write `/etc/vst-runner`, create/reuse keys,
apply the Store migration, install runtime files, change policy, enable/start services, or dispatch
work. No secret or key material is included.

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
- Numeric `getent` lookups returned no passwd entries for UIDs 980 and 981, and no group entries
  for GIDs 983 and 984. These are free only at the recorded observation time and must be checked
  again immediately before any creation.
- `vst-supervisor.service`, `vst-signer.service`, `vst-runner.service`, and
  `vst-dispatcher.service` reported `inactive`.
- `/etc/vst-runner` and `/run/vst-runner` do not exist. `/var/lib/vst` and
  `/var/lib/vst/keys` are `root:root` mode `0700`.
- `/opt/vst-runtime` is a symlink to
  `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. The target directory is
  `root:root` mode `0755`. The symlink's reported `0777` mode is not the target's permission; no
  chmod or ownership change was made.

The exact read-only identity/unit command was:

```sh
wsl.exe -d Ubuntu-24.04 -- sh -lc 'getent passwd vst-runner vst-signer vst-supervisor vst-worker vst-reviewer vst-dispatcher vst-dispatch-owner; getent group vst-runner vst-signer vst-supervisor vst-worker vst-reviewer vst-dispatcher vst-supervisor-client; getent passwd 980; getent passwd 981; getent group 983; getent group 984; systemctl is-active vst-supervisor.service vst-signer.service vst-runner.service vst-dispatcher.service 2>&1 || true'
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
| Dispatch-owner client | `vst-dispatch-owner` user | UID 980 / primary GID 984 | Fixed cgroup `/system.slice/vst-dispatch-owner.service`; no `vst-dispatcher` membership; principal mapping `Codex` only after accepted source contract |

The numeric IDs are candidates based on one read-only observation, not reservations. Before
creation, repeat numeric and named `getent` checks and stop on any collision or changed identity.
Do not silently allocate replacements; update and re-review this plan first.

## Proposed socket and service boundaries

- Supervisor socket proposal: `/run/vst-supervisor/supervisor.sock`; parent root-owned,
  `vst-supervisor-client` group, mode `0710`; socket root-owned, same group, mode `0660`.
- Runner socket and runtime directory must follow the existing Runner contract and template; their
  owner/group/mode must be derived from the exact accepted root config and verified from live
  service state. Do not copy a guessed value into `/etc`.
- Dispatcher service uses only its fixed unit identity and `AF_UNIX` address family. It consumes
  Supervisor-filtered intents, forwards the exact authorized intent/grant, and does not enumerate
  or select tasks.
- Dispatch-owner peer is pinned by UID, GID, exact unit cgroup, kernel peer credentials, and the
  root-owned Supervisor peer map. A JSON principal or UID is never trusted from request input.
- The owner client fails closed when the pinned trust registry or a valid signed instruction is
  absent. The source verifier is being implemented; no real issuer/key is present.

## Configuration readiness

No complete `/etc/vst-runner` configuration can be generated yet. Required source/runtime digests,
current E5 run identity, genuine probe output, independently authorized egress evidence, and some
service-generation/key-custody values are not verified for the current source. Values must come
from the exact committed source, accepted configuration schema, and actual environment; do not
insert placeholders or values copied from an older runtime.

Before provisioning, prepare and review a separate configuration bundle covering Supervisor,
Runner, signer, dispatcher, peer UID/GID/cgroup maps, socket paths/modes, generation records,
manifest digests, key paths/trust roots and ownership. The bundle must contain no private keys and
must explicitly mark unavailable values rather than inventing them. Key generation/reuse,
schema migration application, runtime installation, service activation, real dispatch, and E5
operator attestation remain outside this plan.

## Ordered prerequisites

1. Codex completes the adjudicated verifier source; the designated test role authors and runs the
   synthetic-key contract cases; fresh specialist reviews and the exact-head GPT-PM gate follow.
   Keep production submission closed and M01 open because no real issuer/key is evidenced.
2. Codex binds all config inputs to the final accepted source and current non-secret runtime
   evidence; independently record current E5/probe prerequisites and unavailable fields.
3. GPT-PM reviews the exact non-secret provisioning/configuration plan at its exact revision.
4. The operator separately authorizes privileged account/configuration provisioning and any
   credential or policy actions that truly require that authority. This plan itself is not that
   authorization.
5. After authorized provisioning, the designated test/runtime agents execute only the allowed
   mapped scenarios; preserve restricted selectors as `NOT_RUN` and require genuine E5 evidence.

## Ownership

Codex owns plan/config preparation and evidence collection; GPT-PM owns architecture/config
adjudication; the operator owns any independently required privileged execution, instruction
signer identity authorization/private-key custody, or signed network-policy attestation.
Assignments do not claim that any such action or approval has occurred.
