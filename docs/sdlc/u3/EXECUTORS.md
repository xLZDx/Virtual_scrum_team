# U3-2 test executors: one interface, two executors

Operator decision OD-2: build both executors and compare them. This document describes the
contract. Implementation: `tools/qa/executor.py`, `tools/qa/executor_native.py`,
`tools/qa/executor_aeve.py`. Status: implemented statically; NOT_RUN (no executor has been
started, no test, Docker or AEVE command was executed while writing this).

## Interface

```
get_executor(executor_id) -> TestExecutor          # closed set: "vst-native", "aeve-sandbox"
TestExecutor.run(category, *, repo_root, expected_head, **options) -> ExecutorReport
judge(report) -> (verdict, reasons)                # APPROVABLE | COARSE_ONLY | NON_APPROVING
validate_report(report)                            # strict; raises ExecutorError(REPORT_INVALID)
```

`ExecutorReport` is a frozen envelope: category, executor_id, expected_head, candidate_head,
head_after, result (PASS, FAIL, INCONCLUSIVE, BLOCKED, NOT_RUN), exit_code, per-id fields
(expected, collected, passed, skipped, failed, uncollected, xfail), artifact_digests,
not_run_reasons, not_available, reasons, native_verdict, raw_record_sha256 and a read-only
raw_record. A per-id field is a tuple, or `None` meaning NOT_AVAILABLE; `not_available` always
names exactly the fields that are `None`. Nothing is estimated or defaulted.

Verdict rules (`judge`):

- NON_APPROVING: unsupported category, result other than PASS, exit code missing or non-zero,
  candidate head or head after differs from expected head (or is missing), any failed, skipped,
  xfail or uncollected id, duplicate ids, expected ids not all passed, unexpected passed ids, an
  invalid envelope, or (native only) the native gate verdict is not APPROVABLE.
- COARSE_ONLY: nothing above fails, but at least one per-id field is NOT_AVAILABLE.
- APPROVABLE: nothing fails and every per-id field is available. An executor that cannot fill the
  id fields can never become APPROVABLE through id-level rules.

Typed refusals (`ExecutorError.code`) common to both executors: UNKNOWN_EXECUTOR,
UNSUPPORTED_CATEGORY, HEAD_INVALID, UNKNOWN_OPTION, MISSING_OPTION, OPTION_INVALID,
PLATFORM_UNSUPPORTED, NOT_REPO_ROOT, REPO_UNUSABLE, STALE_HEAD, EXEC_FAILED, REPORT_INVALID.

## Executor A: `vst-native`

Wraps `python -m tools.qa.run` and `tools.qa.gate_check`. It runs a fixed-argv subprocess (no shell)
with the pinned `C:\Python314\python.exe -P -s -B`, cwd and PYTHONPATH = the candidate repo root,
because the runner binds its runtime profile to its own interpreter and parses argv with argparse.
It then selects the last record appended by this run to
`docs/sdlc/evidence/qa/<category>.report.jsonl`, runs `gate_check.check_report` against the
repo registry (artifact bytes taken from the recorded ranges) and carries that verdict.

Options: `dependency_target`, `dependency_wheelhouse`, `scratch_root`, `run_id` (required);
`timeout_seconds` (1..3600, default 900), `output_cap_bytes` (1..4 MiB). All paths absolute and
outside the repository. All per-id fields are available. The run appends to the candidate's
append-only evidence files, so the worktree gains changes under `docs/sdlc/evidence/qa/`.
Refusals: INTERPRETER_MISSING, NATIVE_CHILD_TIMEOUT, NATIVE_OUTPUT_TRUNCATED, NATIVE_NO_RECORD,
NATIVE_RECORD_MISMATCH, NATIVE_RECORD_INVALID, NATIVE_EXIT_INCONSISTENT, RESULT_UNMAPPED (unknown
result string), UNSUPPORTED_CATEGORY (native result UNSUPPORTED).

## Executor B: `aeve-sandbox`

Wraps `aeve sandbox project-test` unchanged (AEVE is read-only; its ledger is never read). Argv:
`<python> -P -s -B -m aeve sandbox project-test --root <repo> --profile <tracked.json>
--wall-timeout-seconds <1..60>`, environment from `aeve_probe.build_child_env`, cwd outside the
candidate, bounded time and output, process tree killed on breach. The AEVE head and matrix digest
are probed and compared with a caller-supplied `aeve_pin` (same rule as `tools/uc/router.py`).

Options: `profile` (repo-relative tracked JSON path) and `aeve_pin` (required);
`wall_timeout_seconds` (optional).

Preconditions: Docker Desktop CLI at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`
(hard-coded in AEVE), the profile tracked and unmodified, a clean checkout at exactly
`expected_head` (AEVE has no `--expected-head`; the executor compares `source_head` itself and
also re-reads HEAD after the run), AEVE checkout without tracked changes.

Mapping: COMPLETE with every baseline exit code 0, CLI exit 0, cleanup AUTO_REMOVED, all digests
present and the vetted profile hash matching is PASS (coarse); a non-zero baseline is FAIL;
INVALID is NOT_RUN; BLOCKED is BLOCKED; TIMEOUT and CANCELLED are INCONCLUSIVE; FAILED is FAIL if
project code ran, else BLOCKED; NEEDS_REVIEW is FAIL for BASELINE_FAILED, else INCONCLUSIVE. The AEVE
reason_code is kept in `not_run_reasons["project-test"]` for every non-PASS result.

Refusal codes specific to B: MUTATION_PROFILE_REFUSED, MUTATION_REPORTED, PROFILE_INVALID,
PROFILE_NOT_TRACKED, AEVE_PIN_REQUIRED, AEVE_PIN_MISMATCH, AEVE_PROBE_FAILED, AEVE_CHECKOUT_DIRTY,
DOCKER_CLI_MISSING, AEVE_CHILD_TIMEOUT, AEVE_OUTPUT_TOO_LARGE, AEVE_NO_EXIT, AEVE_BAD_OUTPUT,
AEVE_CONTRACT_VIOLATION (unknown or duplicate keys, schema mismatch, llm_calls != 0, exit 0 without
COMPLETE, COMPLETE without executed project code).

### What B cannot provide (NOT_AVAILABLE)

`expected_ids`, `collected_ids`, `passed_ids`, `skipped_ids`, `failed_ids`, `uncollected_ids`,
`xfail_ids`. AEVE returns only a profile-level baseline exit code and hashes: no per-test ids, no
registry binding, no stdout/stderr artifacts, no category semantics. Its `head_after` is filled by
the executor from git, not by AEVE. Verdict ceiling for B is therefore COARSE_ONLY.

## No mutation run

No mutation run is ever performed. B refuses any profile unless `max_mutants == 0` and
`mutation_paths == []`, reading those values from the exact bytes AEVE will read, before launching;
it refuses a result that reports any mutation activity; A runs no mutation campaign at all.
