# S2 task-by-task acceptance checkpoint — 0471/0472 working diff

Date: 2026-10-28  
Repository: `D:\Repo\Virtual_scrum_team`  
Branch/base HEAD: `s4-canonical-continuation` / `2da827be982d3f2d6f2adf152668af6ff8007f21`  
Current source is an uncommitted working diff in the canonical checkout. No per-sprint worktree was created.

This checkpoint updates only claims supported by evidence linked below. Earlier S2 state is
carried forward from `s2-task-acceptance-a6ea0dc-20261027.md` and its cited exact-head records;
historical results remain tied to their recorded heads. The latest approved focused run is a
working-diff run, not full S2 or service-runtime acceptance. A subsequent silent-failure and database
review also found a post-reservation exception path, missing predecessor binding, and a gate-state
omission. Those source findings were corrected and directly tested in the 138-pass run below; fresh
specialist review of the corrected source is still pending.

## Acceptance matrix

| ID / criterion | Meaning | Current state | Evidence / completed work | Remaining acceptance | Dependency / owner | Next step |
|---|---|---|---|---|---|---|
| VST-009 / E1 | Reviewer key mapping and independent reviewer contract | Selected coverage PASS; whole criterion PARTIAL | Final authorized focused run: 32 selected IDs passed, `s2-final-fatal-focused-test-run-20261027.md` | Full trust boundary and exact-head gate remain open | Codex coordinates; GPT-PM adjudicates | Include final diff and selected evidence in exact-head gate |
| VST-010 / E2 | Runner derives evidence/head; caller cannot replace authority | Selected coverage PASS; whole criterion PARTIAL | Final authorized focused run: 38 selected IDs passed | Persistent service identity/helper runtime is not proven | Codex; designated test roles | Keep runtime claims NOT_VERIFIED until authorized evidence |
| VST-011 / persistent execution authority | Worker cannot access signer authority; execution is bound to trusted grants | Source implemented; selected tests PASS; runtime NOT_VERIFIED | Latest approved run: 46 persistent-runner, 32 E1, 38 E2, and 22 E6 IDs passed; `s2-final-gate-authority-regressions-20261028.md` | Actual service framing/restart, deployed identity/cgroup/signer boundary, and production coordinator integration remain unproven | Codex coordinates; functional-test-reviewer/e2e-runner own test execution; GPT-PM verifies integration | Preserve NOT_RUN runtime cases; resolve S2-DISPATCH-M01 before production-path acceptance |
| VST-012 / E3 | External anchor rejects restored/forked/malformed recovery state | Partial; safe selected fixtures only | Prior checkpoint records 8 WSL temporary-anchor and 10 Windows store tests | Interrupted commit/checkpoint recovery scenarios remain NOT_RUN under the active restriction | Codex records; operator owns any required scope authorization; GPT-PM adjudicates | Keep crash/recovery selectors NOT_RUN |
| VST-013 / E4 | POSIX descendant cleanup and Windows nested Job Object containment | Partial; design and selected evidence only | Prior checkpoint records safe POSIX admission tests and bounded Windows nested Job Object probes | Populated stale-scope cleanup, runner crash/restart, kill-on-close, descendant termination, Windows ACL/key isolation, and persistent delegated-parent behavior remain unproven | Codex coordinates; designated test roles own permitted execution; operator owns host provisioning/attestation | Preserve prohibited scenarios as NOT_RUN; obtain only permitted host evidence |
| VST-014 / E5 | Fresh run-bound sandbox inventory or operator attestation | OPEN / NOT VERIFIED | Read-only Windows/WSL records exist; they are not a current operator-root-signed inventory | Signed inventory and full host egress/persistent boundary are absent | Operator signs required attestation; Codex collects permitted evidence; GPT-PM adjudicates | Do not manufacture signature; keep E5 open |
| VST-015 / E6 | Diff evidence is path-scoped/signed; reviewer credential cannot write | Selected coverage PASS; whole criterion PARTIAL | Final focused run: 22 DiffGate IDs passed | Windows read-only credential and deployed persistent behavior remain NOT_VERIFIED | Codex; GPT-PM | Preserve limits and include exact evidence in final gate |
| VST-016 / E7 | STOP/rollback and restart fail closed | Selected transition coverage only | Earlier checkpoint records 8 selected lifecycle/breaker/reconciliation cases | Restart/crash acceptance remains NOT_RUN; final runner daemon restart not executed | Codex coordinates; designated test roles own authorized tests/runtime | Keep restart/crash claims NOT_RUN pending authorization and safe environment |
| VST-017 / E7 | External operations are idempotent; timeout state remains retryable | Selected synthetic coverage only | Earlier checkpoint records operation recovery, timeout/retry, lock timeout and synthetic Git groups | Real child start/kill/read failure and persistent workspace/resource boundaries remain unproven | Codex; designated test roles | Do not infer runtime PASS from synthetic tests |
| VST-018 / E7 | Circuit breaker override is episode-bound and replay-safe | Selected coverage only | Earlier checkpoint records lifecycle/breaker/reconciliation group | Overall S2 remains open; no full recovery/restart acceptance | Codex; GPT-PM | Carry into exact-head gate without overstating |
| VST-019 / E7 | Startup reconciliation blocks until valid resolution/replay | Store fixtures pass; process restart NOT_VERIFIED | Prior Windows store and WSL anchor fixtures; current source terminalizes predecessor PENDING/EXECUTION_RESERVED claims as INDETERMINATE | Installed service restart, operator resolution path and exact production integration remain open | Codex coordinates; GPT-PM adjudicates; operator owns required host action | Keep runtime acceptance open; preserve non-replay invariant |
| VST-020 / E8 | Compare workers on the same crash/resume fixture without unauthorized writes | NOT ACCEPTED; selectors NOT_RUN | No E8 execution; prior checkpoint records the six E8 placeholders within 20 restricted/unverified IDs | Requires prohibited crash/resume, budget, write/egress scenarios and candidate authorization | Operator owns any valid policy authorization; Codex records; GPT-PM adjudicates | Do not execute or claim PASS |
| S2.D1 | Every manifest slot pins a required command and trusted parser | Selected contract coverage PASS; whole gate open | Prior exact-head contract group plus current selected tests | Full sprint acceptance and exact-head gate remain open | Codex; GPT-PM | Include in final reviewed diff |
| S2.D2 | Any waiver is narrowly scoped to named non-execution states | Contract code coverage; no operator waiver recorded | Prior exact-head contract group; no waiver inferred | The 20 restricted/unverified selectors remain unwaived and NOT_RUN | Operator for any valid signed waiver; Codex preserves status; GPT-PM adjudicates | Keep them NOT_RUN and unwaived |
| S2-RF-M01 / persistent runner acceptance | Persistent service connects authorized intent to one-use runner execution | OPEN / NOT APPROVED | Change 0471 implements the local grant, authenticated IPC, claim/reservation, and service library paths; current focused tests cover authority behavior | Production coordinator source/call site is absent in this repository; runtime/systemd and E5 remain incomplete | Codex identifies in-scope source; GPT-PM verifies; operator owns reserved host authorization | Do not invent scheduler/CLI/spool or claim production acceptance |
| S2-LEASE-M01 | Recovery authority is separate from grant issuance | GPT-PM decision RETAINED | Correlated request `1ff3b849-6180-4cb3-83ea-0eab47e56a3e`, reply `762291a2-5c34-470d-8b98-9a38a4cfc5ee`: no global reaper as `issue_grant` side effect | Any existing trusted coordinator/recovery source and its authority must be established | Codex identifies source; GPT-PM verifies | Keep grant issuance side-effect-free; refuse when required recovery marker is missing |
| S2-DISPATCH-M01 | Existing production coordinator invokes bounded authenticated runner | MAJOR / OPEN | In-repo search found only the library dispatcher definition and its internal call; GPT-PM confirmed an uncalled helper is not production integration | Need an existing in-scope coordinator with durable assignment identity, or retain incomplete acceptance | Codex identifies source; GPT-PM verifies any integration | Search only this repository; if absent, retain the blocker and do not create a new scheduler |
| S2-RC-M01 | Ambiguous predecessor execution is reconciled before any successor attempt | Source + focused regressions PASS; fresh review pending | `Store` binds `AUTHORITY_CHANGED_BEFORE_COMPLETION` to `EXECUTION_RESERVED`; resolution outcomes require an allowed exact predecessor state. Direct null/wrong-state and outcome-matrix regressions pass in `s2-final-gate-authority-regressions-20261028.md` | Fresh exact-diff specialist and GPT-PM review; operator-signed evidence is not inferred | Codex implements and coordinates; functional-test-reviewer tests; GPT-PM adjudicates; operator owns any attestation | Obtain fresh specialist review, then one exact-head GPT-PM sweep |
| REL-M01 | Fail closed after any failure leaves a durable execution reservation unresolved | Source + focused regression PASS; runtime NOT_RUN | Reservation is marked confirmed before the post-reservation boundary callback; an injected `OSError` becomes `AmbiguousExecutionAuthorityError` and no child launches; direct regression is in `s2-final-gate-authority-regressions-20261028.md` | Actual daemon/systemd generation termination and restart remain unproven | Codex coordinates; e2e-runner owns permitted runtime execution; GPT-PM reviews gate | Obtain only authorized runtime evidence; keep unrun restart cases NOT_RUN |
| S2-GATE-M01 | A prior PASS receipt cannot approve while a later runner execution is unresolved | Source + focused regressions PASS; fresh review pending | `evaluate_gate` checks claim state inside the same SQLite snapshot as receipts; regressions refuse `PENDING`, `EXECUTION_RESERVED`, and `INDETERMINATE`, then allow ordinary evaluation only for safe terminal states | Fresh database/reliability review and exact-head GPT-PM review | Codex implements; functional-test-reviewer tests; database-reviewer/reliability-reviewer review; GPT-PM adjudicates | Re-review the exact committed source and test evidence |
| S2 Phase 8 / sprint gate | All acceptance items, allowed tests/reviews, exact-head GPT-PM review | NOT APPROVED | Four approved groups passed 138 IDs on the current working source/test diff; artifact: `s2-final-gate-authority-regressions-20261028.md` | Full S2 acceptance incomplete; fresh specialist and exact-head GPT-PM reviews, allowed system evidence, E5 attestation, and production coordinator path remain open | Codex coordinates; GPT-PM owns adjudication; operator owns required attestation | Continue S2 only; do not start S3, push, PR, or merge |

## Exact selected functional evidence

The designated `functional-test-reviewer` ran four approved command groups on the current working
source/test diff based on HEAD `2da827be...`: 46 persistent runner tests, 32 E1 contracts, 38 E2
contracts, and 22 E6 DiffGate tests: **138 passed, 0 failed, 0 skipped**. Exact commands, source
hashes, tracked diff SHA-256 `4a9ea8fa78009134042224f563bf8705b68c05db2ce749f1f2767d0bdae58e19`,
working-delta SHA-256 `b45ba45bc05028a84a9b065642a12833e6b7c75d521359d61250dca3f210fde2`, and evidence
SHA-256 `f32cfce4fe08cf2252612e67443c44ffd03c7993bad8ae030ed7141eb700c63c` are recorded in
`s2-final-gate-authority-regressions-20261028.md`. The protected pre-existing
`s2-functional-test-run.md` was not changed.

This run does **not** prove `REFUSED` socket framing, systemd restart, service installation,
WSL runtime, Windows ACL/Job Object behavior, full egress, or any prohibited process/crash/recovery/
mutation/E8/policy scenario. Those remain `NOT_RUN` or `NOT_VERIFIED` as identified above.

## Ordered closure queue

1. Commit the tested source and focused regression set with a dedicated change record, decision-log
   entry, and lesson; then obtain fresh specialist review on that exact committed head.
2. Identify an existing in-scope production coordinator and its durable assignment source. If it
   does not exist in this repository, retain `S2-DISPATCH-M01` as the concrete production-path
   blocker; do not invent a new authority path.
3. Complete only authorized system evidence; preserve all restricted process, crash/recovery,
   mutation, E8, and policy selectors as `NOT_RUN`; obtain the required operator-root-signed E5
   inventory rather than fabricating one.
4. Obtain GPT-PM's fresh exact-head review after code, tests, and specialist reviews are final.
5. Close S2 before starting S3. No push, PR, or merge is authorized by this checkpoint.
