# 0066 S2 bounded idempotent operation recovery

## What changed

- Added `Store.execute_external_idempotent`: append a durable pending operation intent in a short Store transaction, invoke the callback outside the SQLite transaction and external-anchor lock, and persist canonical completion in a later hash-chained event.
- An interrupted/failed call remains pending; retries must reuse the same operation and payload digest and invoke the local backend with the same idempotency key. Conflicting completed results fail closed.
- Added finite per-command timeouts for every Git subprocess used by `SyntheticOperationBackend`.
- Kept receipt creation on the existing atomic in-Store idempotency path.
- Rejects reuse of a completed manual-override action ID with a different signed record, both in the current Supervisor cache and in durable Store replay.
- Updated S2 S7.2/S7.3 contract, Known limits and VST-014/VST-017 backlog notes.

## Why

The fresh reliability review found S7.2 backend callbacks were invoked under a Store transaction and cross-process anchor lock, with no subprocess timeout. A hung Git process could indefinitely block unrelated Store work. The same review found a completed manual-override action could be replayed with a different valid signed record, causing the audit callback and breaker history to disagree. Review scope and exact evidence were `source HEAD 280e2d0a613a0b70252c13ce7afe85f22734f7d1`, documentation HEAD `4f8a0ca693a6045f9ede43a4d4f6fdbc9282bb2c`, GPT-6 Luna medium; the reliability finding was MAJOR for S7.2 and MINOR for S7.3.

## Design and compatibility

- Design alternatives and failure handling are documented in change record 0065.
- The existing append-only operations row and event stream are reused; no SQLite schema migration or receipt contract version change was made.
- `execute_idempotent` remains available for atomic internal database effects such as receipt insertion. External callers use the new method and must provide a backend that durably honors the operation key.
- Previously committed operation rows remain readable as completed results.
- Only the local synthetic Git backend is in this scope; no remote service or external candidate is added.

## Ownership

- Accountable task owner: operator.
- Executor: Codex.
- Implemented in response to the fresh reliability reviewer; post-fix review remains pending.
- Required runtime regression authorship/execution belongs to `functional-test-reviewer` and `e2e-runner`.

## Verification state

- Source HEAD before this change: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- No tests, checks, builds, CI, migrations, or backend runtime scenarios were run during implementation.
- Exact post-commit code identity and test-agent evidence will be recorded after the designated focused rerun.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not modified or staged.
