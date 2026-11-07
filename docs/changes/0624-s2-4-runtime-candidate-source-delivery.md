# S2-4 current runtime-candidate source delivery

## Task and acceptance delta

Current ordered task: **S2-4 — current runtime/E5 and Owner-to-Runner qualification**. This
record covers the in-progress source/configuration delta prepared to make the next bounded
qualification executable. It does not close S2-4, approve S2, or authorize production activation.

The source candidate now has a deterministic archive for the exact pinned Git tree and installs
one root-owned, read-only task-source snapshot at the Runner working directory. The runtime
configuration and inventory bind the exact source, bundle, identities, and installed destinations.
Preflight permits only the exact systemd-masked WSL path with matching root device/filesystem; other
host and Windows-drive mounts remain fail-closed. The bounded launcher keeps one WSL child for its
protocol, and Supervisor recovery obtains one fresh bounded observation before readiness rather
than trusting only an old observation. No development checkout or per-sprint worktree is created;
development remains in `D:\Repo\Virtual_scrum_team`.

The bounded launcher and its WSL protocol adapter are
`tools/qa/run_s2_runtime_qualification.py` and `tools/qa/s2_runtime_qualification_wsl.py`; focused
mock-contract coverage is in `tests/vst/test_s2_runtime_qualification_harness.py`.

The candidate baseline is pushed HEAD
`aedf712c07eb0cc531852d18443faa497e19bb2d`; the current worktree contains uncommitted S2-4
changes. The origin of those pre-existing worktree edits is not established by this record.

## Verification evidence

- `e2e-runner` ran the six source-snapshot selectors recorded in
  `docs/sdlc/evidence/s2-4-task-source-snapshot-windows-owner-map-run2-20261030.json` and `.txt`:
  **11 passed, 0 failed**, exit 0, one existing pytest-asyncio deprecation warning, 7.41 seconds.
  This native Windows fixture mocks ownership metadata and `chown`/`fchown`; it is not live POSIX
  ownership or runtime proof.
- `functional-test-reviewer`'s bounded WSL recovery-loader selectors passed **9/9** on Ubuntu
  24.04 / Python 3.12.3 / pytest 7.4.4 using an exact temporary source archive. This proves the
  mocked recovery contract, not a live Supervisor runtime. Full records are linked from
  `docs/changes/0622-s2-4-masked-wsl-runtime-diagnosis.md`.
- Prior narrow masked-mount regression evidence is **5 passed**; the bounded runtime qualification
  harness contract is **4 passed**. These do not establish a current run-bound E5 result.
- Current-turn read-only `code-reviewer` and `security-reviewer` reviewed the dirty S2-4 code delta
  against `aedf712c07eb0cc531852d18443faa497e19bb2d`; neither found a new BLOCKER or MAJOR. Neither
  reviewer ran tests.
- Report integrity check:
  `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py D:\Repo\Virtual_scrum_team\reports --check`
  returned exit 0 (`all reports carry the mandated block`).

These results are limited to the exact scopes stated in their records. The Windows snapshot run
does not establish POSIX ownership, and no new current-candidate runtime/E5/Owner-to-Runner result
is claimed.

## Remaining acceptance and safeguards

S2-4 remains **IN PROGRESS**. Current run-bound E5 provenance, a real permitted Owner-to-Runner
result, and the bounded report-bound TestRun remain unproven. WSL POSIX snapshot execution and the
producer archive cross-check in WSL remain `NOT_RUN`. Restricted process-kill, crash/recovery,
mutation, E8, and policy selectors remain `NOT_RUN` under the accepted scope. No production
activation is authorized by this work.

The prior one-shot runtime authorization
`8ee40d1a-27a4-4e1b-9129-292a58959aa3` is consumed and must not be reused. Its fail-closed outcome
is documented in `docs/sdlc/evidence/s2-runtime-qual-8ee40d1a-outcome-20261030.md`.

## Owner and ordered next action

Owner: **Codex**. Deliver this reviewed S2-4 source/configuration delta with a normal task commit
and push, respecting the repository's enforced pre-push hook. Then request a fresh correlated
one-shot runtime decision bound to the pushed source/configuration/run identities. Only
`e2e-runner` executes that bounded scope. If fresh authorization is unavailable, or runtime
preflight refuses, retain the exact refusal and keep S2-4 open; do not reuse the consumed tuple,
bypass preflight, or start S2-5.
