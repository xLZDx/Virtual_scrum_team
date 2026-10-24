# Change record 0022: S1 second remediation round, tests and documentation

## What changed
- Code of the second round is recorded in `docs/changes/0019` (contracts, gate), `0020` (store, runner, slice) and `0021` (Windows Job Object in the runner).
- `tests/vst/test_e1_contracts.py`, `test_e2_gate.py`, `test_e3_store.py`, `test_e4_runner.py`, `test_e5_slice.py`, `test_e5_process_death.py`: updated for the second-round rules and extended (deciding-attempt head rule, history findings, key distinctness, NFKC principals, artifact key paths, retry cap by worker-attributed failures, budget seeding and refusal, verified event anchor, `LEASE_EXPIRED_PARTIAL`, `extra_env` rejection, capture-incomplete exit -4, Job Object post-exit kill, three new slice scenarios).
- `docs/sdlc/evidence/s1-second-round-e1-e2-test-run.md`, `s1-second-round-e3-e4-test-run.md`, `s1-second-round-e5-test-run.md`: test-agent run evidence.
- `team/agents/reporting-analyst.md`, `team/skills/sdlc-metrics/SKILL.md`, `team/skills/sprint-ceremonies/SKILL.md`, `team/skills/sdlc-orchestrator/SKILL.md`, `governance/DEFINITION_OF_DONE.md`, `README.md`, `core/STATE.md`: one cutover wording for the state authority (store once in use, STATE.md its generated view), exit artifacts recorded as Documentation receipts or events (registry deferred to S2), `core/STATE.md` refreshed (remote `9b5b597`).
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: entries for the second round.

## Why
Four specialist re-reviewers returned MODIFY on 3e27720 with one common MAJOR (head checks applied to history and supervisor markers). The package fixes it and the smaller findings; deferred items stay deferred to S2.

## Verification state
Test agents ran their complete sets on the working tree over 5a749ee: E1+E2 813 passed; E3+E4 506 passed and 2 skipped; E5 rerun after the runner change recorded in its evidence file. Skips: POSIX permission bits and a POSIX/symlink-capability case. The coordinator ran no tests. Not verified: POSIX behaviour, real lease timeouts, Job Object nesting under a parent job, mutation checks (NOT_RUN by operator decision). Not independently reviewed after this round.
