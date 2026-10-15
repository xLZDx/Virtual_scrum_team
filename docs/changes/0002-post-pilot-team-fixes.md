# Change record 0002: post-pilot team fixes

## What changed
- `team/agents/functional-test-reviewer.md` synced with the global definition (maxTurns 25).
- `core/BACKLOG.md`: VST-001 done, VST-004 note, VST-007 and VST-008 added.
- `core/DECISION_LOG.md`: entry "Team fixes after the RQDO pilot".
- Global (outside this repository, snapshot kept): maxTurns raised for code-explorer, code-architect, tdd-guide, e2e-runner, functional-test-reviewer, security-reviewer, doc-updater; "Reporting discipline" section added to security-reviewer, silent-failure-hunter, reliability-reviewer.

## Why
In the RQDO pilot the test, security and design agents repeatedly stopped at their turn limit, and reviewers sometimes returned findings as titles only, each time costing a resume round.

## Verification state
`agentctl.py --strict`: no new errors (one pre-existing ERP context-size error). `run_eval.py --router`: 15/15 passed. No agent behavior was re-run after the change.
