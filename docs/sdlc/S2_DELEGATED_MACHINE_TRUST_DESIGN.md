# S2 delegated machine issuer and E5 trust design

Sprint: Agentic_Framework `39b7cc253f5d`, mapped to the active project sprint S2.
Status: candidate source design; it has not passed independent review or GPT-PM verification, and neither machine signer is active.
Decision source: GPT-PM correlated architecture ruling, request `a3e130f0-9aec-4304-b001-388a45c0be55`, reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`; full record: `docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`.

**Active assignment-provenance design:** the later GPT-PM ruling `MODIFY — ALTERNATIVE ACCEPTED
IN PRINCIPLE` (request `4b2e7e61-c0bd-407d-9b2c-b9078da5f7d9`) retires the candidate external
per-task operator-signed record. Use `docs/sdlc/S2_AUTHENTICATED_ASSIGNMENT_BASIS_DESIGN.md` for
the selected Store-backed provenance and bounded read-only `assignment_basis` API. The older
external-record schema and its disconnected validator below are retained as candidate-history;
they are not an active Supervisor contract. The upstream writer and production issuer remain
unimplemented and must not be claimed as accepted.

**Root dispatch issuer supersession (bounded):** for the dispatch-issuance choice and crash-state
contract only, the later GPT-PM ruling `MODIFY` (request
`8b6b69f3-9b39-491b-a948-03c497870b5d`, reply
`b1728c67-3bc2-4db5-9fbf-6b359a73ad82`) prefers the existing root Supervisor and unchanged
signed v1 instruction format. Use
[`S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md`](S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md) for the
corrected append-only crash-consistent issuance protocol and explicit delegated-key enforcement.
This supersedes the separate issuer daemon/v2 dispatch-format proposal below only. It does not
supersede the selected authenticated assignment-basis design, authorize private-key signing,
provisioning or activation, close `S2-MACHINE-ISSUER-I01`, or change the existing human E5
contract. The daemon/v2 material below is retained as historical candidate context, not the active
dispatch design.

## Decision and boundary

This candidate proposes two separately versioned, purpose-bound machine contracts: one for issuance of an already-authorized S2 assignment and one for collecting E5 host-policy observations. The operator remains the sole human delegation authority. The repository has no established operator assignment-delegation signing purpose or trust configuration for this contract. A policy could become effective only after a new, purpose-separated operator authority key and root-owned trust configuration are explicitly provisioned and the operator signs its canonical bytes. Codex may author the candidate and compute its digest, but may not sign it, claim the operator approved it, or provision a key. The signed delegation states machine identity, exact role, scope, policy digest, validity, and revocation identity.

The issuer receives one immutable authorization record and returns one instruction for that record. It cannot enumerate tasks, accept a task ID as proof of authorization, create or change a Store assignment/lease, or choose among work. The root Supervisor still verifies the signed instruction and performs all existing Store admission checks. The two keys and trust purposes are distinct. E5 v1 remains authoritative until an explicitly approved new policy version is installed and selected; there is no implicit fallback.

This candidate proposes remediation for the two architectural findings in the GPT-PM ruling; both findings remain MAJOR/OPEN pending independent review and GPT-PM verification. GPT-PM's reply labels the gate “MODIFY” and separately scopes its ruling to design only; it authorizes bounded source design, deterministic read-only collectors and synthetic verifiers only. It does not approve privileged signer implementation, key creation, provisioning, activation, production dispatch, replacement of the current human E5 contract, or S2 closure. The reply reports no live-host inspection, key creation, test execution or runtime evidence.

## Existing contracts to preserve

- `tools/vst/dispatch_instruction.py:13-19,25-64` defines an exact v1 envelope and signing domain. It binds request ID, task, slot, attempt, epoch, run, key purpose and expiry, but has no assignment-provenance field. Lines 67-95 verify the key's configured principal/purpose, expiry and Ed25519 signature.
- `tools/vst/preflight.py:133-208` collects POSIX/WSL inventory and binds run ID, nonce and sandbox-spec digest. Lines 182 and 203 explicitly limit external-egress evidence to one reserved-target smoke test. Lines 220-230 sign the existing network-policy attestation with the operator key; lines 265-281 require that operator signature.
- `tools/vst/store.py:1102-1210` validates a v1 instruction and transactionally checks request idempotency, task manifest/slot, live owner epoch, current lease, consumed preflight, eligible attempt and receipt absence before recording `DISPATCH_INTENT_ACCEPTED`. The stored result binds the lease and manifest digest. This is admission after instruction receipt; it does not, by itself, authenticate the issuer's upstream choice.
- Store's event chain and supervisor operation journal are existing durable boundaries, but no signed operator assignment-authorization record or corresponding trust purpose exists today. This candidate therefore defines a new immutable external authorization signed with a new purpose-separated operator authority key. The root Supervisor verifies that record against a read-only current Store assignment snapshot and stores the issued envelope in its existing durable journal. It must not query/list tasks or receive a Store handle capable of assignment/lease mutation.
- The preflight functions and v1 verifier remain unchanged while the new version is developed and reviewed. The Supervisor selects a format and trust purpose explicitly.

## Trust objects

All JSON objects below use the repository's canonical JSON encoding, reject duplicate/unknown/missing fields, validate exact types and digest formats, and are signed over a fixed domain label plus canonical bytes without the signature field. No object contains private-key bytes.

### Operator delegation policy

Use a new exact schema, `VST_S2_MACHINE_DELEGATION_POLICY_V1`. Its signature purpose is `VST_S2_MACHINE_DELEGATION_POLICY_V1`, trusted only through a new root-owned config path `/etc/vst-runner/machine-delegation-trust.json`. Candidate trust-config schema is `VST_S2_MACHINE_DELEGATION_TRUST_CONFIG_V1`: exact fields `schema`, `operator_authorities`, `machine_principals`, `revocations`. Each operator authority has exactly `key_id`, `purpose`, `public_key_path`, `revocation_id`; purpose is `VST_S2_MACHINE_DELEGATION_POLICY_V1` or `VST_S2_ASSIGNMENT_AUTHORIZATION_V1` and uses a distinct key ID/key. Each machine entry has exactly `principal`, `key_id`, `purpose`, `public_key_path`, `policy_sha256`, `not_before`, `expires_at`, `revocation_id`. Revocations are exact `revocation_id`, `revoked_at`, `reason_code` records. Key revocation is represented by the registry entry's explicit `revocation_id`; no caller-selected revocation lookup is trusted. The verifier rejects duplicate IDs, unknown fields, duplicate keys, paths not root-owned and non-regular, symlinked or group/world-writable files, wrong purpose/key-ID combinations, expired or revoked keys. No such signing purpose/config is currently present; this is a candidate path and contract only.

```json
{
  "schema": "VST_S2_MACHINE_DELEGATION_POLICY_V1",
  "policy_id": "stable-policy-id",
  "operator_key_id": "new-policy-authority-key-id",
  "project": "Virtual_scrum_team",
  "repository": "https://github.com/xLZDx/Virtual_scrum_team",
  "sprint_id": "39b7cc253f5d",
  "role": "dispatch-issuer",
  "machine_principal": "root-configured-principal",
  "machine_key_id": "purpose-specific-key-id",
  "key_purpose": "VST_S2_DELEGATED_DISPATCH_ISSUER_V1",
  "source_head": "40-lowercase-hex",
  "manifest_sha256": "64-lowercase-hex",
  "allowed_authorization_type": "VST_S2_ASSIGNMENT_AUTHORIZATION_V1",
  "not_before": "canonical UTC",
  "expires_at": "canonical UTC",
  "revocation_id": "stable-revocation-id",
  "signature": "operator signature"
}
```

The E5 policy uses the same common fields but has role `network-observer`, a different machine key purpose, and an exact `role_config` with `collector_artifacts`, `evaluator_sha256`, `policy_revision_sha256`, `required_observation_schema`, `environment_id`, and `freshness_seconds`. Each collector artifact entry has exactly `source_id`, `path`, `source_head`, `sha256`, `os_id`, `os_build_constraint`, and `privilege_boundary`. This candidate currently allows only observation-completeness evaluation, not a production network policy verdict. A policy for one role cannot authorize the other. The trust config pins each operator public key by key ID and one of the exact operator purposes above, and maps each machine key ID to one principal and one purpose; revocation/expiry are checked on every verification. Runtime trust/config paths remain root-owned. No permissive default, wildcard repository, caller-selected key, automatic key generation or acceptance of unsigned candidate policy is allowed.

The policy's signed `manifest_sha256` freezes the non-secret sprint scope. The manifest identifies exact allowed story/requirement work and source artifacts. It does not make any task assigned. Assignment still has to exist independently in the authenticated assignment record below.

### Immutable external assignment authorization

Schema clarification for bounded validator implementation: add `authorization_key_id` to the
exact assignment field set below for the new operator signing key. `issuer_key_id` remains the
intended delegated machine issuer and must match the policy; it is not the operator key.
Policy `operator_key_id` selects only the purpose-pinned operator delegation key. Each trust key
has an explicit revocation ID; verification checks that ID and each record's revocation ID
against the configured revocation records. For the observation role,
`freshness_seconds` is an exact integer in 1..3600 (booleans rejected). These clarifications grant
no production authority; the validator change record specifies the executable exact schema.

The existing candidate `VST_S2_ASSIGNMENT_AUTHORIZATION_V1` field set is `schema`, `authorization_id`, `project`, `repository`, `sprint_id`, `manifest_sha256`, `task_id`, `story_id`, `principal`, `slot`, `attempt`, `epoch`, `lease_id`, `run_id`, `request_id`, `policy_id`, `policy_sha256`, `authorization_key_id`, `issuer_key_id`, `issuer_key_purpose`, `issued_at`, `expires_at`, `revocation_id`, and `signature`. It does not contain the authenticated Store operation identity and therefore MUST NOT authorize machine dispatch issuance. Do not add fields to V1 or reinterpret its signature.

The proposed issuance contract is a separately signed `VST_S2_ASSIGNMENT_AUTHORIZATION_V2` with signature purpose `VST_S2_ASSIGNMENT_AUTHORIZATION_V2`. Its exact fields are `schema`, `authorization_id`, `assignment_operation_id`, `project`, `repository`, `sprint_id`, `source_head`, `manifest_sha256`, `project_id`, `phase`, `task_manifest_sha256`, `task_id`, `story_id`, `principal`, `slot`, `attempt`, `epoch`, `lease_id`, `runner_id`, `run_id`, `service_generation`, `probe_sha256`, `request_id`, `assignment_policy_id`, `assignment_policy_sha256`, `delegation_policy_id`, `delegation_policy_sha256`, `authorization_key_id`, `issuer_key_id`, `issuer_key_purpose`, `issued_at`, `expires_at`, `revocation_id`, and `signature`. `assignment_operation_id` is the existing canonical Store assignment key; the signature covers it and the complete immutable tuple. No V2 key, policy, trust configuration, or authorization record currently exists.

The exact `VST_S2_MACHINE_DELEGATION_POLICY_V2` schema uses signature purpose `VST_S2_MACHINE_DELEGATION_POLICY_V2` and exactly these fields: `schema`, `operator_key_id`, `policy_id`, `project`, `repository`, `sprint_id`, `role`, `machine_principal`, `machine_key_id`, `key_purpose`, `source_head`, `manifest_sha256`, `allowed_authorization_type`, `not_before`, `expires_at`, `revocation_id`, and `signature`. Values are fixed to role `dispatch-issuer`, authorization type `VST_S2_ASSIGNMENT_AUTHORIZATION_V2`, and key purpose `VST_S2_DELEGATED_DISPATCH_ISSUER_V2`; scope is one project/repository/sprint/source/manifest and a bounded validity interval. The policy digest is SHA-256 over its canonical signed bytes.

The exact `VST_S2_MACHINE_DELEGATION_TRUST_CONFIG_V2` schema has fields `schema`, `operator_authorities`, `machine_principals`, and `revocations`. Operator authority records have exactly `key_id`, `purpose`, `public_key_path`, `revocation_id`; only the V2 policy and V2 assignment-authorization purposes are allowed, with distinct unique key IDs. Machine principal records have exactly `principal`, `key_id`, `purpose`, `public_key_path`, `policy_sha256`, `not_before`, `expires_at`, and `revocation_id`; only `VST_S2_DELEGATED_DISPATCH_ISSUER_V2` is allowed. Revocation records have exactly `revocation_id`, `revoked_at`, `reason_code`, with unique IDs. Verification rejects V1 trust schemas/purposes, cross-version records, duplicate identities, unknown fields, unsafe key files, wrong purpose, expired keys, and revoked IDs. No V2 authority or key material is provisioned.

Before any V2 issuance reservation or irreversible `STARTED` signer claim, the root Supervisor must bind this trusted machine principal to the actual configured dispatch signer: the V2 policy `machine_key_id` and trust principal `key_id` must equal the root `root_dispatch_issuer.key_id`; the trusted principal's public-key file identity/fingerprint must equal the configured dispatch public key identity/fingerprint; and the configured private key must be the matching pair. The V2 trust role purpose is not a substitute for the V1 dispatch-instruction signing purpose; the policy explicitly authorizes that one mapping. A missing or mismatched key ID, purpose, public-key fingerprint, or private/public pair fails before reservation/signing. No alternate signer is accepted.

The signed record is external to the Store; do not claim that it is an existing signed Store event. The V2 request has exactly `schema` and `authorization_id`; the authorization ID itself is the idempotency identity. The root Supervisor obtains exactly one immutable record from a root-controlled provider using that ID, verifies the V2 policy and authorization signatures, derives `assignment_operation_id` only from the verified record, and obtains the current Store assignment snapshot internally. It compares every field (including source, manifest, task/story, principal, slot, attempt, epoch, lease, run and policy) before allowing issuance. Caller-supplied operation IDs, task selectors, Store snapshots, policies, trust records and expiry values are forbidden. The external provider must reject absent, multiple, mutable, stale, expired, revoked or conflicting authorization records; it must not enumerate work or create assignments.

- authorization ID and digest, project, repository, sprint, manifest digest and task/story identity;
- principal `Codex`, slot, attempt, epoch, lease identity, run ID, request ID and bounded expiry;
- the operator authorization identity, policy ID/digest, issuer key purpose, issue-once idempotency key and revocation reference.

The authorization must name exactly one project/repository/sprint/manifest/task/story/slot/attempt/epoch/lease/run/request and Codex principal, with canonical issue and expiry times. The Supervisor obtains the record by its authorization ID, verifies its operator signature under the new purpose and checks it against the current Store snapshot, including current assignment to Codex, live owner epoch, matching live lease, manifest digest, eligible attempt, run-bound consumed probe and absence of an existing receipt. The Store snapshot alone is not the authorization; the signed external record supplies the independent exact-work authorization. The machine caller cannot enumerate records or supply an alternate tuple. Missing, multiple, mutable, stale, expired, revoked, wrong-principal, unassigned, mismatched or unresolved records fail closed. This does not add a scheduler or assignment database.

The V2 authorization is retained and hash-bound in the separately versioned durable V2 issuance journal. The unchanged V1 dispatch envelope does not claim to carry or prove the V2 authorization; root verification of the journal and fresh Store admission remain required at downstream acceptance.

### Dispatch instruction compatibility and downstream admission boundary

Keep the existing `VST_S2_DISPATCH_INSTRUCTION_V1` fields, signature domain, validator and owner relay unchanged. Do not introduce a V2 dispatch instruction. The root admission method is intentionally changed: before accepting a V1 envelope, `Supervisor.accept_dispatch_intent` must resolve its exact canonical bytes to exactly one durably completed V2 issuance-journal record through `Store.dispatch_issuance_for_envelope`. That V2 record carries the signed authorization and its digest, policy identity, authenticated issuer peer, complete Store tuple and current root-verification result. The Store reducer verifies the V2 authorization/policy signatures and digest; Supervisor rechecks current trust/revocation/expiry, run, generation, owner, lease, configured signer-key binding and Store admission before acceptance. A valid V1 signature alone is insufficient for a new dispatch admission.

Legacy V1 issuance records remain readable for audit but cannot authorize a new dispatch acceptance through this route. The V1 issuance RPC that accepts a caller-selected operation ID must be disabled when the V2 path is introduced; there is no fallback. Previously accepted durable dispatch records remain historical records and are not rewritten. The signed V2 assignment authorization is checked at issuance and retained in the separately versioned V2 journal. Any future V2 wire envelope requires a separate design and downstream compatibility review.

The issuer derives every V1 envelope field from the verified immutable V2 authorization and current Store snapshot. It never accepts a free-form task/slot/attempt/epoch/run/expiry, caller-provided operation ID, Store snapshot or client-provided policy digest. The request is authenticated over the fixed AF_UNIX endpoint with kernel peer credentials and the approved UID/GID/cgroup mapping. The request contains only the V2 schema selector and authorization ID.

Use the existing append-only Store/Supervisor operation journal for issue-once durability, with a new explicit V2 intent/event schema and reducer while retaining V1 readers unchanged. The operation key is a domain-separated hash of policy digest plus assignment-authorization digest; the operation payload digest covers the exact canonical authorization, current Store tuple and authenticated caller identity. State transitions are `ABSENT -> RESERVED -> STARTED -> COMPLETED` or `ABSENT -> RESERVED -> STARTED -> UNKNOWN`. `RESERVED` is committed before signer entry. A single `STARTED` transition claims the only signing attempt. The completed envelope and its identity are persisted atomically. If signing or completion persistence has an ambiguous outcome, state is `UNKNOWN`; no later call may sign again. Only an exact, durably completed record can be replayed, byte-for-byte. Changed payload under an existing key, missing/conflicting history, or a second signer claim fails closed. Existing stores with V1 issuance records remain readable and are never rewritten or migrated by this source change.

An exact completed historical envelope is not fresh execution authority. Before replay can be accepted for execution, current trust/revocation, expiry, run, generation, lease, owner and Store admission checks must still pass. If any are stale, revoked, expired or unavailable, the operation may expose its immutable historical record for audit but cannot produce a currently admissible dispatch or authorize Runner execution. No replay may recreate a lease, extend expiry, change request ID or transition an unresolved `STARTED/UNKNOWN` record back to signable.

The future privileged root issuance path must verify the operator assignment signature and delegation policy signature, both key purpose/revocation/expiry checks, exact source/manifest/policy bindings and current Store admission before the existing transaction and checks in `Store.accept_dispatch_intent`. The V2 signed assignment authorization is a distinct selector from V1; invalid or unknown authorization versions are rejected, and V1 is never silently reinterpreted as delegated machine authorization. The current source task implements validators and a root-only read-only comparison method only; it does not enable an issuance route.

### E5 observation-only candidate

The authorized source scope supports only an observation collector. It must emit `VST_S2_MACHINE_NETWORK_OBSERVATION_BUNDLE_V1` and must never emit PASS or sign `VST_S2_DELEGATED_MACHINE_NETWORK_POLICY_ATTESTATION_V1`. Full E5 remains UNKNOWN until GPT-PM accepts an exact policy revision, complete source coverage and evaluator predicates. Any later machine attestation uses a new trust purpose `VST_S2_DELEGATED_MACHINE_NETWORK_POLICY_ATTESTATION_V1`, different from both the new delegation authority and dispatch issuer; its key/config are not provisioned.

Candidate source schemas are exact and reject unknown/missing fields. They are schema proposals, not deployed or trusted records:

`VST_S2_MACHINE_NETWORK_OBSERVATION_BUNDLE_V1` contains exactly `schema`, `run_id`, `nonce`, `source_head`, `sandbox_spec_sha256`, `started_at_utc`, `finished_at_utc`, `sources`, `raw_observations`, and `bundle_sha256`. There is no `policy_revision_sha256` or E5 verdict in this observation-only bundle. Each source receipt contains exactly `schema` (= `VST_S2_MACHINE_OBSERVATION_RECEIPT_V1`), `source_id`, `collector_path`, `collector_head`, `collector_sha256`, `os_id`, `os_build`, `principal`, `privilege_boundary`, `observation_schema`, `collected_at_utc`, `raw_sha256`, and `signature`. Receipt signature purpose is `VST_S2_MACHINE_OBSERVATION_RECEIPT_V1`; collector public keys and trust config are not present, so current source collection may emit unsigned receipts only and cannot claim an authenticated measurement. Source IDs are exactly `windows-host` and `wsl-guest`; both are required. Digests are lowercase 64-hex; timestamps canonical UTC; nonce is 32 lowercase hex. Bundle hash is SHA-256 over canonical bundle bytes without `bundle_sha256`.

Windows raw observation object exact fields: `os_id`, `os_build`, `firewall_profiles`, `effective_firewall_rules`, `wsl_hyperv_firewall_profiles`, `effective_wsl_hyperv_firewall_rules`, `wsl_distributions`, `wsl_network_configuration`, `host_endpoints`, `host_path_exposures`, `collection_complete`, `errors`, `raw_command_outputs`. Each Windows profile has `name` (Domain/Private/Public), `enabled`, `default_inbound_action`, `default_outbound_action`, `policy_source`. Each normalized effective rule has `rule_id`, `enabled`, `direction`, `action`, `protocol`, `local_addresses`, `remote_addresses`, `local_ports`, `remote_ports`, `profiles`, `policy_source`; preserve the complete effective set, not just enabled/block rules. WSL/Hyper-V policy has the same profile and rule shapes plus `environment_id` and complete-source markers. WSL distribution entries include exact name/version/state/network mode. Endpoint entries include address, protocol, port, owning process identity and exposure/interface. Error arrays retain command, exit status and parse/completeness error; no omitted rule may be treated as blocked. If the active Windows build/network mode does not expose a complete effective WSL/Hyper-V policy, collection status is UNSUPPORTED.

WSL raw observation object exact fields: `os_id`, `os_build`, `kernel_release`, `nft_ruleset_raw`, `ipv4_routes_raw`, `ipv6_routes_raw`, `ipv4_rules_raw`, `ipv6_rules_raw`, `namespaces_raw`, `interfaces_raw`, `mounts_raw`, `windows_drive_mounts`, `wsl_interop_present`, `wsl_interop_enabled`, `container_socket_paths`, `container_socket_inventory_complete`, `listeners_raw`, `uid`, `gid`, `collection_complete`, `errors`. These raw string fields retain full command/proc output. Hash the canonical raw object before evaluation. The existing `preflight.py` reserved-target egress smoke probe can be recorded as a probe observation only; it cannot stand in for Windows effective firewall, WSL/Hyper-V firewall, nftables or routing tables or prove comprehensive egress blocking.

Windows host collection and WSL collection are separate named source artifacts with pinned path, source HEAD, digest, OS/build and privilege identity. They run read-only. A missing source, permission error, truncated output, unparsed rule, unsupported OS/build/network mode, unmatched firewall/WSL endpoint, incomplete inventory or inconsistent host/guest observation yields UNKNOWN. Do not coerce UNKNOWN to false/true or PASS.

A later deterministic completeness evaluator is a separate pinned artifact and accepts only the exact observation bundle schema. Its result schema is `VST_S2_MACHINE_NETWORK_EVALUATION_V1`: `schema`, `bundle_sha256`, `evaluator_sha256`, `status` (only `OBSERVATIONS_COMPLETE`, `UNKNOWN`, `INCOMPLETE`, or `UNSUPPORTED`; never PASS), `predicates`, `missing_sources`, `unmatched_rules`, and `result_sha256`. Each predicate has `id`, `status` and evidence references `source_id` plus `raw_field_path`. Deterministic predicates are limited to: both exact source IDs present once; source and observation schemas recognized; required fields present with exact types; raw hashes match canonical contents; collector metadata matches pinned source identity when trust config later exists; all required commands completed; firewall profiles and all effective rules captured; nftables ruleset and v4/v6 routes/rules captured; namespace/interface/mount/interop/socket/listener scans complete; Windows WSL distribution/network records correlate with the WSL guest; timestamps ordered and within configured freshness bound; run/nonce/spec/source bindings match. Any missing, unknown, unsupported, incomplete, unmatched or contradictory input returns UNKNOWN/INCOMPLETE/UNSUPPORTED. `OBSERVATIONS_COMPLETE` means only that collection met this schema; it is not a policy result, proof of blocked egress, or E5 PASS. No production E5 policy predicate set is approved. A later attestor, only after separate design approval, would verify authenticated source receipts, recompute hashes/evaluation, check freshness and nonce replay, and sign exactly the accepted policy result; it may not populate observations, choose an evaluator, or assert a favorable boolean.

No Supervisor path accepts this observation bundle as E5. A future machine-attestation verifier may be added only when a separately reviewed policy fixes the complete required source and predicate set. It must explicitly select the new record version, verify source identities, raw/evaluator hashes, freshness, run/nonce/source/spec/policy bindings, policy validity/revocation and every required observation. Unknown or contradictory input fails closed; it cannot fall back to operator-E5 v1 or accept a machine key in the operator-key slot. Until the contract is reviewed and activated, current human E5 v1 remains mandatory.

### Threat boundary

This design detects caller forgery, stale/replayed records, substituted artifacts, incomplete collection and untrusted worker input. It does not claim that two UIDs or two processes on one WSL host are independent from a compromised Windows administrator, WSL root, kernel or hypervisor. Such an actor can alter collectors, files or observations before signing. The current authorized scope supports source contracts and read-only host measurements; it does not provide hardware-backed remote attestation. Production claims must state this platform limit. If the accepted policy requires resistance to a compromised host administrator, the design is insufficient and no machine E5 may be accepted.

## Source work allowed now

1. Add pure schema/canonicalization/digest validators for the candidate V2 delegation policy, external assignment authorization and observation bundle/evaluation. Keep the V1 dispatch-envelope wire format unchanged; do not create a V2 envelope in this contract. Add verification helpers against caller-supplied public-key fixtures; do not create/provision authority keys or treat fixtures as production trust.
2. Add Supervisor comparison of one externally signed authorization to one read-only current Store assignment snapshot. Do not invent a signed Store assignment event/table that currently does not exist. A separately versioned V2 issuance journal entry is required to bind the V1 envelope to that verified authorization; its reducer and root downstream gate must reject unbound V1 records. Before reservation or STARTED, bind the V2 machine principal's key ID, purpose and public-key fingerprint to the exact root-configured V1 dispatch signer and verify the private/public pair. No privileged issuance or production activation until the revised design and exact source are separately reviewed and provisioned.
3. Add read-only Windows and WSL observation collectors with the exact source fields above. Their result is an observation bundle only. Keep the current POSIX probe API and human E5 verifier unchanged.
4. Add deterministic completeness and consistency evaluation that returns only OBSERVATIONS_COMPLETE, UNKNOWN, INCOMPLETE or UNSUPPORTED. It must not return FAIL/PASS as an E5 policy verdict until an exact egress/policy predicate set and its sources are separately accepted. The current one-target egress smoke result never produces comprehensive E5 PASS.
5. Do not add an attestor or Supervisor machine-E5 acceptance path yet. Do not change service units, create configs/keys/users, write to WSL, initialize/migrate Store, activate services, dispatch work or claim production authority.

## Negative-test matrix for the later test phase

Tests are planned only; the designated functional-test reviewer/e2e runner author and execute them after all S2 coding is complete.

| Boundary | Negative case | Required outcome |
|---|---|---|
| Delegation | unsigned, bad signature, wrong operator key purpose, wildcard scope, wrong sprint/repository/manifest, expired or revoked policy | reject before issuer work |
| Assignment | arbitrary task ID; no authorization ID; task outside signed manifest; assignment for another principal; altered tuple; task merely eligible but not assigned | reject, with no envelope or Store mutation |
| Caller | wrong UID/GID/cgroup, non-PID1 peer where PID1 is required, inherited/invalid peer descriptor, alternate socket/path | reject before authorization lookup |
| Freshness | expired authorization, stale epoch/lease, changed generation, replayed nonce/request, stale source/spec/policy digest | reject and preserve prior durable state |
| Idempotency | same request replay; same operation key with changed payload; uncertain Store commit; corrupted issuance journal | identical bytes for a known committed retry; otherwise unresolved/fail closed, never mint new authority |
| V2 binding | modify task/slot/attempt/epoch/run/lease/principal/manifest/authorization digest; v1/v2 downgrade, purpose mismatch or unknown version | signature/provenance failure, no fallback |
| E5 collector | missing source, permission error, partial firewall/mount/socket inventory, malformed output, unsupported OS/build, conflicting Windows/WSL facts | UNKNOWN/INCOMPLETE/UNSUPPORTED; no attestation |
| E5 integrity | changed raw evidence, evaluator output, collector or evaluator digest; substituted collector receipt | reject |
| E5 freshness | wrong run, nonce, source/spec/policy digest; expired record; replayed nonce; revoked delegation | reject |
| E5 authority | source attempts to produce E5 PASS, evaluator inputs self-asserted, operator key supplied as machine key or vice versa | UNKNOWN/reject; no attestation, human and machine formats stay distinct |
| Platform limit | source input attempts to represent Windows administrator, WSL root, kernel or hypervisor compromise as independently measured | result must state UNSUPPORTED, not PASS |

## Ordered implementation and review

1. Independent architecture/security review assesses this candidate and the issuer/downstream MAJOR findings together; GPT-PM then verifies the exact revised design. Findings stay OPEN until that occurs.
2. Implement only pure validators, signed-external-authorization comparison against Store snapshot, and read-only observation collectors that cannot report E5 PASS.
3. Finish all S2 coding before the functional-test reviewer and e2e runner author/run the mapped negative tests and permitted source tests.
4. Obtain focused security/architecture review, remediate valid BLOCKER/MAJOR findings, and repeat only direct regressions.
5. Only after separate review and explicit provisioning of new purpose-specific operator authority/trust configuration can policy signing be considered. Machine E5 remains unavailable until its complete policy predicates and independent source trust are reviewed. Exact-head approval and mapped runtime evidence remain required for S2; restricted process-kill/crash/mutation/policy selectors remain NOT_RUN.
