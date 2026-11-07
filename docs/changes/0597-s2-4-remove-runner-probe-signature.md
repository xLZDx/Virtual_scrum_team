# Change 0597 — Remove Runner signing from the probe path

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.1, ordered child task of S2-4

## Accepted baseline and delta

Baseline HEAD: `473e559d3c82405cbe11d4969439c6760840675b` on
`s2-canonical-continuation`; upstream initially matched. The worktree already contained the
S2-4 runtime-bundle candidate and unrelated/protected untracked evidence. Those files were not
staged or overwritten by this task.

At resumption, the source diff described below was already present; its earlier authoring action is
not verified in this turn. This turn requested the focused test run and read-only security review,
reconciled their results, and added this delivery/checkpoint record. The functional-test reviewer
made the scoped test-only cleanup to remove a now-irrelevant fake probe signer from the fixture.

The prior startup path required a probe-specific Runner signing key even though the non-root probe
cannot authenticate itself to Supervisor without starting the Supervisor/signing service first.
This change removes the probe-only key and signature APIs while retaining the bounded environment
measurement contract and separately verified root network-policy attestation.

## Implementation

- `tools/vst/preflight.py`: replaced signed-probe verification with strict unsigned schema and
  run/spec/nonce validation, including mount, interop, UID, socket, and reserved-target fields.
- `tools/vst/signer.py`: removed only the probe signing purpose and API; unrelated Runner receipt
  and DiffGate signing remain.
- `tools/vst/slice.py`, `tools/vst/supervisor.py`, and
  `tools/vst/supervisor_service.py`: removed probe-key plumbing and the `probe_key_path` config
  requirement. Supervisor still validates the exact inventory, verifies the operator-signed
  network-policy attestation, and stores the consumed evidence digest in Store.
- Runtime configuration candidate no longer declares `probe_key_path`; its manifest hashes were
  refreshed in the existing S2-4 bundle worktree. That candidate remains pinned to the previous
  source revision and is not yet installable as a matching bundle.

## Verification evidence

The designated `functional-test-reviewer` reports this focused command at baseline HEAD
`473e559d3c82405cbe11d4969439c6760840675b`:

```powershell
python -c "import socket, pytest; socket.AF_UNIX = getattr(socket, 'AF_UNIX', 1); raise SystemExit(pytest.main(['-q', 'tests/vst/test_s2_sandbox_probe.py', 'tests/vst/test_s2_e8_synthetic_lifecycle.py', 'tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run', 'tests/vst/test_s2_dispatch_owner_service.py::test_s2_supervisor_service_rejects_removed_probe_key_path', 'tests/vst/test_s2_runtime_config_bundle.py']))"
```

Reported result: `65 passed, 8 skipped, 1 warning in 17.98s`. The exact source/test diff from
baseline HEAD used by that command hashes to
`10839b5279159e8c51aa1e383ef5d49eed7a7b67f416a42cc01d29d59a1768d4` (41,994 bytes), computed
from `git diff HEAD --binary` over the five implementation files and six selected test files. On
Windows, the reviewer supplied an
in-memory `socket.AF_UNIX` fallback solely so a POSIX-only test module could be collected; it was
not used by the selected tests. The warning is pytest-asyncio's Python 3.14 deprecation warning.
An earlier wider collection failed on the absent Windows `socket.AF_UNIX`; one POSIX-path-specific
test was excluded because Windows `os.path.isabs('/var/...')` prevents its intended assertion from
being reached. Neither is represented as a passing test.

A read-only `security-reviewer` found no confirmed source regression from removing the probe
signature. Its conclusion is conditional on the root process capturing the probe output into the
root-owned record. That live capture path has not been established: the configured
`probe-entrypoint.py` runs as UID/GID `999:989` and prints JSON, while no in-repository writer from
that output to `/var/lib/vst-runner/private/preflight.json` was found in the scoped source search.
Synthetic tests prove schema and binding only; they do not prove capture authenticity or host
isolation.

## Acceptance disposition

- **S2-4.1 source/test contract:** delivered in commit
  `8acd56ccb37e888a64b4f5898864bb07599683d0`; normal push output was
  `473e559..8acd56c` to `origin/s2-canonical-continuation`.
- **S2-4 runtime acceptance:** remains `IN PROGRESS`. Root capture, current E5, service activation,
  Store/API startup, and a real owner-to-Runner result are not proven by this change.
- **Restricted scenarios:** process-kill, crash/recovery, mutation, E8, and policy selectors remain
  `NOT_RUN` as required.
- **No S2 closure:** S2-5 and later sprints remain queued behind S2-4 and the ordered backlog.

## Ordered next action

After this bounded source/test task is committed and normally pushed, Codex implements and verifies
the exact root capture path as the next S2-4 child task, then prepares a runtime bundle pinned to
the resulting source HEAD. Do not start S2-5 or S3 before S2-4 acceptance is actually satisfied.
