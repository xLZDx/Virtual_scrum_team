# Sprint S2 plan: trust roots and isolated worker sandbox

Status: IN PROGRESS, implementation not started at baseline `6117ba24`. Prepared on 2026-10-24 while S1 was being tested and reviewed (process rule: prepare the next sprint's documentation during the current sprint's testing). Nothing in this document is done; every statement about behavior describes a target.

Sources: `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md` section 4 (S2 paragraph), blueprint `docs/UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md` sections 6, 9, 13.2-13.4, decision log entries "S1 third review" and "S1 fourth check" in `core/DECISION_LOG.md`, and "Known limits" in `tools/vst/schemas/README.md`.

Naming note: the blueprint roadmap (section 10) calls S2 "Planning router" and S3 "Worker pilot". The baseline plan (section 4) re-scoped S2 to the isolated worker sandbox, and this plan follows the baseline. The blueprint roadmap table is stale on this point and is not changed here; the S2 closing change record should align it.

## 1. Goal

Move the trust roots out of the process that runs commands and prove an isolated worker can run on the S1 control plane. Concretely: (a) close the five trust gaps deferred out of S1; (b) write the sandbox specification first and prove it with a pre-flight probe; (c) put a real (but minimal) worker inside that sandbox and show it survives crash, STOP and resume on one fixture, with the S1 gate still the only acceptance authority.

## 2. Scope

In scope:
- Authenticated reviewer identity (distinct reviewer signing key; IndependentReview receipts verified with it).
- Runner-derived `candidate_head`; signing key isolated from the process that runs commands.
- Externally anchored event head to detect whole-database rollback.
- Verification of POSIX permissions and process-group behavior, and of Job Object nesting.
- Sandbox specification (blueprint 13.4) and a stdlib-only pre-flight probe.
- Deterministic diff gate; read-only reviewer credential.
- STOP and rollback transition table, idempotency keys, circuit breaker, startup reconciliation.
- A bake-off of a hand-written worker loop against at most one external candidate on one crash/resume fixture, on a synthetic repository with a local bare remote.

Out of scope (explicit):
- Any real project or pilot repository; real customer or production data.
- Push, pull request or merge performed by a worker; no push token inside the sandbox.
- Unattended mode (stays off until the kill path is proven, blueprint R-6).
- CI, mutation runs, red/green seeded-defect checks (ADR-0001; read as `NOT_RUN`).
- QA automation (S4), AEVE gate (S5), CI/PR flow (S6), planning router, scale beyond 1 AI slot.
- Cloning, installing or updating any upstream into an active worktree; external candidates only in a quarantined evaluation location after operator authorization, pinned to a commit with license audit.
- Global configuration changes under `~/.claude` (operator-owned, see `core/BACKLOG.md`).
- History rewriting; changing S1 contracts except where an epic below names it.

## 3. Entry criteria and verified baseline

1. **S1 merge:** satisfied. `origin/main` and the local `main` both resolved to `6117ba24b08a260b42402db6da0bf767864e1c04` on 2026-10-24; that history contains merge `d5cd7f5` and follow-ups `c5a8eb1` and `61412e2`.
2. **S1 test evidence:** retained in `docs/sdlc/evidence/`, but it is not exact-merged-head evidence. `docs/changes/0032-s0-s1-merge-record.md` and `docs/changes/0033-s0-s1-closure-report.md` state that test agents ran on a working tree before the final commit and did not rerun on the approved head. S2 does not upgrade that claim.
3. **Sandbox provisioning:** not yet reached. The operator must provision or authorize provisioning of the dedicated WSL distribution or VM before sandbox-dependent acceptance in E4-E8. E1-E3 and platform-independent E4 work may proceed first; blocked acceptance must be recorded as `NOT_RUN` until the environment exists.
4. **External candidate:** none is authorized for this run. Use the hand-written loop only. Cloning or running an external candidate remains out of scope unless the operator separately authorizes a pinned, quarantined evaluation and license audit.
5. **State authority:** until a VST store instance is initialized for this project, `docs/sdlc/STATE.md` is the phase record. At the documented cutover (the first initialized store bound to this project's state), the store is authoritative and `STATE.md` becomes a generated read-only view; do not permit two independent writers.

## 4. Epics and stories

Acceptance mechanism classes follow blueprint 13.3: executable negative test, schema validation, signed inventory, static audit, independently reviewed proof, explicit operator decision. Each epic lists a non-empty denominator and a failing input that must be rejected.

### E1 Authenticated reviewer identity (VST-009)
Mechanism: executable negative test.
- S1.1 Add a `reviewer_key` (distinct from worker, supervisor, operator and event keys; the pairwise-distinct key check is extended to it) and a domain-separation label for reviewer receipts.
- S1.2 `IndependentReviewReceipt` includes `reviewer_key_id` and is verified with the mapped reviewer key in the gate; a receipt signed with the worker key no longer satisfies a review slot.
- S1.3 A reviewer principal registry maps normalized reviewer principal to key id. The registry is signed with the already trusted operator key under a distinct domain label; the gate receives the trusted operator public key through its existing trust configuration, verifies the signature, and matches the registry content digest/version named by the manifest. The manifest author principal must not map to the reviewer key. Unknown registry versions, digest mismatches, duplicate principals, or invalid signatures are non-approval.
- Denominator: every IndependentReview receipt fixture in the test set (valid reviewer; worker-signed; author-equals-reviewer; unknown principal; duplicate principal; reviewer key equal to another key; invalid registry signature; stale registry version; registry digest mismatch).
- Must reject: an IndependentReview receipt with verdict APPROVE signed with the worker key (gate gives non-approval).

### E2 Runner-derived head and signing-key isolation (VST-010, VST-011)
Mechanism: executable negative test, plus independently reviewed proof for the platform boundary.
- S2.1 The runner reads the candidate head from the repository itself (git, read-only) after command execution and writes it into the receipt; a head supplied by the caller is not part of the acceptance API.
- S2.2 Split signing from command execution: commands run under a restricted worker identity with no signing-key file access and no access to the signer IPC endpoint. A trusted runner outside that identity derives the head and records argv, exit codes, artifact hashes, and the request nonce; a separate signer process/account accepts requests only from the runner identity and signs that canonical record. The signer rejects missing, duplicate, or inconsistent evidence fields. The worker receives only the final receipt, never the signing key or signer channel.
- S2.3 Key files get restrictive permissions (Windows ACL; POSIX mode 0600 and owner check), and the runner refuses to start if the key is readable by the command account.
- Denominator: all receipt types produced by the runner (four) and every key kind (five); head history changes across at least three commits; exact signing-request replay, malformed request, and command identity access to both key storage and signer IPC.
- Must reject: a receipt whose `candidate_head` differs from the repository head at run time; a command that reads the signing key file or reaches signer IPC during the run; an old signing request replayed for a later head.

### E3 External anchor against whole-database rollback (VST-012)
Mechanism: executable negative test.
- S3.1 After each committed event, the store compare-and-appends (event count, head hash) signed with the event key to an append-only anchor file or location outside the database and outside the worker mount. Repeating the same count/head is idempotent; the same count with a different head is an integrity failure.
- S3.2 Startup and `verify` compare the database head with the latest anchor; a database whose head is older than the anchor, or whose chain does not extend the anchor, is reported as `integrity` failure and blocks all gate decisions. If the database is exactly one valid event ahead because the process stopped after the database commit but before anchor append, startup enters a write-locked recovery state and appends that verified event to the anchor before permitting any lease or gate operation. Any other mismatch, unavailable anchor, or failed recovery stays fail-closed and requires operator recovery; no receipt is approved during recovery.
- S3.3 The anchor path is configuration, default-deny when unset in sandbox mode.
- Denominator: scenarios for anchor state (matches, ahead of database, database ahead of anchor by one committed event, older internally consistent database, anchor missing, anchor tampered, interruption after event commit, interruption during anchor append, interrupted-recovery restart).
- Must reject: restoring an earlier internally consistent copy of the database file (anchor ahead of database).

### E4 Platform verification: POSIX and Job Object nesting (VST-013)
Mechanism: executable negative test where the platform is available; independently reviewed proof otherwise.
- S4.1 Run the runner and store test sets inside the sandbox distro (POSIX): process-group kill, post-exit descendant kill, key-file permission check.
- S4.2 Verify Job Object behavior when the runner itself already runs inside a parent job (nesting) on Windows; record the supported configurations and refuse unsupported ones explicitly.
- S4.3 Replace the 2 skipped tests (platform-specific) with real runs on their platform, or document each as `NOT_RUN` with reason.
- Denominator: the full list of platform-conditional tests (names recorded at sprint start, not fewer than the S1 skipped set).
- Must reject: a command leaving a descendant alive after the run (exit marker -4 or kill failure recorded, never PASS).

### E5 Sandbox specification and pre-flight probe (VST-014)
Mechanism: static audit of the specification plus signed inventory from the probe.
- S5.1 Write `docs/SANDBOX_SPEC.md`: dedicated WSL distribution or VM; Windows drive automount disabled; interoperability disabled; no container-engine socket; default-deny egress with an explicit allowlist (empty by default); non-root user; per-run scoped secrets (created per run, deleted after, never the signing keys); CPU, memory and time budgets; no host path outside the run directory.
- S5.2 A stdlib-only pre-flight probe run inside the sandbox emits an inventory (mount table, interop setting, user id, socket paths present, egress test to a blocked target and a sandbox-local loopback canary, environment variable names) and the runner signs it; the supervisor refuses to start a worker without a fresh passing probe tied to the run id. The loopback canary is an ephemeral local test endpoint, not an upstream or public-network exception; the default external egress allowlist stays empty.
- S5.3 Operator step: provision the distro/VM (entry criterion 3).
- Denominator: every requirement line in the spec (each maps to one probe check or is marked operator-verified), including empty external allowlist, passing sandbox-local loopback canary, and blocked external target.
- Must reject: a probe inventory showing automount on, interop on, a container socket present, root user, or egress to a non-allowlisted target (each separately).

### E6 Deterministic diff gate and read-only reviewer credential (VST-015)
Mechanism: executable negative test.
- S6.1 Before any model review, a pure function checks the worker diff against a path allowlist derived from the task scope; edits to CI configuration, lockfiles, hooks, manifests and install scripts are blocked unless the manifest lists them.
- S6.2 Result is a typed, runner-signed receipt component bound to manifest digest and candidate head and consumed by the gate (missing, stale, or inconsistent diff-gate evidence is a non-approval).
- S6.3 The reviewer runs with a read-only credential distinct from the worker credential and cannot write to the worktree or the store (checked by the probe and a negative test).
- Denominator: diff fixtures covering each blocked class (CI file, lockfile, hook, manifest, install script, path traversal, path outside scope, rename into blocked path, symlink); parser catalog known/unknown id, version mismatch and content-digest mismatch; missing required command; attempted worker write using reviewer identity.
- Must reject: a diff that edits a hook file, and a diff that renames an allowed file onto a blocked path.

### E7 Lifecycle: STOP, rollback, idempotency, breaker, reconciliation (VST-016 to VST-019)
Mechanism: explicit transition table (static audit) plus executable negative tests.
- S7.1 STOP and rollback transition table (state x event -> state, with the cleanup action and who may trigger it) as a document and as data used by the code; any pair not in the table is rejected.
- S7.2 Idempotency keys at the trusted supervisor/coordinator boundary for simulated push, pull request and receipt creation: a repeated operation with the same key returns the first result and performs no second effect (push and pull request are simulated against the local bare remote; no real remote). Worker commands have no push/PR credential or operation path.
- S7.3 Circuit breaker with a paused-provider state: consecutive provider failures open the breaker, workers are not started while open, no silent fallback to another model or provider; a manual-override path writes a distinct record, never a plain APPROVE.
- S7.4 Startup reconciliation after restart: leases, slots, in-flight attempts and anchors are reconciled before any new lease; orphaned attempts become `INCONCLUSIVE(WORKER_LOST)`.
- Denominator: every state-event pair in the table; every operation kind with an idempotency key; each breaker state.
- Must reject: a STOP event in a state where the table has no entry; a duplicate push key causing a second push; a worker start while the breaker is open; a lease started before reconciliation completes.

### E8 Isolated worker candidate bake-off (VST-020)
Mechanism: executable negative test on a fixture, plus explicit operator decision for the choice.
- S8.1 One crash/resume fixture on a synthetic repository with a local bare remote: worker killed mid-edit, STOP injected, budget exhaustion, resume.
- S8.2 Run the hand-written loop worker inside the sandbox through the E5 probe, E6 diff gate and S1 gate. Optionally run one external candidate under the same fixture (operator-authorized, pinned commit, quarantined clone, license audit; its repository text is treated as untrusted).
- S8.3 Comparison record (what survived crash, STOP, budget, resume; unauthorized writes observed) and an operator decision on the worker used in S3. No "TOP" label before this record exists.
- Denominator: the fixture scenarios (crash, STOP, budget exhaustion, resume, unauthorized write attempt, egress attempt) for each worker compared.
- Must reject: a worker write outside the allowed paths, an egress attempt to a blocked target, a resume that reuses an earlier epoch receipt.

## 5. Sprint order

Per the operator workflow: all E1-E8 code and documents first by `implementation-engineer`; then `functional-test-reviewer` and `e2e-runner` author and run focused tests per epic and the complete set again at the end; then relevant read-only reviewers on the exact head; fixes; final independent review of the exact head; then push and one pull request. E1-E4 do not depend on E5; E6-E8 depend on E5 and the operator-provisioned sandbox. Suggested order: E1, E2, E3, E4 (platform part waits for sandbox), E5, E6, E7, E8.

## 6. Definition of Done for S2

1. Every epic's failing input is rejected by an executable test, and each test set that the test agents wrote was run completely on the exact final head, with command, collected list, counts and head retained under `docs/sdlc/evidence/`.
2. No skipped or `NOT_RUN` result counts as PASS; each platform-conditional test is run on its platform or recorded as `NOT_RUN` with a reason in the sprint record.
3. The sandbox specification exists, and a probe inventory from the provisioned sandbox for the final head shows every spec line passing or marked operator-verified.
4. A reviewer receipt signed with a worker key is rejected by the gate (E1), and a restored old database is detected (E3).
5. The Known limits section of `tools/vst/schemas/README.md` is updated: closed items removed, remaining items stated.
6. Specialist reviewers (reliability, security, silent-failure, architect) report no open BLOCKER or MAJOR on the exact head; independent review on an allowed model approves the exact head.
7. Change records, decision log and lessons log entries, backlog and state updated, document registry regenerated, blueprint roadmap naming for S2 aligned.
8. One pull request for the sprint; push only after the independent approval of the exact head.

## 7. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Operator does not provision the sandbox | E5-E8 cannot be accepted | Entry criterion 3; E1-E4 are independently valuable; record block with cause |
| Key isolation on Windows is weaker than expected (same account) | E2 acceptance only partial | Use a separate account or the sandbox boundary; state the narrowest guarantee proved; do not claim isolation otherwise |
| Local anchor stored on the same disk is deletable by a privileged attacker | E3 detects accident and simple restore only | Document the limit; anchor outside worker mount; stronger remote anchor is a later option |
| WSL interop or automount settings revert after updates | Silent loss of isolation | The probe is mandatory per run and fresh per run id |
| External candidate has prompt-injection or supply-chain issues | Compromise of sandbox | Pinned commit, license audit, quarantined clone, diff gate and independent review of its output |
| Scope growth (8 epics) | Late closure | E8 candidate comparison limited to one external candidate; defer anything not named here |
| Skipped platform tests hide failures | False green | DoD item 2; denominator recorded at sprint start |

## 8. Backlog mapping

`core/BACKLOG.md`: VST-009 (E1), VST-010 and VST-011 (E2), VST-012 (E3), VST-013 (E4), VST-014 (E5), VST-015 (E6), VST-016 to VST-019 (E7), VST-020 (E8).

## 9. Items added after the S1 independent review (deferred to S2)

Both items were found by the independent review of S1 and are deliberately not fixed in S1 (`gate.py` is unchanged).

- S2.D1 Mandatory commands and parser pinning. `test_result_parser` is a caller-supplied callable outside the manifest, and the gate does not check that every mandatory command actually ran. The manifest names each mandatory command and a parser identifier, version, and content digest; the gate resolves only parser implementations in its trusted built-in catalog and checks the pinned digest. The runner records argv, exit code, and parsed outcome for every required command. Must reject: an omitted mandatory command; an unknown parser id/version; a digest mismatch; or any caller-supplied parser not present in the trusted catalog.
- S2.D2 Scope of a signed waiver. A signed waiver may cover only `NOT_RUN`, `INCONCLUSIVE`, or `BLOCKED` evidence, with the named and scoped operator record required by ADR-0001. `FAIL`, reviewer `MODIFY`, and `NO_GO` are never waivable. This sprint adopts the narrower safe scope; it does not authorize changing the global ADR or an operator's other records.

## 10. Decisions required before implementation

The following contracts are binding for S2 implementation and test design:

1. The operator key is the trust root for the signed reviewer registry; the manifest binds its exact registry version and content digest. Registry validation fails closed.
2. The worker identity cannot read signing keys or reach signer IPC. Only the runner identity may submit a canonical signing request; the signer signs runner-derived evidence and rejects malformed or replayed requests.
3. External-anchor recovery may auto-append only the single verified event immediately following the anchor. All other mismatches stay write-locked and fail-closed pending operator recovery.
4. Mandatory result parsers are selected from a trusted catalog by manifest-pinned id, version, and digest; caller-supplied parser callables are removed from the acceptance path.
5. Egress is deny-by-default. The positive pre-flight probe targets an ephemeral loopback canary inside the sandbox; it does not grant external network access.
6. Idempotent push/PR simulation belongs to the supervisor/coordinator boundary. The worker has no credential or path that can push or open a PR.
7. S2 does not authorize an external bake-off candidate. The hand-written worker is the only candidate unless separate operator authorization is recorded.
8. Only `NOT_RUN`, `INCONCLUSIVE`, and `BLOCKED` can receive the separately recorded waiver verdict; failure or reviewer rejection cannot.
9. Introduce an explicit manifest contract version 2. Add `reviewer_registry: {version, sha256}`, `mandatory_commands: [{slot, argv, parser_id, parser_version, parser_sha256}]`, and `change_scope: {allowed_paths}`. Include them in the canonical manifest hash. Unknown versions and unrecognized fields fail closed.
10. A signed reviewer registry has `{version, entries:[{principal, key_id}], signature}`; its digest is calculated from canonical entries, excluding the signature. `IndependentReview` adds `reviewer_key_id`. The gate validates registry signature, version and digest against the manifest, principal/key mapping, reviewer/author separation, and receipt signature.
11. Runner submits one exact-field signing request containing `{request_id, task_id, slot, attempt, epoch, manifest_sha256, candidate_head, commands:[{argv, exit_code}], parser_results, artifact_digests}`. The runner derives the head after execution. The signer authenticates the runner OS identity, accepts a request ID once, returns the original signature for an identical request, and rejects reuse with a different payload. Commands cannot access signer IPC.
12. Parser selection uses a trusted built-in catalog keyed by `(parser_id, version, sha256)`. The manifest can select only a catalog entry; caller-supplied parser callables are not accepted by the runner or gate.
13. External anchoring uses `read_latest()` and compare-and-append semantics. The store appends the event in SQLite, then CAS-appends the signed external checkpoint. Startup checks this before leases/gate operations. If the database is exactly one valid event ahead, writes remain locked while startup idempotently appends the checkpoint; any other mismatch or recovery failure remains locked pending operator recovery.
14. A diff check returns `{diff_sha256, changed_paths, verdict, reason}` from manifest digest, base head, candidate head, and allowed paths. Normalize paths; reject traversal, out-of-scope paths, blocked file classes, unsafe renames, and symlink changes. Bind this evidence to the required v2 receipt.
15. A probe receipt binds `{run_id, spec_sha256, nonce, checked_properties, result}` and is fresh for that run. Supervisor reconciliation and anchor recovery complete before lease acquisition. Idempotency keys bind both operation and payload: identical retries return the prior result; key reuse with a different payload fails.
16. Keep v1 signed bodies and hashes immutable. V2 validation is explicit; v1 evidence never passes a v2 gate. Any store migration preserves event/receipt bytes and chain hashes; failure leaves the store read-only and acceptance blocked. Do not reconstruct an external anchor from the database.
