# Change 0554: Root issuer verification and transaction contract

Sprint: 39b7cc253f5d

## Why and behavior

Actual database and security reviewers identified two MAJOR design omissions in the root-bound v1 issuer proposal: accepting a structurally valid completion without cryptographic verification, and separating delegated provenance checks from the snapshot/commit which grants authority. The proposal now requires a trusted verifier bound to exact signing bytes, signer fingerprint and immutable journal identity. External cryptographic processes and key reads stay outside SQL; the Store binds a root-owned verification context to exact bytes inside the current transaction. The pure callback contract was committed separately in change0553.

Admission, delivery observation, grant persistence/replay and durable runner claim/reservation use a shared connection-taking current-authority predicate and locked grant-basis helper. Delivery is explicitly a snapshot hint; it cannot preserve authority after revocation. Delegate-origin work cannot fall through to legacy because the feature is disabled or provenance is missing. No new wire version, scheduler, daemon, table or migration is proposed.

## Independent design rechecks

At HEAD e44f48dca00802b9f6ad6c8629fe909dbe0a4a99, actual database-reviewer and security-reviewer roles, using their configured gpt-6-luna profiles at medium effort, read the revised working-tree contract and committed pure reducer. Both reported no remaining design-level BLOCKER/MAJOR and recommended bounded integrated SOURCE GO. They did not authorize runtime signing, key provisioning, activation or S2 closure. Their dispositions are recorded in the linked evidence file.

## Paths and decisions

- docs/sdlc/S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md: verification/transaction corrections and explicit scope.
- docs/sdlc/S2_DELEGATED_MACHINE_TRUST_DESIGN.md: existing pending pointer identifying the selected root-Supervisor/v1 alternative; no production-authority claim.
- docs/sdlc/evidence/s2-root-issuer-design-recheck-20261029.md: actual role findings and limits.
- docs/sdlc/STATE.md and state.json: the operator-requested `python D:/Repo/Agentic_Framework/tools/af_cli.py on` resumed existing S2 at phase7 hard, with no missing exit artifacts. This machine state is not runtime/test acceptance or phase8 approval.
- core decision/lessons logs and generated registry: current provenance.

## Verification state and next action

No tests, checks, build, CI, runtime configuration, service activation, key creation or signing were executed by this documentation batch. S2 coding remains open. Codex requests GPT-PM's targeted I01 source adjudication, then implements the bounded integrated contract before the final permitted test/review phase. Existing forbidden process/crash/mutation coverage remains NOT_RUN and is not waived by this change.
