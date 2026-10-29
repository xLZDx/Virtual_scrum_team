# Change 0473 — Correct S2 runner retry authority and egress boundary

## Why

Fresh architecture and security reviews of committed S2 HEAD
`378df7260d8654f396ae1b45eaa9462d4bb4b88f` found that the persistent runner could strand
a pre-reservation claim, could admit a receipt-chain attempt gap inconsistently, could issue a
run whose manifest timeout exceeded the remaining owner/lease authority window, and lacked a
private network boundary. Operator reconciliation also had no service transport. A production
coordinator call site remained absent and must stay a separate acceptance blocker.

GPT-PM's correlated clarification `b84e73a1-55ac-47b0-87f8-20261028f002` /
`8cc3b2ca-fc98-4d8a-98ee-120579a9cde6` permits a receipt gap only when every omitted attempt
has exact authenticated `NO_EXECUTION_PROVEN` from `PENDING`, or exact signed `EFFECTS_RESOLVED`
from `EXECUTION_RESERVED`, and a separate successor lease/grant is valid. It forbids fabricated
receipts, bare `INDETERMINATE`, unresolved/rejected resolutions, and migrations.

An earlier six-finding PM response was returned by `gpt_await_reply` for request
`a7126c4d-8ef2-4d91-9c83-20261028f001`, but its durable Bridge job ended `uncertain` without a
reply ID. It is recorded only as preliminary design input, not as a correlated approval or final
gate. The later correlated clarification above resolves the only ambiguity exposed by functional
testing.

## What changed

- `tools/vst/store.py` records an append-only, exact-claim `NO_EXECUTION` disposition only for
  an authenticated runner daemon's still-`PENDING` claim. An existing `EXECUTION_RESERVED` claim
  cannot use this path. Recovery marks predecessor `PENDING` as no-execution and keeps a reserved
  predecessor ambiguous.
- One Store predicate verifies successor eligibility for exact no-execution or signed
  `EFFECTS_RESOLVED` history. Lease continuation, grant basis, claim, reservation, receipt append,
  gate evidence, and receipt-history replay use the same predicate. Real receipt digests remain
  linked; no synthetic receipt is created.
- Grant issue, claim, and reservation require the complete manifest execution timeout plus a
  five-second completion margin to fit before both story-owner and lease expiry. A required run
  is refused when the authority window is too short; its manifest timeout is not silently reduced.
- `tools/vst/supervisor_service.py` provides a closed versioned operator-only reconciliation
  operation behind an optional, distinct, pinned peer. The deployed configuration remains
  unchanged: no operator peer, account, or key was provisioned or activated. Dispatcher, runner,
  and signer roles do not receive this capability.
- The fixed runner systemd unit uses `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX`, and
  `RestrictNamespaces=yes`. These source directives do not establish effective WSL/systemd
  egress behavior, inherited descriptors, or forwarding-service absence.
- `tests/vst/test_s2_persistent_runner_service.py` adds focused cases for safe receipt gaps,
  claim terminalization, authority-window feasibility, and operator-role isolation.

## Affected contracts and files

Source: `tools/vst/store.py`, `tools/vst/gate.py`, `tools/vst/execution_grant.py`,
`tools/vst/supervisor.py`, `tools/vst/supervisor_service.py`, `tools/vst/runner_service.py`,
`tools/vst/systemd/vst-runner.service`.

Tests: `tests/vst/test_s2_persistent_runner_service.py`.

Evidence: `docs/sdlc/evidence/s2-adjudicated-runner-regressions-20261028-attempt1.md` records
the first failed run and its exact finding; `docs/sdlc/evidence/s2-adjudicated-runner-regressions-20261028-attempt2.md`
records the corrected four-group run.

## Verification state

The assigned `functional-test-reviewer` ran the exact commands and interpreter in attempt 2 at
base HEAD `378df7260d8654f396ae1b45eaa9462d4bb4b88f` with the working source/test diff:

- Persistent runner module: 56 passed.
- E1 contract gate: 32 passed.
- E2 runner lifecycle: 38 passed.
- E6 diff gate: 22 passed.
- Total: **148 passed, 0 failed, 0 skipped** across four commands; each emitted one
  `pytest-asyncio` deprecation warning. Exact selectors, commands, environment, source/test hashes,
  and limitations are in the attempt-2 evidence file.

The tracked source/test diff SHA-256 at the evidence cut was
`f9877b26a17d6c00102682cc6e8b9a79765386d57d228e7c8ae8183d0b0041f8` (80,864 bytes). The
test agent also recorded per-file hashes in its evidence file. One incidental `git diff --check`
was run by the implementation agent during source inspection and produced no output; it was not
used as final acceptance evidence.

These focused tests use in-memory Store fixtures, fake clocks, and fake RPC identity. They do not
prove live POSIX/systemd, WSL network isolation, inherited-FD/forwarding absence, Windows process
containment, full E5 inventory, or production coordinator integration. Prohibited process-kill,
crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`. S2 Phase 8 remains
`NOT APPROVED`; no final exact-head GPT-PM gate, push, PR, or merge is claimed.

## Remaining acceptance

- `S2-DISPATCH-M01`: a production coordinator or durable assignment source is still absent in this
  repository. No scheduler, CLI, spool, or second assignment authority was added.
- Runtime qualification must test the committed unit boundary and permitted WSL/POSIX behavior;
  a unit directive alone is not E5 PASS.
- E5 requires its run-bound system/network evidence and actual authorized operator attestation;
  Codex does not create a human signature.
- The optional reconciliation RPC remains inactive until a distinct operator peer and its
  independently provisioned credentials are supplied.
- Fresh specialist review and exact-head GPT-PM final gate remain required after the final
  committed source/evidence head.

