# Change 0498 — Require a fresh work directory for the synthetic helper

Date: 2026-10-28

## What changed and why

The security review found no security issue in the safe synthetic flow, but noted that the helper
accepted any caller-provided `workdir` and initialized repositories beneath it. A reused path could
collide with existing files. The helper now creates its work directory with `os.mkdir`, which fails
if that exact directory already exists. The test passes a new child path below its
`TemporaryDirectory` parent, and the context manager owns cleanup.

## Affected paths and contracts

- `tools/vst/slice.py::run_lifecycle_scenarios` requires a non-existing workdir and creates only
  that new root before creating its local Git/database fixtures.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` passes a fresh child under a disposable parent.
- `docs/S2_E8_SYNTHETIC_HARNESS_DESIGN_2026-10-28.md` records this boundary.
- No restricted process/crash, STOP, resume/restart, out-of-scope mutation, egress or real sandbox
  scenario is invoked.

## Verification and review state

- The prior exact focused run at `05a443c76b6453c48a103aa136576ba487c80b44` passed 5/5; this
  workdir-contract change requires a new exact-head focused run.
- Security recheck at `db811a4c6bf8e482ca47a897d06d8a7c9098c940` found no findings and noted the
  caller-provided workdir limitation addressed here. Python review at `05a443c76b6453c48a103aa136576ba487c80b44`
  found no findings. The current change still needs focused test execution and exact-head review.

## Ownership and next step

Codex owns implementation and Git/evidence coordination. The functional-test-reviewer owns the
fixture contract; e2e-runner owns the exact-head rerun; Python/security reviewers own the relevant
static reviews; GPT-PM owns exact-head adjudication. The operator owns actual sandbox/E5 evidence,
worker choice, and any deletion of old retained pytest temporary roots. Keep S2 and E8 open until
their independent system and integration gates are satisfied.
