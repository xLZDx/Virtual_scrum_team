# Change 0454: contain distinct-UID POSIX workers in a delegated cgroup

## What changed

- Added a unique cgroup-v2 child scope under the runner's delegated systemd subtree for distinct-UID POSIX commands.
- Added a fixed-environment exec gate. The parent sends the worker allowlist environment as pipe data, attaches the gate to its scope, and only then releases the command.
- Fail closed if delegation/control files, attachment, or confirmed cleanup are unavailable. Cleanup kills the cgroup, waits for `populated 0`, removes it, and retries an unconfirmed result once in finalization.
- Kept Windows Job Object and same-UID POSIX compatibility paths unchanged; the all-descendant acceptance guarantee is limited to distinct-UID POSIX workers.
- Added focused fake-boundary coverage and updated the S2 design, sandbox contract, backlog, decision log, lessons, and state.

## Why

The authorized cross-UID timeout selector at source/test HEAD `161dcc7838b2bd05f01f485dab38a37cba9d82b2` failed: the worker UID 999 descendant continued writing after runner UID 997's process-group cleanup. A broad `CAP_KILL` would let the runner signal processes outside the worker tree; a custom privileged helper would add a new root trust boundary. The existing systemd-delegated cgroup-v2 boundary permits a per-command kill scope without either expansion.

## Affected contracts and paths

- `tools/vst/runner.py`: distinct-UID POSIX launch, gating, scope kill and cleanup.
- `tests/vst/test_s2_runner_lifecycle.py`: fail-closed and gate-ordering tests mapped to S2 E4.1 / VST-013.
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `docs/SANDBOX_SPEC.md`: launch and deployment contract.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md` and generated `governance/DOCUMENT_REGISTRY.md`.

## Decisions and review

- Rejected broad `CAP_KILL` and a custom privileged root helper; selected a runner-owned per-command delegated cgroup.
- `architect` reviewed the design. It found the initial gate could inherit loader variables before cgroup attachment and that the same-UID fallback exceeded the stated guarantee. The design now requires a sanitized environment before the first `setpriv` exec, sends worker environment only over a separate FD, and scopes the guarantee to distinct-UID POSIX. A second review confirmed these issues closed.
- Reviewer: `architect`; model GPT-6 Luna; effort medium; read-only design review. This is not the post-test source review.

## Verification state

- Test author: `functional-test-reviewer`.
- Pre-commit focused command: `python -m pytest -q tests/vst/test_s2_runner_lifecycle.py -k 'distinct_uid_worker_refuses or distinct_uid_cgroup_gate or distinct_uid_attach_failure'`.
- Result: 5 passed, 85 deselected; one pytest-asyncio deprecation warning; exit 0. The first run found a reversed pipe-end assignment; Codex corrected it and the focused rerun passed. This run used an uncommitted working tree based at HEAD `47cdc4804d881e62cacacb1fba1006d23791529b`; it is provisional, not exact-commit acceptance evidence.
- Exact-commit functional rerun and actual Ubuntu-24.04 WSL UID 997/999 delegated-cgroup E2E are pending. No test is upgraded to PASS from these mock-based selectors.
- No CI/build/migration, broad process-kill capability, persistent service deployment, or S2 closure is claimed.

## Ordered next steps

1. Codex: commit this source/test/design change with its generated registry entry.
2. `functional-test-reviewer`: rerun the focused selectors at the exact commit.
3. `e2e-runner`: run only `test_posix_worker_timeout_kills_descendant_across_uid_boundary` under the existing bounded Ubuntu-24.04 unit with `Delegate=yes`; capture cgroup path, identities, capabilities, exit and cleanup.
4. Codex: fix any valid defect, update evidence and rerun the impacted exact-head selectors.
5. After E4.1/E4.2 are complete, continue the remaining S2 acceptance in sprint order; keep E5-E8 system and operator-only attestations distinct.

## Attribution

Source and records: Codex. Test authoring and focused execution: `functional-test-reviewer`. Design review: `architect`. Real WSL E2E remains assigned to `e2e-runner`.
