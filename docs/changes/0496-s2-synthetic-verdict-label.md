# Change 0496 — Disambiguate the synthetic gate result

Date: 2026-10-28

## What changed and why

Renamed the local candidate report field from `gate_verdict` to
`synthetic_gate_verdict`. A Python reviewer noted that the shorter name could be mistaken for E8 or
production approval even though the enclosing report already says E8 is not established. The test
contract now requires the explicit synthetic label and rejects the ambiguous key.

## Affected paths and contracts

- `tools/vst/slice.py::run_lifecycle_scenarios` report field name.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` contract assertion.
- No production dispatch, E5 evidence, external integration, or real E8 behavior changed.

## Verification and review state

- Previous exact focused run at `23c4a678358728fb7b65ceb84e2fe70a636f97ca` passed 5 tests; that
  result predates this field rename and does not verify the current revision.
- Python review at `91dfdeeec5b76dead42a773f7d98eb9ba7fcc676` found no BLOCKER/MAJOR and raised the
  INFO naming concern fixed here. Security review at that same head found no findings. This new
  exact revision needs focused re-execution and targeted Python re-review.
- Restricted process/crash, STOP, resume/restart, mutation, egress and real sandbox scenarios remain
  `NOT_RUN`.

## Ownership and next step

Codex owns implementation, review coordination and evidence reconciliation. The
functional-test-reviewer owns the assertion; e2e-runner owns the exact-head rerun. Python reviewer
rechecks the label fix; security reviewer has no findings on the prior exact diff. GPT-PM owns the
subsequent exact-head adjudication. Keep S2 and E8 open pending their separate acceptance gates.
