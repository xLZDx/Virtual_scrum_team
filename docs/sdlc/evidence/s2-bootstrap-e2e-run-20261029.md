# S2 bootstrap and stage-only focused test evidence

Date: 2026-10-29

## Scope and identity

- Repository: `D:\Repo\Virtual_scrum_team` (canonical project checkout).
- Historical baseline source revision: `7e9c519` (`git rev-parse --short HEAD` at that earlier evidence capture).
- This follow-up adds cases to `tests/vst/test_s2_bootstrap_runtime.py` and `tests/vst/test_s2_stage_only_install.py`; both are working-tree modifications to frozen source head `c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`. Current test SHA-256 values are `CACDCF1B62181A01CD7C475EB907656CCD6632C77996D19A9857B44DD776E820` and `51BD33717D8E8FEE7B430D44960C1230008815D247902FF4E34D04361DF9765F`, respectively. They remain uncommitted.
- `docs/sdlc/evidence/s2-functional-test-run.md` was already untracked and explicitly out of scope; it was not read or changed.

## Historical baseline results (7e9c519)

| Acceptance | Result | Evidence and limits |
|---|---|---|
| Bootstrap apply/recover transition logic | PASS, 6 focused POSIX cases | Actual `tools.vst.bootstrap_runtime.apply` / `recover` logic and `runtime_bundle` validation run against disposable `tmp_path` fixtures. Cases cover a wrong exact review digest with no writes; exact selector and unit replacement while reporting no service activation or Store changes; recovery retaining staged files; all-path fingerprint preflight refusing third-party bytes without a partial restore; ordinary exception injection before a unit replacement followed by recovery; and rejection of malformed/stale manifests and an invalid old runtime tree. |
| Stage-only installer preflight and embedded Python | PASS, 7 focused cases | Parses the embedded Windows handoff Python and standalone shell-installer Python blocks. Executes the stage-only guard through a deterministic AST harness with mocked filesystem/systemctl boundaries. Covers complete inactive inventory, existing configuration, an activating unit, systemd job rows with the service name in the second column, and a populated cgroup. No installer was executed. |

### Historical Windows focused run

Environment: Windows host, Python 3.14.3. `python -m pytest --version` did not produce version text in the captured shell output; this is `NOT_RECORDED`. The stage-only test file was run with:

```powershell
python -m pytest -q tests/vst/test_s2_stage_only_install.py
```

Result: `7 passed, 1 warning in 0.57s`. The warning is from the installed `pytest_asyncio` plugin: `asyncio.get_event_loop_policy` is deprecated. The POSIX bootstrap module intentionally skips on Windows because it tests UID/GID, POSIX links, modes and `fcntl` assumptions.

### Historical dedicated WSL2 POSIX fixture run

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

## Follow-up on frozen source c2b1cd2

The accepted tests were expanded with ordinary-exception partial writes during journal preparation and while preserving selected units during recovery. A harmless subprocess test reproduces the installer's actual `-I -S -c` argument shape and checks the Python `sys.argv` indexing without launching WSL installation. The installer call passes `ExpectedHead`, `archiveSha256`, `transferId`, and stage-only flag after `-c` (`tools/qa/install_wsl_runtime.ps1:375-379`); its embedded code unpacks `sys.argv[1:4]` and reads `sys.argv[4]` (`:81-86`).

### Failure reproduction before journal I/O fix

Before source commit `5724ba8` was available, the two new WSL fixture cases reproduced the reported retry failures. This was a pre-freeze working-tree run; that exact dirty source snapshot was not hashed, so no exact commit identity is claimed for it. The observed errors were:

- Partial ordinary write of the temporary journal state left the transaction directory without `state.json`; retrying `apply` raised `FileNotFoundError` from `_require_no_pending_journal` instead of starting a new safe transition.
- Partial ordinary write of a deterministic retained-copy destination caused retrying `recover` to refuse with `ContractError: bootstrap transition refused: retained selected unit differs from the reviewed new fingerprint`.

These were reproducible injected I/O failures in `tmp_path` fixtures; no actual service or host path was involved. The two failures were the expected red cases before the source fix, not test defects or flakes.

### Post-fix Windows focused run

Environment: Windows host, Python 3.14.3. Command:

```powershell
python -m pytest -q tests/vst/test_s2_bootstrap_runtime.py tests/vst/test_s2_stage_only_install.py
```

Result: `8 passed, 8 skipped, 1 warning in 1.45s`. The bootstrap module's eight POSIX cases skip on Windows. The warning is the installed `pytest_asyncio` deprecation for `asyncio.get_event_loop_policy`.

### Post-fix dedicated WSL2 fixture run

Environment: `Ubuntu-24.04` on WSL2; kernel `6.6.114.1-microsoft-standard-WSL2`; Python `3.12.3`; pytest `7.4.4`; root solely for root-owned disposable fixtures. Source was streamed over `wsl.exe` stdin into a unique `/run/vst-e2e-<archive digest>-<random>` directory; no Windows drive was mounted and no worktree was created. Exact in-WSL command:

```text
/usr/bin/python3.12 -m pytest -q --tb=short <extracted-root>/tests/vst/test_s2_bootstrap_runtime.py <extracted-root>/tests/vst/test_s2_stage_only_install.py
```

Result at frozen source `c2b1cd2172a0b5db85247a6f414a4b1568a4fcb0`: `16 passed in 5.05s`, exit code 0. This includes both partial-write retry cases after source fix and the subprocess argv assertion.

### Python argument boundary result

Direct harmless command:

```powershell
python -I -S -c "import json,sys; head,digest,transfer_id=sys.argv[1:4]; stage_only=sys.argv[4]; print(json.dumps(sys.argv))" aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb cccccccccccccccccccccccccccccccc 1
```

Output:

```text
["-c", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "cccccccccccccccccccccccccccccccc", "1"]
```

The actual four post-`-c` arguments therefore occupy `sys.argv[1:5]` as expected. No installer or WSL command was invoked by this check.

## Safety boundary and interpretation

- Bootstrap code ran against isolated temporary trees only. Module-local filesystem adapters mapped the fixed `/opt` namespace into the fixture; production path validation and apply/recovery logic remained under test. Parent checks and systemd inactivity were stubbed at the boundary; `systemctl` was mocked in the stage-only harness.
- No actual `/opt`, `/etc`, `/run` service state, systemd unit, cgroup, production configuration, Store, E5 provenance, or deployment target was changed or opened by the focused test runs. No service was enabled, started, stopped, reloaded, or killed. Compiler metadata collection was performed separately and recorded in `s2-runtime-inventory-20261029.md`; no compilation, provisioning, dependency installation, or network download was performed.
- This proves focused transition/preflight behavior in deterministic fixtures, not a production installation or live service integration. Process-kill, crash/power-loss, restricted policy-selector, E8, and real host mutation scenarios remain `NOT_RUN`.
- The third-party-byte case changes only a disposable fixture file to verify fail-closed recovery; it is not a production or policy-selector mutation.
- The pre-fix partial-write red cases established two source defects, both corrected in commit `5724ba8` and independently verified by the 16-pass frozen-source run. This result does not close separate S2 runtime/E5, dispatch integration, functional-suite, specialist review, or exact-head approval gates.

## Reproduction commands

Windows focused stage-only command:

```powershell
python -m pytest -q tests/vst/test_s2_stage_only_install.py
```

WSL test command after streaming/extracting the source archive and the two test files:

```text
/usr/bin/python3.12 -m pytest -q --tb=short <extracted-root>/tests/vst/test_s2_bootstrap_runtime.py <extracted-root>/tests/vst/test_s2_stage_only_install.py
```
