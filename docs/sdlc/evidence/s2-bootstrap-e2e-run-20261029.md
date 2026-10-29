# S2 bootstrap and stage-only focused test evidence

Date: 2026-10-29

## Scope and identity

- Repository: `D:\Repo\Virtual_scrum_team` (canonical project checkout).
- Source revision tested: `7e9c519` (`git rev-parse --short HEAD` at evidence capture).
- Test sources authored for this task: `tests/vst/test_s2_bootstrap_runtime.py` (SHA-256 `51A3BFBCC7FAB7B23013D865599BD23BE68C7B7EE2CF1DF26A4E55AFFADC6C20`) and `tests/vst/test_s2_stage_only_install.py` (SHA-256 `6D7AE8F4BA904B45B6AC923C6612FFE2903F772F1E1B9BD32C8B71832746EF6E`). They were untracked at capture; no commit was made.
- `docs/sdlc/evidence/s2-functional-test-run.md` was already untracked and explicitly out of scope; it was not read or changed.

## Results

| Acceptance | Result | Evidence and limits |
|---|---|---|
| Bootstrap apply/recover transition logic | PASS, 6 focused POSIX cases | Actual `tools.vst.bootstrap_runtime.apply` / `recover` logic and `runtime_bundle` validation run against disposable `tmp_path` fixtures. Cases cover a wrong exact review digest with no writes; exact selector and unit replacement while reporting no service activation or Store changes; recovery retaining staged files; all-path fingerprint preflight refusing third-party bytes without a partial restore; ordinary exception injection before a unit replacement followed by recovery; and rejection of malformed/stale manifests and an invalid old runtime tree. |
| Stage-only installer preflight and embedded Python | PASS, 7 focused cases | Parses the embedded Windows handoff Python and standalone shell-installer Python blocks. Executes the stage-only guard through a deterministic AST harness with mocked filesystem/systemctl boundaries. Covers complete inactive inventory, existing configuration, an activating unit, systemd job rows with the service name in the second column, and a populated cgroup. No installer was executed. |

### Windows focused run

Environment: Windows host, Python 3.14.3. `python -m pytest --version` did not produce version text in the captured shell output; this is `NOT_RECORDED`. The stage-only test file was run with:

```powershell
python -m pytest -q tests/vst/test_s2_stage_only_install.py
```

Result: `7 passed, 1 warning in 0.57s`. The warning is from the installed `pytest_asyncio` plugin: `asyncio.get_event_loop_policy` is deprecated. The POSIX bootstrap module intentionally skips on Windows because it tests UID/GID, POSIX links, modes and `fcntl` assumptions.

### Dedicated WSL2 POSIX fixture run

Environment: `Ubuntu-24.04` under WSL2; kernel `6.6.114.1-microsoft-standard-WSL2`; Python `3.12.3`; pytest `7.4.4`; command user `root` solely to exercise root-owned temporary fixtures. Source archive and the two untracked tests were streamed from the Windows host through `wsl.exe` stdin and extracted into a unique `/run/vst-e2e-<archive digest>` directory. There was no D: drive mount and no repository worktree was created in WSL. Pytest created its ordinary disposable fixtures under `/tmp/pytest-of-root`.

The WSL bootstrap command was:

```powershell
wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -I -S -c <stdin-archive-extractor-and-pytest-bootstrap>
```

The bootstrap validated and extracted the streamed tar, then ran this exact test command inside the extracted directory:

```text
/usr/bin/python3.12 -m pytest -q --tb=short <extracted-root>/tests/vst/test_s2_bootstrap_runtime.py <extracted-root>/tests/vst/test_s2_stage_only_install.py
```

Result: `13 passed in 1.25s` (6 bootstrap cases and 7 stage-only cases; exit code 0).

## Safety boundary and interpretation

- Bootstrap code ran against isolated temporary trees only. Module-local filesystem adapters mapped the fixed `/opt` namespace into the fixture; production path validation and apply/recovery logic remained under test. Parent checks and systemd inactivity were stubbed at the boundary; `systemctl` was mocked in the stage-only harness.
- No actual `/opt`, `/etc`, `/run` service state, systemd unit, cgroup, production configuration, Store, E5 provenance, or deployment target was changed or opened. No service was enabled, started, stopped, reloaded, or killed. No compiler, provisioning, dependency installation, or network download was performed.
- This proves focused transition/preflight behavior in deterministic fixtures, not a production installation or live service integration. Process-kill, crash/power-loss, restricted policy-selector, E8, and real host mutation scenarios remain `NOT_RUN`.
- The third-party-byte case changes only a disposable fixture file to verify fail-closed recovery; it is not a production or policy-selector mutation.
- No product/source defect was observed in these focused cases. This result does not close separate S2 runtime/E5, dispatch integration, functional-suite, specialist review, or exact-head approval gates.

## Reproduction commands

Windows focused stage-only command:

```powershell
python -m pytest -q tests/vst/test_s2_stage_only_install.py
```

WSL test command after streaming/extracting the source archive and the two test files:

```text
/usr/bin/python3.12 -m pytest -q --tb=short <extracted-root>/tests/vst/test_s2_bootstrap_runtime.py <extracted-root>/tests/vst/test_s2_stage_only_install.py
```
