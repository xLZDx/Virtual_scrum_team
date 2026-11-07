# 0079 S2 hook-free Git pack publication E2E

## What changed

- Added E2E coverage for safe source-to-bare publication in `tests/vst/test_s2_runner_lifecycle.py`.
- Falsified worker-controlled `pre-push` hook execution: a positive control proves the temporary hook writes its marker for ordinary Git push; supervisor publication transfers a source-only candidate without changing that marker.
- Added coverage for malicious repository-local pack settings and hostile Git config environment variables; checks the source pack command's fixed resource settings and filtered environment.
- Added source-only object transfer, fast-forward acceptance, non-fast-forward branch rejection, repeated PR operation, changed-payload rejection, and rejection of a pre-existing PR ref that points at a different commit.
- Added a cumulative target-object-storage cap test that proves rejection occurs before pack subprocess launch, plus cross-process target lock timeout/release coverage.
- Adapted timeout/restart coverage to inject `TimeoutExpired` at the `pack-objects` Popen boundary before any child process starts. It verifies durable PENDING, same-key retry after Store restart, target ref completion, and backend payload conflict handling.
- Added Windows and selected-WSL2 evidence, prior red diagnostics, exact skip boundaries, and limitations in `docs/sdlc/evidence/s2-e2e-hook-free-pack-1ef3fee.md`.

## Why

Security review found that source-repository Git push could execute worker-controlled pre-push hooks under the runner identity. Follow-up reliability review required bounded pack settings, bounded cumulative target storage, and safe target-object-write serialization. Tests exercise the local backend boundary without a real remote or prohibited process-kill/overflow-cleanup paths.

## Scope and compatibility

- No production source code or schema was changed by this E2E commit.
- All repositories are disposable local synthetic repositories. Hook control writes only a temporary marker.
- Timeout failure is injected before creating a child. The target-lock child exits normally through stdin. These tests do not invoke `process.kill()`.
- The storage-cap test proves preflight rejection before pack child creation. Post-start overflow cleanup remains `NOT_RUN` because that path may call `process.kill()`.

## Verification

- Source HEAD: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Windows command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Windows environment: Python 3.14.3, pytest 8.4.2, Windows 11 build 10.0.26300-SP0.
- Windows result: exit 0; 76 passed, 14 skipped, 1 pytest-asyncio deprecation warning; 90 total cases. Pytest reported 150.80 seconds.
- Selected WSL2 result: one POSIX target-lock contention test passed as UID 997 (`vst-runner`), Python 3.12.3, pytest 7.4.4, Ubuntu 24.04.5 under WSL2 kernel 6.6.114.1.
- The runner source and test file copied to WSL matched the Windows SHA-256 values recorded in the linked evidence. The repository HEAD moved from `1ef3fee` to `060a7dc` when the functional agent committed record 0078; `tools/vst` remained identical to the source HEAD.
- The 14 platform skips and overflow-cleanup `NOT_RUN` scenario are explicit in the evidence. No process-kill, kill-table, build, CI, migration, or unrelated suite was invoked.
- Historical test defects and intermediate runs are distinguished from final acceptance in the evidence; no result is classified as a flake.

## Ownership

- Accountable task owner: operator, by delegated task.
- Executor and test author: Codex E2E runner (`gpt-6-luna`, medium effort).
- Product source was implemented in revisions leading to `1ef3fee`; this commit adds only tests and evidence.
- No canonical technical service owner for the synthetic Git backend is established in project records.

## Next action

Coordinator may reconcile this E2E evidence with functional record 0078. Keep overflow cleanup, process-kill/kill-table, and full E4 containment acceptance marked `NOT_RUN` until those restrictions or platform dependencies change.
