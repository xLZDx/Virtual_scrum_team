# Change 0548: Read-only S2 authenticated assignment basis

## State

Implemented in this coding pass; no tests, checks, or runtime acceptance were run. The source is
fail-closed until a separately reviewed authenticated assignment writer, root-owned policy, and
dedicated delegated_issuer peer are installed. Existing deployment configurations keep their
previous schema and do not enable the feature.

## Why

The read-only issuer needs provenance stronger than a legacy owner string or lease row. It must
bind one exact authenticated assignment operation to the append-only Store history and then
recheck current Store authority without creating a nested SQLite transaction.

## Changed contracts and paths

- Added tools/vst/assignment_basis.py with closed validators for root policy, handoff, request,
  and response; the module has no signing key, persistence, or assignment writer.
- Refactored Store.execution_grant_basis() to delegate its existing validation and result
  calculation to _execution_grant_basis_locked(). Its public signature and preflight checks stay
  unchanged.
- Added Store.authenticated_assignment_basis(). It reads the operation row, exact supervisor
  NOTE event, complete keyed event chain, configured external anchor, supervisor record/event
  correspondence, consumed probe, and live task/owner/lease basis under one read snapshot. It
  refuses absent or legacy operation names and checks the canonical handoff result and its digest.
- Added Supervisor.assignment_basis(), which uses only constructor-supplied root policy and the
  configured active-generation provider. Callers cannot select a task, owner, policy, lease, or
  generation.
- Added the optional delegated_issuer RPC role, with exactly assignment_basis. It is enabled
  only when the fixed root policy path and its exact SHA-256 pin are both present in the root
  service configuration and the peer identity matches that policy. Existing peer allowlists and
  the default deployment schema are unchanged.

## Decisions and limits

- The authenticated assignment mutation endpoint, role, producer, keys, signing, provisioning,
  database migration, and E5 integration were not added.
- A valid row cannot be produced by this change. The reader therefore refuses all legacy records
  and reports no basis until a separate writer creates the exact operation and linked event.
- The current policy contract carries a revocation_id but does not define a separate revocation
  registry. Each request reloads the fixed root-controlled policy and requires it to equal the
  startup config's exact digest pin. Removal, unreadability, or any replacement fails closed.
  Per-assignment revocation is not supported; revoking one assignment requires replacing the
  whole pinned policy.
- The handoff contains the exact bootstrap request. The reader validates its manifest with the
  repository TaskManifest validator, checks the task/story/slot against the root allowlist,
  recomputes the domain-separated operation key, and recomputes the Store payload digest from the
  request, kernel-mapped bootstrap peer, and policy digest.
- Change 0549 adds the handoff's required service generation and checks both it and the current
  Supervisor run ID inside the Store snapshot. Older handoffs are not upgraded.

## Verification

- Tests and checks: NOT_RUN; explicitly deferred until coding is complete and the designated
  functional-test reviewer takes ownership.
- Runtime acceptance: NOT_RUN; the authenticated writer and root-owned deployment policy are
  absent from this bounded change.
- No commit was created.
