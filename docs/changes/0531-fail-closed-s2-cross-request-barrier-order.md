# Change 0531: reject cross-request S2 barrier history interleavings

## Why

Fresh code review at exact HEAD `80b01c55c700d029e357297f1af920e3b3033683` found that the
validator checked each request's own `PENDING → ACK` order but did not require that request A be
acknowledged before a later request B is accepted. A contradictory, hash-valid history could
therefore be classified as fully acknowledged even if B was accepted while A remained pending.

## What changed

- Dispatch outcome reconstruction now verifies global event ordering: every accepted intent after
  the first must appear after the preceding intent's acknowledgement. Legacy histories with no
  protocol controls remain `LEGACY_UNRESOLVED`; a mixture of legacy and new controls is integrity
  failure.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- The prior focused run at `80b01c55c700d029e357297f1af920e3b3033683` passed 118/118 but did not
  cover cross-request interleaving. Exact command and environment are in the e2e-runner record for
  that head; this source correction remains untested.
- `code-reviewer` identified the finding as MAJOR. `reliability-reviewer` independently found that
  a pending result becomes permanently stuck if the Runner generation changes; a signed dispatch
  reconciliation path is not present. That recovery contract is pending GPT-PM adjudication; no
  bypass has been implemented.
- `functional-test-reviewer` owns a regression test for the interleaved history. `e2e-runner` must
  execute it after test source is frozen and this correction is committed.
- `security-reviewer` found no actionable issue in peer authorization/result binding at the reviewed
  head. This does not close the MAJOR findings above.
