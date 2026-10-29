# S2 Store-backed pub/sub E2E triage — 2026-10-28

## Result

**Suite: NOT_RUN (0 tests executed).** No production or host-level E2E test is safe/available in
this pass. The source implementation is committed at exact HEAD
`ec9aefe9444003a65af81f27eaf813b250e25c10`; worktree status at triage showed only the protected
pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`, which was not read or changed.

## Stack and source evidence

- Repository tests are Python/pytest under `tests/vst/`; no Playwright/Cypress configuration or
  package-based browser E2E stack was found by `rg --files -g "pytest.ini" -g "pyproject.toml"
  -g "setup.cfg" -g "tox.ini" -g "package.json" -g "playwright.config.*" -g "cypress.config.*"
  -g ".github/workflows/**"` (no matches).
- `rg -n "Supervisor|SO_PEERCRED|AF_UNIX|dispatcher|issue_dispatch|submit_dispatch|dispatch_authorized|persistent_runner" tests -g "*.py"`
  found the existing persistent-runner/Supervisor tests. These are source-level tests and do not
  establish a deployed dispatcher runtime.
- `rg -n "dispatcher_service|DISPATCH_INTENT_ACCEPTED|next_dispatch_intent|submit_dispatch_intent|issue_dispatch_intent_grant" tests -g "*.py"`
  found no committed dispatcher-specific E2E test at this head.
- The new Supervisor/Runner service path requires POSIX `SO_PEERCRED`, kernel `SO_PEERPIDFD`, Linux
  cgroup inspection, and a root Supervisor (`tools/vst/supervisor_service.py:98-103,164-170,295-297`;
  `tools/vst/runner_service.py:204-206,444-449`). Dispatcher `main` also rejects non-POSIX execution
  (`tools/vst/dispatcher_service.py:93`). This triage ran in the Windows PowerShell checkout, not in
  a provisioned Linux service runtime.
- The current prerequisite record says root service configuration/credentials, a current signed E5,
  and sandbox provenance are absent (`docs/sdlc/evidence/s2-prerequisite-absence-confirmation-20261028.md`).

## Why execution is `NOT_RUN`

The actual system journey requires provisioned root service configuration and credentials, the
authenticated `dispatch_owner` identity mapping, migrated/current Store state, an installed matching
runtime, active Supervisor and Runner services, and a real run-bound E5 provenance record. The
current GPT-PM decision authorizes source tests but does not authorize migration application, key
provisioning, service activation, or a real dispatch. This triage was explicitly limited to not
modifying WSL/config/keys, not applying migrations, not enabling or starting units, and not
dispatching a task. Therefore no production E2E command was attempted.

## Scope and next owner

- No tests/checks/builds/migrations were run; no service or WSL state was touched.
- No new E2E test was authored because this role cannot truthfully call a mocked Windows/source-level
  test a production POSIX E2E result. The designated functional-test-reviewer owns mapped source
  tests that do not require runtime provisioning.
- Codex owns coordinating any later allowed runtime setup. GPT-PM owns adjudicating its exact scope;
  the operator owns only any genuine human network-policy attestation required for E5. Until these
  dependencies exist, dispatcher runtime acceptance remains `NOT_RUN`, and `S2-DISPATCH-M01` remains
  open.
