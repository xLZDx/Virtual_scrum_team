# S4 fresh WSL2 transfer and mapped worker E2E at `56dce67`

## Scope and provenance

- Source branch: `s4-native-qa-runner`.
- Exact source HEAD before transfer: `56dce67e508ccf452b2b7b39ed7f33c863081269`; Windows worktree was clean.
- Distribution: the named `Ubuntu-24.04` WSL2.
- This was a fresh transfer into a newly provisioned, run-specific S4 snapshot root. The earlier `RESULT_NOT_CAPTURED` destination was neither inspected nor retried.
- Private POSIX path and identity values are intentionally omitted from this public repository.

## Transfer invocation and correlated response

The Windows host invoked the documented bounded command with the pinned `C:\Python314\python.exe`, `tools.qa.wsl_snapshot`, `--cwd .`, `--distribution Ubuntu-24.04`, and the provisioned unprivileged runner, worker group, and new snapshot root. Private arguments are redacted here.

The response was `TRANSFERRED` with:

- Run ID: `f3ad62c94bc0429987bc24277103d5b4`
- Candidate HEAD: `56dce67e508ccf452b2b7b39ed7f33c863081269` (exact match)
- Bundle SHA-256: `d842a5770c4b6b4c0e69eafc00d61e3b6460e0c7868b3ea05664677b2a943a6e`
- Bundle bytes: `1,105,578`

The receiver verified the returned run directory under the supplied root, runner/group ownership and modes, repository entry ownership and modes, no symlinks, and the exact cloned HEAD before returning this correlated metadata.

## Read-only worker boundary

- The runner-side `_require_worker_source_read_only` check in `tools/qa/run.py` returned `PASS` for the new identified snapshot, checking the complete source and Git metadata against the provisioned worker identity.
- The worker could read `README.md`. A shell permission probe reported the file and repository directory were not writable by the worker.
- A direct append-open of `README.md` returned `PermissionError: [Errno 13] Permission denied`; no bytes were written.
- No new-file creation was attempted. The directory write check was mode/access based.

One initial inline Python preflight had a command-construction error: literal `\n` text was passed to `python3 -c`, resulting in `SyntaxError` before any boundary assertion executed. This is a command setup error, not a product/test failure. The corrected shell and append-open probes above then passed.

## Mapped native E2E

The read-only worker ran the same seven mapped selectors previously listed in evidence `s4-native-e2e-452c8ea.md`, against this new run's repository snapshot. Command shape, with the private snapshot path redacted:

```text
wsl.exe --distribution Ubuntu-24.04 --user [read-only worker] --cd [new identified run repository] --exec env TMPDIR=/dev/shm PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_OPTIONAL_LOCKS=0 /usr/bin/timeout --signal=TERM 120s /usr/bin/python3 -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin <same seven mapped selectors>
```

Runtime: Ubuntu 24.04 WSL2, CPython `3.12.3`, pytest `7.4.4`. Result: **7 passed, 0 failed, 0 skipped**, `3.62s`. No warning was emitted.

Post-run, the worker read Git HEAD `56dce67e508ccf452b2b7b39ed7f33c863081269`; porcelain status length was `0` bytes. The test run left the identified snapshot clean.

## Boundaries

This proves one run-scoped transfer, source/Git read-only permission boundary, and the seven mapped selectors on the identified POSIX snapshot. It does not prove the full S4 category denominator, POSIX symlink-specific registry case, signer socket, report-bound runner, signed receipt, authoritative gate, resource quotas, or broad sandbox acceptance. Those remain `NOT_RUN` or `NOT_VERIFIED`. No package was installed and no mutation, process-kill, signer, report, receipt, or gate operation was performed.
