# Change record 0017: S1 remediation tests and state-authority wording

## What changed
- `tests/vst/e1e4_helpers.py`, `test_e1_contracts.py`, `test_e2_gate.py`, `test_e3_store.py`, `test_e4_runner.py`, `test_e5_slice.py`, `test_e5_process_death.py`: rewritten and extended for the remediated contracts, gate, store, runner and slice (records 0015, 0016).
- `docs/sdlc/evidence/s1-remediation-e1-e4-test-run.md`, `s1-remediation-e5-test-run.md`: test-run evidence written by the test agents.
- `README.md`, `team/skills/sdlc-orchestrator/SKILL.md`, the master blueprint: state authority wording aligned with baseline decision BD-1 (the store is the authority, `docs/sdlc/STATE.md` is its generated view).
- `tools/vst/schemas/README.md`: the known-limits bullet about event-chain truncation rewritten to match the keyed anchor.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: entries for the remediation.

## Why
Four specialist reviewers returned MODIFY on 63e0e35; the remediation package and its tests close the findings that can be closed in S1. Items deferred to S2 stay listed in the decision log.

## Verification state
Test agents ran the complete sets on the working tree over 63e0e35: E1-E4 1105 passed and 2 skipped, E5 38 passed. Skips: POSIX permission bits and `os.symlink` (not permitted on this machine). The coordinator ran no tests. Not independently reviewed; the specialist re-review on the committed head and the operator's independent review are still pending.
