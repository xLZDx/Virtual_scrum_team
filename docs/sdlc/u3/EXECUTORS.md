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
(expected, collected, passed, skipped, failed, uncollected, xfail), profile (aeve only),
candidate_attested, artifact_digests (64-hex only), not_run_reasons, not_available, reasons,
native_verdict, raw_record_sha256 and a read-only raw_record. A per-id field is a tuple, or `None`
meaning NOT_AVAILABLE; `not_available` always names exactly the fields that are `None`. Nothing is
estimated or defaulted. `head_after` is always read by the executor itself with git after the run.

Verdict rules (`judge`):

- NON_APPROVING: unsupported category, result other than PASS, exit code missing or non-zero,
  candidate head or head after differs from expected head (or is missing), any failed, skipped,
  xfail or uncollected id, duplicate ids, expected ids not all passed, unexpected passed ids, an
  invalid envelope, or a carried native gate verdict that is not APPROVABLE (the native executor must
  carry one).
- COARSE_ONLY: nothing above fails, but the ceiling applies. Ceilings: (a) `aeve-sandbox` is capped
  at COARSE_ONLY unconditionally; (b) a native report that is candidate-attested (see below), reason
  `NATIVE_CANDIDATE_ATTESTED`; (c) any report with a per-id field NOT_AVAILABLE.
- APPROVABLE: only a native report, with every per-id field available, everything passed, the native
  gate APPROVABLE, and both caller pins supplied and matching.

Common typed refusals (`ExecutorError.code`): UNKNOWN_EXECUTOR, UNSUPPORTED_CATEGORY, HEAD_INVALID,
UNKNOWN_OPTION, MISSING_OPTION, OPTION_INVALID, PLATFORM_UNSUPPORTED, NOT_REPO_ROOT, REPO_UNUSABLE,
STALE_HEAD, GIT_UNTRUSTED, EXEC_FAILED, REPORT_INVALID.

Process requirement: git is accepted only if the git the registry helpers resolve is the first git on
an absolute PATH entry outside the candidate (`aeve_probe._find_git` rule), otherwise GIT_UNTRUSTED.
The VST process must not run with its current directory on the candidate and should be started with
`python -P`.

## Executor A: `vst-native`

Wraps `python -m tools.qa.run` and `tools.qa.gate_check`. It runs a fixed-argv subprocess (no shell)
with the pinned `C:\Python314\python.exe -P -s -B`, cwd and PYTHONPATH = the candidate repo root,
because the runner binds its runtime profile to its own interpreter and parses argv with argparse.

Options: `dependency_target`, `dependency_wheelhouse`, `scratch_root`, `run_id` (required);
`timeout_seconds` (1..3600, default 900), `output_cap_bytes` (1..4 MiB), `expected_registry_sha256`,
`expected_runner_tree_sha256` (optional pins). The three directories must be absolute and resolve
(realpath) outside the repository, else PATH_INSIDE_REPOSITORY.

Record selection: the executor remembers the size of `docs/sdlc/evidence/qa/<category>.report.jsonl`,
reads only the bytes appended after that offset (8 MiB cap, torn last line dropped), keeps the records
whose `run_id` and `category` match, and requires exactly one (or, for the runner's documented
superseding record, a final BLOCKED one). After the child exits the executor re-reads HEAD and the
worktree itself; the record's `head_after` is not trusted.

### Candidate attestation and the pins

The child runs the candidate's own `tools.qa.run` and registry, so an unpinned native record is
candidate-attested: it proves what the candidate's runner says, not what an independent runner
would say. Therefore a native report is capped at COARSE_ONLY (`NATIVE_CANDIDATE_ATTESTED`) unless
BOTH pins are supplied and match:

- `expected_registry_sha256`: the registry sha256 (`validate_registry(...).sha256`) at the head.
- `expected_runner_tree_sha256`: sha256 over the sorted `path\0blobsha\n` lines of
  `git ls-tree -r -z <expected_head> -- tools/qa`.

A supplied pin that differs is refused before the run (REGISTRY_PIN_MISMATCH, RUNNER_PIN_MISMATCH).
The computed runner tree digest and the record's registry digest are carried in `artifact_digests`.

### Precondition: clean worktree per category

Evidence is append-only inside the candidate, so after a run the worktree holds uncommitted
`docs/sdlc/evidence/qa/<category>.*` files. A run requires the worktree to be clean apart from that
category's own three artifacts, else CANDIDATE_DIRTY_BEFORE_RUN (naming the paths). To run a second
category use a fresh clean checkout, or commit the previous category's evidence first (which changes
HEAD, so a new `expected_head`). A dirty tree after the run is CANDIDATE_DIRTY_AFTER_RUN.

Native refusal codes: INTERPRETER_MISSING, PATH_INSIDE_REPOSITORY, CANDIDATE_DIRTY_BEFORE_RUN,
CANDIDATE_DIRTY_AFTER_RUN, REGISTRY_UNAVAILABLE, REGISTRY_PIN_MISMATCH, RUNNER_PIN_MISMATCH,
NATIVE_CHILD_TIMEOUT, NATIVE_OUTPUT_TRUNCATED, NATIVE_NO_RECORD, NATIVE_RECORD_TOO_LARGE,
NATIVE_RECORD_AMBIGUOUS, NATIVE_RECORD_INVALID, NATIVE_EXIT_INCONSISTENT, RESULT_UNMAPPED (unknown
result string), UNSUPPORTED_CATEGORY (native result UNSUPPORTED). A non-PASS record with missing
head or id fields is mapped to a report with those fields NOT_AVAILABLE and the reason kept.

## Executor B: `aeve-sandbox`

Wraps `aeve sandbox project-test` unchanged (AEVE is read-only; its ledger is never read). Argv:
`<python> -P -s -B -m aeve sandbox project-test --root <repo> --profile <tracked.json>
--wall-timeout-seconds <1..60>`, environment from `aeve_probe.build_child_env`, cwd outside the
candidate, bounded time and output, process tree killed on breach.

Order: AEVE probe and pin check (head, matrix digest, no tracked changes, no untracked source files,
missing counts refused, as in `tools/uc/router.py`), then the profile is read and vetted, HEAD is
re-read immediately before launch together with a candidate worktree check, and after the child
exits the probe and pin check, the HEAD re-read and the worktree check run again.

Candidate worktree: read-only `git status --porcelain=v1 -z --untracked-files=all` (trusted git, only
`.gitignore`d paths are exempt). AEVE writes nothing into the candidate, so ANY modified, staged,
deleted or untracked path refuses with CANDIDATE_DIRTY_BEFORE_RUN (nothing launched) or
CANDIDATE_DIRTY_AFTER_RUN (no report, so a PASS is never returned for a changed tree); the detail
names up to 8 paths. There are no exceptions, unlike the native executor, which allows its own
category's three evidence artifacts.

Options: `profile` (repo-relative tracked JSON path starting with an alphanumeric character) and
`aeve_pin` (required); `wall_timeout_seconds` (optional).

Preconditions: Docker Desktop CLI at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`
(hard-coded in AEVE), the profile tracked and unmodified, a clean checkout at exactly
`expected_head` (AEVE has no `--expected-head`; the executor compares `source_head` itself).

Mapping: COMPLETE with every baseline exit code 0, CLI exit 0, cleanup AUTO_REMOVED, all digests
present, image digest `sha256:<64 hex>` (prefix stripped in the report) and matching vetted profile
hash is PASS (coarse, still COARSE_ONLY in `judge`); a non-zero baseline is FAIL; INVALID is NOT_RUN;
BLOCKED is BLOCKED; TIMEOUT and CANCELLED are INCONCLUSIVE; FAILED is FAIL if project code ran, else
BLOCKED; NEEDS_REVIEW is FAIL for BASELINE_FAILED, else INCONCLUSIVE. The AEVE reason_code is kept
in `not_run_reasons["project-test"]` for every non-PASS result. A `profile_sha256` in the envelope
that differs from the vetted bytes is refused for every status.

Refusal codes specific to B: CANDIDATE_DIRTY_BEFORE_RUN, CANDIDATE_DIRTY_AFTER_RUN, MUTATION_PROFILE_REFUSED, MUTATION_REPORTED, PROFILE_INVALID,
PROFILE_NOT_TRACKED, PROFILE_HASH_MISMATCH, AEVE_PIN_REQUIRED, AEVE_PIN_MISMATCH, AEVE_PROBE_FAILED,
AEVE_CHECKOUT_DIRTY, DOCKER_CLI_MISSING, AEVE_CHILD_TIMEOUT, AEVE_OUTPUT_TOO_LARGE, AEVE_NO_EXIT
(these three state that container cleanup is unconfirmed), AEVE_BAD_OUTPUT, AEVE_CONTRACT_VIOLATION.

### What B cannot provide (NOT_AVAILABLE)

`expected_ids`, `collected_ids`, `passed_ids`, `skipped_ids`, `failed_ids`, `uncollected_ids`,
`xfail_ids`. AEVE returns only a profile-level baseline exit code and hashes: no per-test ids, no
registry binding, no stdout/stderr artifacts, no category semantics. The verdict ceiling for B is
COARSE_ONLY, unconditionally.

## No mutation run

No mutation run is ever performed. B refuses any profile unless `max_mutants == 0` and
`mutation_paths == []`, reading those values from the exact bytes AEVE will read, before launching;
it refuses a result that reports any mutation activity; A runs no mutation campaign at all.
