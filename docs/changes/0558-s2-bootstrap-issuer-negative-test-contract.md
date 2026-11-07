# Change 0558: S2 bootstrap and integrated issuer negative-test contract

## State and authorization

Planning-only test contract. The functional-test-reviewer role owns this coverage design; Codex owns coordination and source completion. At the observed baseline HEAD `4314957`, S2 source coding was still active and the worktree already contained source changes in `tools/vst/store.py`, `tools/vst/supervisor.py`, `tools/vst/supervisor_service.py`, an untracked `tools/vst/root_dispatch_issuer.py`, and unrelated/current coordination artifacts. Those files were read only for contract context and were not edited here. No tests, checks, builds, CI, runtime commands, or test code were authored. The plan explicitly waits for root's final S2 code-freeze GO.

## Changed paths

- `docs/sdlc/test-plan.md`: appended TP-29–TP-38 covering fresh-only bootstrap atomicity/rollback, exact idempotency, history eligibility, zero-budget boundary, I01 key-class and journal behavior, exact issuance/grant provenance, admission new/replay semantics, repeated current-authority checks at grant/claim/reservation boundaries, and default-off authenticated RPC scope.
- `docs/changes/0558-s2-bootstrap-issuer-negative-test-contract.md`: this record.

## Contract basis and mapping

The coverage derives from accepted S2-3 AC-1/4 and S2-4 AC-2/3, change0552's fresh-only authenticated bootstrap contract, and I01-SRC-01 through I01-SRC-05 in the correlated source adjudication `docs/sdlc/evidence/s2-i01-integrated-source-adjudication-20261029.md`. Relevant original epic mapping is recorded per case in TP-29–TP-38: E1 authorization/key boundaries, E2 service/RPC isolation, E3 journal integrity, E6 assignment/budget/Runner boundaries, and E7 lifecycle/idempotency/recovery. These cases are source/disposable-fixture acceptance and do not independently accept S2-4 runtime behavior.

Cases use the cheapest boundary capable of falsifying the contract: disposable SQLite transaction integration for atomic Store behavior; deterministic signer-call instrumentation for at-most-once invocation; and isolated RPC fixtures for caller-role/operation scope. They assert durable state, exact byte identity, refusal, or absence of side effects. The final exact node selector allowlist must be written only after the source API stabilizes.

## Explicit limits

Do not claim process-crash recovery from seeded journal rows. Process kill/crash, power-loss durability, mutation, E8, restricted policy selectors, real root-key signing/provisioning/activation, E5, systemd/PID 1 authentication, and production owner-to-Runner outcomes remain prohibited or `NOT_RUN` as scoped in the updated test plan. No production request or real root credential may be used in the later source tests. Existing TP-01–TP-28 and their historical records were left intact; historical outcomes are not current-head evidence.

## Verification

Not run by instruction. No test or check command was executed. Status after this documentation edit: test plan authored for the requested scope; functional execution is `NOT_RUN` pending all-in-scope source coding completion and explicit root GO. No commit was created by this role.
