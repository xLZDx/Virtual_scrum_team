# S2 bounded source and fresh-only writer design review

Sprint: 39b7cc253f5d

Owner: Codex (coordination); GPT-PM (source/architecture adjudication).
Frozen current source: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`.

## Actual independent role evidence

1. `s2_runtime_code_review`, code-reviewer, gpt-6-luna medium: two valid journal retry MAJORs,
   corrected in 5724ba8 and focused rechecked against 3d5f6c2. Both resolved. Initial Python
   argv-index assertion was explicitly retracted; actual subprocess test confirms existing shape.
2. `s2_runtime_security_review`, security-reviewer, gpt-6-luna medium: no reachable source
   BLOCKER/MAJOR in runtime/candidate-contract source 9c1be0f..7e9c519. No runtime claim.
3. `s2_basis_database_review`, database-reviewer, gpt-6-luna medium: no reachable source
   BLOCKER/MAJOR in read-only Store basis diff 5724ba8..3d5f6c2; consistent read snapshot,
   complete chain/anchor/journal/probe/live authority and run/generation binding. No migration.
4. `s2_basis_security_review`, security-reviewer, gpt-6-luna medium: no reachable source
   BLOCKER/MAJOR in that read API; optional issuer-only role and exact current root policy.

Source tests are independently recorded: WSL 36 for source plan/bundle/candidate machine
contracts, WSL 16 for journal/staging fixtures, Windows and WSL 23 for the new basis plus two
current Store regressions. They are separate commands at their declared revisions, not one
full-suite or deployed-head run. Exact evidence is linked from `docs/sdlc/verify-evidence.md`.

## Fresh-only writer design correction

The new addendum in `docs/sdlc/S2_AUTHENTICATED_ASSIGNMENT_BASIS_DESIGN.md` restricts bootstrap
to an absent story/task/history and attempt 1, under exact root policy/task/manifest/slot/budget/
TTL/runner settings. One existing `execute_idempotent` transaction uses connection-taking locked
helpers, never nested public transactions, and commits the full assignment, authenticated
handoff, idempotency row and event together. Any failure rolls back. Existing legacy public lease
retry/budget marker semantics remain unchanged and are proven inapplicable in the fresh path.
The kernel-derived bootstrap peer and root-derived current policy/run/probe/generation are
rechecked at the write boundary. Exact committed replay returns the prior result without TTL
renewal or reassignment; conflicting or uncertain outcomes fail closed. Legacy adoption is refused.

Focused database recheck of the addendum: prior transaction concern resolved at contract level,
no remaining database MAJOR in this design slice; sufficient for bounded SOURCE implementation
subject to security review and GPT-PM GO. Focused security recheck: all four reported design
requirements addressed, no additional design correction; exact remaining gate is GPT-PM SOURCE
GO, then review/tests of the actual implementation before any enablement.

These are actual role results, not simulated reviews or production approvals. No writer source,
new signing key/service, policy configuration, machine E5 acceptance, deployment, push or PR is
authorized by this record. Current operator E5 remains unchanged. Codex must obtain the explicit
SOURCE decision, implement only that scope, then test and review the exact code.
