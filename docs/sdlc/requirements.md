# S2 Requirements Reconciliation

Sprint: 39b7cc253f5d — active project sprint: S2

The Agentic_Framework phase-1 record is attached to the already active S2. It does not create a new product sprint or authorize starting S3. This document consolidates the existing S2 scope and acceptance state; it does not add product scope or reopen the accepted architecture.

## Context and goal

S2 delivers a bounded, authenticated path for dispatching work that has already been assigned by the existing Store, and establishes the evidence needed to qualify its runner boundary. The Store remains the sole task, assignment, and lease authority. The accepted coordinator path is the existing `DispatchOwnerService`, authenticated Supervisor/Store admission, Store-filtered Pub/Sub, and `StoreBackedDispatcher`. No external coordinator, second scheduler, or assignment authority is required. [S1: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”.]

## Scope

**In scope:** source-level signed-instruction verification and owner relay for already-authorized work; fail-closed admission and outcome handling; bounded runtime configuration/evidence under the recorded authorization; truthful S2 acceptance and exact-head review.

**Out of scope:** granting production signing authority, provisioning production issuer/attestor keys, activating production dispatch or E5, migrating an existing Store, running restricted process-kill, crash/recovery, mutation, E8, or policy selectors, or starting S3 before S2 closes. Bounded source preparation for an explicitly machine-labelled delegation contract, pure validators, and read-only measurement collectors is authorized within S2 under the GPT-PM adjudication below. Preparation does not itself authorize signing, replace active E5 verification, or permit activation.

## Requirements

### Machine-delegation adjudication amendment (2026-10-29)

GPT-PM returned `MODIFY` for request `a3e130f0-9aec-4304-b001-388a45c0be55`,
correlated reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`. The exact harvested response is
preserved in `evidence/s2-machine-authority-adjudication-20261029.md`. Machine issuance and
machine E5 are permissible in principle. Codex owns preparing the explicit delegation policy,
assignment-provenance contract, independent measurement topology, versioned schemas and bounded
pure validators/read-only collectors; GPT-PM owns adjudicating the two reported MAJOR findings.
Private-key-bearing production signing services, production signing-key provisioning, replacement
of the current operator E5 contract and activation remain held. A concrete operator-authorized
policy is required before granting production powers; a prepared policy is not an authorization
or a human signature. The earlier unknowns below describe the current runtime contract, not a
requirement to locate a nonexistent external coordinator or to request another generic GO.

| ID | Requirement | Source and priority | Current evidence/state |
|---|---|---|---|
| REQ-001 | A dispatch instruction MUST be accepted only after independent root-Supervisor verification of its purpose-specific signature and bindings for request ID, task, slot, attempt, epoch, run ID, key ID, absolute UTC expiry, version, algorithm, and purpose. Invalid, expired, mismatched, or unsigned instructions MUST fail closed. | Accepted S2 contract in `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; S2 goal. | Verifier/client source is recorded as committed; `core/STATE.md` records source/test acceptance. This does not prove production issuer/key provisioning or runtime acceptance. |
| REQ-002 | The Store MUST remain the sole authority for task assignment, leases, and durable dispatch state; the signer/transport MUST NOT assign work or provide an alternate scheduler. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Architecture is adjudicated and accepted. Production integration remains incomplete under REQ-005. |
| REQ-003 | The owner relay MUST deliver only already-authorized signed instructions through the accepted authenticated Supervisor/Store and Store-filtered dispatch path, with ambiguous outcomes handled fail-closed and without unsigned fallback. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Existing bounded architecture and transport-only source/test scope are recorded as accepted. The qualified production owner-to-Runner journey remains open. |
| REQ-004 | Runner admission and recovery MUST preserve the accepted fail-closed boundary: unresolved or ambiguous dispatch outcomes MUST NOT permit an unauthorized or duplicate execution, and the existing admission fence MUST remain effective across the recorded recovery path. | `core/BACKLOG.md`, S2 section, including `S2-PROV-M03-R01` source/test closure and changes 0518/0522. | `S2-PROV-M03-R01` is recorded closed for source/test only. Installed systemd behavior and production runtime remain unverified. |
| REQ-005 | S2 production-runtime acceptance MUST be supported by an authenticated owner identity and root-controlled configuration, an authorized production instruction issuer/trust key, current run-bound E5/runtime evidence, and a qualified real owner-to-Runner journey. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary. | `S2-DISPATCH-M01` is MAJOR/OPEN. Current production integration, current signed E5, and service/runtime qualification are not established. |
| REQ-006 | Evidence and approval MUST identify the exact reviewed source revision. Source/test results, synthetic fixtures, or prior-head records MUST NOT be represented as installed-production or current-runtime acceptance. S2 MUST remain NOT APPROVED and S3 unstarted until its required acceptance and exact-head gate are satisfied. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope and closure queue. | Current records explicitly distinguish source/test closure from runtime acceptance and state S2 is NOT APPROVED; S3 remains unstarted. |

## Non-functional requirements and constraints

- **Security:** fail closed on invalid provenance and ambiguous admission; keep signer authority distinct from Store assignment authority. [REQ-001–REQ-004; sources above.]
- **Runtime isolation:** use the accepted authenticated identities, root-controlled configuration, and bounded runtime profile; do not claim isolation from mocked peer credentials or transient test units. [REQ-004–REQ-005; `core/STATE.md`, current S2 coordinator/runtime adjudication.]
- **Numeric service targets:** UNKNOWN. The active S2 records do not establish a numeric dispatch-latency, availability, throughput, or recovery-time target. No target is invented here.
- **Restricted verification:** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN` under the recorded restrictions. A skipped or unrun selector is not a pass. [`core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary.]
- **Data safety:** fresh schema-v6 Store initialization is conditionally allowed by the recorded adjudication; migration of an existing Store requires a separate gate. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]

## Facts, assumptions, and unknowns

### Facts

- GPT-PM accepted the existing bounded coordinator architecture; no external coordinator path is required. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]
- Transport-only source/test scope has recorded GPT-PM acceptance; the recorded functional and WSL runs are source/test evidence, not production-runtime proof. [Same state section; `core/BACKLOG.md`, S2 section.]
- S2 remains `NOT APPROVED`; `S2-DISPATCH-M01` remains `MAJOR/OPEN`; current signed E5, service/runtime qualification, and final exact-head approval remain open. [Same state section.]
- The operator is the sole human owner. Service identities are technical isolation identities, not project owners. [Same state section.]

### Assumptions

- This artifact belongs to the existing active S2 because the project state and backlog identify S2 as active. The framework sprint ID above is recorded as its phase-1 tracking ID, not evidence of a new sprint. [This mapping follows the parent-task instruction and the active S2 records; framework state is tracked separately.]
- Historical test counts and acceptance matrices at earlier revisions are not promoted to current-head evidence. The latest current-state summary governs this reconciliation.

### Unknowns that block S2 closure

| ID | Unknown / missing acceptance evidence | Owner | Next action |
|---|---|---|---|
| UNKNOWN-001 | No production issuer delegation policy/key is installed or evidenced. GPT-PM accepts bounded machine issuance in principle, subject to the concrete provenance contract and separate production authority decision. Codex MUST NOT self-authorize production powers or create production keys. | Codex prepares a precise policy and source contract; GPT-PM adjudicates its architecture; operator authorizes the exact production delegation and key custody if activation is later desired. | Implement/review the bounded machine issuer contract and idempotent Store-assignment provenance. Keep production signing held until the exact delegation is authorized, key custody is established, and its trust chain is verified. |
| UNKNOWN-002 | No production machine-attestor policy, independently verified current run-bound measurement provenance, root configuration, or qualified real owner-to-Runner journey is evidenced. Machine E5 is acceptable only under its explicit versioned trust domain and independent measurement contract; the current human verifier is not silently replaced. | Codex prepares versioned schemas, pure validators and read-only collectors; GPT-PM adjudicates provenance; operator authorizes any concrete production delegation/key custody. | Implement the measurement and verification contract; collect only genuine permitted observations. Keep E5 activation held until independent collector identities, evidence freshness/binding, exact policy, and applicable authority are verified. |
| UNKNOWN-003 | Exact-head GPT-PM final approval for the completed S2 code, mapped tests, and relevant specialist reviews is not recorded. | GPT-PM; Codex owns coordination and submission. | After coding and permitted test/review work are complete, submit the exact final revision and correlated evidence for the required gate; any later code change requires a fresh gate. |

## Traceability and acceptance boundary

`REQ-001`–`REQ-004` describe the accepted bounded source contract. Their recorded source/test evidence does not close production-runtime acceptance. `REQ-005` is currently unmet and is tracked by `S2-DISPATCH-M01` (MAJOR/OPEN). `REQ-006` prevents premature sprint closure or S3 work. Restricted selectors remain `NOT_RUN`; no waiver or pass is inferred from their absence. Once runtime evidence and all permitted source/test/review work are reconciled, GPT-PM must adjudicate the exact final revision before S2 can be reported closed.

## Glossary

- **E5:** the project’s sandbox/runtime inventory and provenance acceptance item; current S2 requires fresh run-bound evidence, and any operator-root-signed attestation must be genuine.
- **Exact-head gate:** GPT-PM approval correlated to the precise final Git revision and its evidence.
- **Store:** the existing durable authority for task assignment, leases, and dispatch state.
- **`NOT_RUN`:** a scenario was not executed; it is not a pass.
