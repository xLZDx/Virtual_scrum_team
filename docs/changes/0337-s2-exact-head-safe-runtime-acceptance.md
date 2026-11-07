# Change 0337 — Record safe S2 runtime acceptance at the corrected code head

## Summary

- Added exact-head runtime evidence for the safe S2 remainder in the existing dedicated Ubuntu 24.04 WSL2 environment.
- Reconciled the S2 E4/E5 status with permitted identity-boundary and Store lifecycle results, without claiming full platform containment or production sandbox acceptance.
- Added the S5 dependency row to `core/BACKLOG.md`; S5 remains prepared and blocked by S2/S4 gates and missing in-scope AEVE identity/interface evidence.
- No source or test code was changed.

## Runtime evidence

- Exact code/test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- Canonical repository HEAD during the latest archive runs: `bc1f015b39ead97f30444fc6fc72a8bc35febd0c`; `tools/vst` and `tests/vst` have no diff from the exact code/test commit.
- Designated role: `e2e-runner`, model `gpt-6-luna` by role configuration; effort for this pre-existing resumed agent thread is `NOT_VERIFIED` from available metadata.
- Environment: Ubuntu-24.04 WSL2, root test harness UID 0, Python 3.12.3, pytest 7.4.4.
- Newly run safe remainder: contract gate 38 passed / 5 already-covered cases deselected; operation recovery 4 passed; synthetic sandbox-probe contracts 14 passed / 8 excluded; safe runner lifecycle 56 passed / 24 deselected. The four groups totaled 112 passes, no warnings. The evidence file records the exact commands and exclusions.
- Prior, not repeated at this continuation step: full DiffGate 22 passed; Store lifecycle 19 passed; contract DiffGate 5 passed; runner provenance 7 passed; four permitted POSIX identity/anchor selectors passed.
- Durable evidence: `docs/sdlc/evidence/s2-permitted-posix-runtime-evidence-f0bbac8-20261026.md`.
- One runner-lifecycle invocation collected no tests because its temporary archive had already been removed (`chdir` failed). It was recreated from the same exact Git commit and the safe selector command then passed; no test failed in that first invocation.

## Acceptance limits

These results do not establish real Windows Job Object nesting/descendant cleanup, POSIX process-group/descendant termination, the current-head signed sandbox inventory/egress/resource/workspace controls, or full E8 crash/resume. Process-kill, kill-table, mutation testing, process-group cleanup and full crash/resume selectors were not run under the active policy. The historical signed E5 probe at product source `280e2d0` is not current-head run binding. S2 Phase 8 therefore remains NOT APPROVED despite no open source BLOCKER/MAJOR from the latest correlated GPT-PM review.

## Next action

Codex coordinates a fresh exact-head sandbox probe where the existing authorized environment permits it; `e2e-runner` owns test execution. Preserve `NOT_VERIFIED` for controls that cannot be observed. Keep S2, S3 and S4 gates open and do not implement S5 until its documented dependencies and in-scope AEVE identity/interface evidence are resolved. No push, PR, merge, policy change, or waiver is authorized by this change.

Change: 0337
Executor: Codex
Accountable owner: Operator

