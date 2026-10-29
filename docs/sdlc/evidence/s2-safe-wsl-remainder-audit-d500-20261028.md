# S2 safe WSL remainder audit — exact source/test HEAD `d500179` — 2026-10-28

## Result

The designated `e2e-runner` performed a read-only triage of remaining WSL/POSIX acceptance at
source/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`. It found **no additional selector
that can be run within the current restrictions**. No tests were run, no files were modified, and
the protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was untouched.

## Candidate disposition

| Candidate | Why it cannot run under current scope | Status |
|---|---|---|
| `test_posix_worker_cannot_read_signer_or_key_file` | Creates synthetic key files and launches a child under `vst-worker`; the current task excludes key/worker scenarios without the authorized service configuration. | `NOT_RUN` |
| `test_runner_drops_uid_change_capabilities_before_worker_command` | Requires runner UID/capability setup and launches a worker command. | `NOT_RUN` |
| Reviewer-boundary and external-anchor selectors | The remaining candidates write temporary fixtures; the E2E audit found they cannot be separated from the current mutation restriction within this bounded pass. | `NOT_RUN` |
| E4 process-containment selectors | Explicitly excluded process/descendant containment scenarios. | `NOT_RUN` |
| Remaining persistent runtime acceptance | Requires root Runner configuration/credentials, service activation, manifest execution or fresh E5 evidence. | Blocked on operator-owned prerequisites |

## Assignment and next action

- Owner: operator for root-owned Runner configuration/credentials and any required authorization for
  the specific service/worker scenarios; Codex coordinates and preserves the acceptance record.
- Next: provide those prerequisites or retain the dependent criteria as `NOT_RUN`; then the
  designated `e2e-runner` can execute only the newly authorized selectors.
- No service activation, manifest run, worker job, key creation, E5 signature, network probe,
  process-kill, crash/recovery, mutation, E8 or policy selector occurred.

This audit does not change GPT-PM's `NOT APPROVED` verdict for S2 Phase 8.
