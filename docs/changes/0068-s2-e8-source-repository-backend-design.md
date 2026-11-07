# 0068 S2 E8 source repository backend design

## Goal

Make the synthetic supervisor backend publish a candidate commit from the isolated worker repository to the local bare remote, with bounded Git execution and supervisor-only authority.

## Current behavior and constraints

- `run_lifecycle_scenarios` creates a worker source repository and a separate bare target. Candidate commits exist only in the source.
- `SyntheticOperationBackend` currently knows only the bare target and attempts `git --git-dir <bare> push <bare> <head>:<ref>`. It cannot transfer an object that exists only in the source repository.
- The worker has no push/PR credential or path. The supervisor may operate only on the local synthetic bare remote.
- Git subprocesses remain finitely timed. No real remote, external network, candidate acquisition, or process-kill scenario is included.

## Options

1. Copy candidate objects from source to target with low-level Git plumbing, introducing object-format and ref-atomicity details into the adapter.
2. Give the trusted backend an explicit `source_repo` and run `git -C <source_repo> push <bare_target> <head>:<ref>`. **Chosen:** Git local transport moves the referenced commit and objects coherently while the worker remains without publish authority.

## Design

- `SyntheticOperationBackend` accepts an explicit source repository and target bare repository. Every target inspection and source push uses the finite configured timeout.
- Candidate branch and pull-request refs are created by pushing the exact requested head from source to target. Existing idempotency-key/payload binding and target-ref conflict checks remain in place; no force push is added.
- The E8 harness provides the worker repository at initial construction and after restart. The backend does not copy or check out files.
- The generic Supervisor backend protocol is unchanged. Store pending/completion behavior from records 0066-0067 remains unchanged; no schema or receipt version change.

## Failure handling and rollout

- Missing source repository or missing head fails through the bounded Git command; the Store retains `PENDING` and the caller gets no success result.
- Timeout remains retryable only with the identical key and payload. The target's durable idempotency binding and idempotent ref update prevent a second logical effect.
- A target ref already bound to a different head is rejected; no overwrite is permitted.
- The change is internal to the synthetic harness. Reverting the code commit restores the prior implementation.

## Verification and ownership

- `e2e-runner` owns focused local bare-remote cases: head exists only in source, timeout then same-key retry, restart completion, and conflicting payload.
- `functional-test-reviewer` owns focused method/contract regressions where applicable.
- Both agents execute only after code is complete. No checks run during implementation.
- Operator is accountable for the delegated sprint; Codex is executor. No named technical service owner is established by canonical sources.

## Unknowns

- Git local-transport timeout behavior across supported platforms remains for the designated E2E agent to establish.
