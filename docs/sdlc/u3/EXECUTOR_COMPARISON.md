# U3-7 executor comparison (static form)

Scope: operator decision 2026-11-10, STATIC COMPARISON ONLY. Nothing was executed while writing this
document: no pytest, no Docker, no AEVE command, no mutation run, no project code. Every statement comes
from reading source. No number below is measured.

Labels: FACT = read in the cited code line; INFERENCE = derived from FACTs, not observed;
NOT_RUN = would need a real run that has not happened.

Executors compared:

- A `vst-native`: `tools/qa/executor_native.py` (wrapper) over `tools/qa/run.py` (runner) and
  `tools/qa/gate_check.py`.
- B `aeve-sandbox`: `tools/qa/executor_aeve.py` (wrapper) over the existing `aeve sandbox project-test`
  in `D:\Repo\AEVE` (read-only here; not modified).

Shared envelope and verdict rules: `tools/qa/executor.py` (`ExecutorReport` at :129-156, `judge` at :285-367).

## 1. Summary table

| Topic | A: vst-native | B: aeve-sandbox |
|---|---|---|
| Collected IDs | FACT: `collected_ids` from record key `collected_node_ids` (executor_native.py:366); run.py fills it from pytest events via `_resolve_cases` (run.py:1107-1112). | FACT: always NOT_AVAILABLE; `ids={}` (executor_aeve.py:283). AEVE envelope keys carry no test ids (executor_aeve.py:47-53). |
| Passed IDs | FACT: `passed_test_ids` per registry test id (executor_native.py:367; run.py:1129 requires set equality with expected ids for no failure reason). | FACT: NOT_AVAILABLE. Only `baseline_exit_codes` (list of int lists) is reported (executor_aeve.py:199-203). |
| skip / xfail / uncollected visibility | FACT: separate fields `skipped_test_ids`, `xfail_test_ids`, `uncollected_test_ids`; each non-empty one adds a failure reason (run.py:1119-1126) and `judge` makes it NON_APPROVING (executor.py:320-325). | FACT: NOT_AVAILABLE for all three. INFERENCE: a skipped or xfail test is invisible to B; whether it can still be hidden inside a zero exit depends on the framework and profile, which this comparison did not execute. |
| Per-id availability (NOT_AVAILABLE) | FACT: all id fields available on a well-formed PASS record; on a non-PASS record with malformed id fields they become None with a note (executor_native.py:339-346). `judge` turns any None field of a native report into NON_APPROVING `NATIVE_FIELDS_MISSING` (executor.py:344-345). | FACT: `expected/collected/passed/skipped/failed/uncollected/xfail_ids` are all NOT_AVAILABLE; `not_available` lists them (executor.py:56, :184-185). |
| Duration | FACT: runner measures `duration_seconds` around the pytest child only (run.py:1060-1064; field initial None at run.py:658). The wrapper does not copy it into a typed field; it is only inside `raw_record` (executor_native.py:397-404). | FACT: no duration key in the allowed envelope keys (executor_aeve.py:49-53). The wrapper does not time the child. B has no duration. INFERENCE: wall time could only be taken from outside, which is not implemented. |
| Time bounds | FACT: runner timeout default 900 s, max 3600 s (run.py:68-69); wrapper outer bound = timeout + 300 s (executor_native.py:45, :285). | FACT: AEVE `--wall-timeout-seconds` 1..60 (executor_aeve.py:309-311; sandbox.py:241-243); AEVE overall budget `OVERALL_SECONDS = 100` with reserves (sandbox.py:45-50); wrapper outer bound = wall + 180 s (executor_aeve.py:41, :360). INFERENCE: a category needing more than about 60 s of test time cannot fit B. |
| Setup cost | FACT: absolute `dependency_target`, `dependency_wheelhouse`, `scratch_root`, `run_id` required, all outside the repo (executor_native.py:39, :229-231); the target is prepared by `tools.qa.prepare_dependencies` (run.py:117-118); pinned interpreter `C:\Python314\python.exe` must exist and be CPython 3.14.3 (executor_native.py:217-219; run.py:429-440); locked wheels verified against `tools/qa/requirements.lock` before and after (run.py:995-1004, :1076-1084); clean tree except this category's three artifacts (executor_native.py:234-239); optional two pins for APPROVABLE (executor_native.py:241-250). | FACT: Docker Desktop CLI at the fixed path (executor_aeve.py:35, :319; sandbox.py:24); AEVE checkout whose head and matrix digest equal the caller `aeve_pin` and which is clean (executor_aeve.py:117-139); a tracked, unmodified profile JSON in the candidate (executor_aeve.py:95-112); profile schema `g4.project_test_profile.v1` requires python `3.14`, framework unittest or pytest, source paths, requirements lock and installer wheel/wheels with sha256 (AEVE project_test.py:88-125); a fully clean candidate checkout at exactly `expected_head`, no exemptions (executor_aeve.py:349-354). FACT: no profile file exists in this repository: `g4.project_test_profile` occurs only in `tools/qa/executor_aeve.py` among `*.py`/`*.json` files (Grep). |
| Isolation / trust | FACT: pytest runs on the host as the operator user with no identity separation; the plugin reports from inside the pytest process, so the record is candidate-attested (run.py:11-17, :79-84). Job object limits: 64 processes, 2 GiB per process (run.py:74-75). Unpinned report is capped COARSE_ONLY `NATIVE_CANDIDATE_ATTESTED`; APPROVABLE only with both pins matching and everything passed (executor.py:354-367; executor_native.py:391). | FACT: container flags `--network=none --read-only --cap-drop=ALL --no-new-privileges --pids-limit=64 --memory=512m --cpus=1.0` (AEVE sandbox.py:379-380). FACT: verdict ceiling is COARSE_ONLY unconditionally (executor.py:349-353). INFERENCE: stronger isolation of the process, weaker evidence about which tests ran. |
| Failure for a seeded failing test | See section 1.1. | See section 1.1. |
| Refusal codes | FACT: common codes plus INTERPRETER_MISSING, PATH_INSIDE_REPOSITORY, CANDIDATE_DIRTY_BEFORE_RUN/AFTER_RUN, REGISTRY_UNAVAILABLE, REGISTRY_PIN_MISMATCH, RUNNER_PIN_MISMATCH, NATIVE_CHILD_TIMEOUT, NATIVE_OUTPUT_TRUNCATED, NATIVE_NO_RECORD, NATIVE_RECORD_TOO_LARGE, NATIVE_RECORD_AMBIGUOUS, NATIVE_RECORD_INVALID, NATIVE_EXIT_INCONSISTENT, RESULT_UNMAPPED, UNSUPPORTED_CATEGORY (executor_native.py:55-250, :288-323). | FACT: common codes plus PROFILE_INVALID, PROFILE_NOT_TRACKED, MUTATION_PROFILE_REFUSED, MUTATION_REPORTED, PROFILE_HASH_MISMATCH, AEVE_PIN_REQUIRED, AEVE_PIN_MISMATCH, AEVE_PROBE_FAILED, AEVE_CHECKOUT_DIRTY, DOCKER_CLI_MISSING, CANDIDATE_DIRTY_BEFORE_RUN/AFTER_RUN, AEVE_CHILD_TIMEOUT, AEVE_OUTPUT_TOO_LARGE, AEVE_NO_EXIT, AEVE_BAD_OUTPUT, AEVE_CONTRACT_VIOLATION (executor_aeve.py:66-386). |
| Platform limits | FACT: Windows only; `PLATFORM_UNSUPPORTED` if `os.name != "nt"` (executor_native.py:215-216); WSL profiles are out of scope and recorded NOT_RUN (run.py:86-88). | FACT: Windows only with Docker Desktop at the fixed path (executor_aeve.py:317-320). |

### 1.1 Seeded failing test: how each executor would surface a failure

Fact about the catalog: `tests/qa/seeded_failure/catalog.json` lists eight synthetic fixtures SF-001..SF-008
(:6-60). Each `test_id` points to a test in `tests/qa/test_s4_seeded_failure_catalog.py` whose job is to
assert that a defective input is REJECTED (the `expected_rejection` text, e.g. SF-005 `NOT_PASSED:
skipped_test_ids=T-REQ`, catalog.json:38). FACT: the catalog does not contain a test that is meant to fail.
INFERENCE: running category `seeded-failure` with a healthy candidate is expected to give PASS under A, not
FAIL, so the catalog alone does not give "a seeded failing case". A real failing case would need a
deliberately broken test or code in a scratch clone (and, for A, a regenerated registry). That clone and
change do not exist; see section 3.

If one test of the category fails:

| Aspect | A (FACT unless marked) | B (FACT unless marked) |
|---|---|---|
| Result | Runner puts the id in `failed_test_ids`, adds a reason, `result = "FAIL"` (run.py:1121-1122, :1172). Wrapper maps it to `FAIL` (executor_native.py:316-325). | AEVE reports a failing baseline as reason `BASELINE_FAILED`, status NEEDS_REVIEW (AEVE project_test.py:43); wrapper maps NEEDS_REVIEW + BASELINE_FAILED to `FAIL` (executor_aeve.py:271-272). |
| Failed ids | Named in `failed_ids` (executor_native.py:369). | Not reported: NOT_AVAILABLE. Only the reason code `BASELINE_FAILED` in `not_run_reasons["project-test"]` (executor_aeve.py:285). |
| Exit code | Runner exit 1 for FAIL (run.py:1185); wrapper enforces `returncode == 0` iff PASS (executor_native.py:321). The report `exit_code` is the pytest exit code from the record (executor_native.py:352), not the runner exit code. | Report `exit_code` is the AEVE CLI return code (executor_aeve.py:282). INFERENCE: non-zero; CLI returns 3 for non-COMPLETE in the sibling commands read (AEVE cli.py:380-394); the project-test return value comes from `run_project_test` and was not traced to a literal. |
| Verdict from `judge` | NON_APPROVING with `RESULT_FAIL`, `EXIT_NONZERO`, `FAILED_IDS` (executor.py:304-325). | NON_APPROVING with `RESULT_FAIL`, `EXIT_NONZERO` (executor.py:304-309). |
| What B cannot report | - | Which test failed, how many, whether the failure is an assertion, an error or a collection problem, and whether other tests were skipped. INFERENCE: B also executes the baseline twice (`baseline_runs` in 0, 1, 2; AEVE sandbox.py:603), so a duration for one test pass is not defined by the envelope. |
| Early-stop cases | Pre-run problems (dirty tree, bad pin, missing interpreter) raise a typed refusal and no report; problems inside the runner become a BLOCKED record with runner exit 2 (run.py:1038-1042, :1203-1204). | Pre-run problems raise typed refusals; AEVE-side problems arrive as INVALID/BLOCKED/TIMEOUT/CANCELLED/FAILED statuses mapped to NOT_RUN/BLOCKED/INCONCLUSIVE/INCONCLUSIVE/FAIL-or-BLOCKED (executor_aeve.py:263-272). |

## 2. What each executor could not run or cannot prove

Plainly stated; none of these gaps was closed by this task.

A, `vst-native`:

- NOT_RUN: it was not started. No pytest ran, so no test result, id list or duration exists for A.
- Cannot prove independence of the runner: the runner and registry come from the candidate itself, so an
  unpinned report proves only what the candidate's runner says (executor_native.py:11-15; run.py:11-17).
  Even with both pins, pytest still runs on the host, in the operator account, with the plugin inside the
  pytest process; the runner's own text says the isolation checks "detect accidental or naive interference
  only" (run.py:16-17).
- Cannot run on WSL profiles; those selectors are recorded NOT_RUN by design (run.py:86-88).
- Cannot run a second category in the same dirty checkout; evidence from the first category makes the tree
  dirty (executor_native.py:233-239).
- FACT from the decision log, not re-verified here: the operator recorded that no trusted offline wheelhouse
  path is available (core/DECISION_LOG.md:887). Treat the dependency prerequisite as unmet until checked.

B, `aeve-sandbox`:

- NOT_RUN: it was not started. No Docker, AEVE or profile run happened.
- Cannot provide any per-test information (section 1) and is capped at COARSE_ONLY in every case
  (executor.py:349-353); it can never be APPROVABLE.
- Cannot run a test set that needs more than the AEVE limits: 60 s wall per baseline, 100 s overall, 512 MiB,
  1 CPU, no network, read-only filesystem (AEVE sandbox.py:45-50, :379-380). INFERENCE: whether the real
  categories fit is unknown.
- No profile for this repository exists yet (Grep result above), so B has no runnable input today.
  INFERENCE: writing one needs wheel files and a requirements lock tracked in the candidate, because the
  profile references repository paths with sha256 (AEVE project_test.py:112-125).
- Cannot bind to the VST registry: it has no registry binding or category semantics (EXECUTORS.md:136-137;
  executor_aeve.py:262 note). The `category` argument is only checked for being a known name
  (executor_aeve.py:305) and never selects tests.
- Cannot report mutation results by design: any profile with `max_mutants != 0` or non-empty `mutation_paths`
  is refused, and any reported mutation activity is refused (executor_aeve.py:76-92, :204-211).
- Container cleanup is unconfirmed after a timeout, output overflow or missing exit (executor_aeve.py:45,
  :363-368).
- The files under `tests/qa/seeded_failure/aeve_fixtures/` (py-bare-except, py-mutable-default-arg and so
  on) are defective/clean source pairs, not `g4.project_test_profile.v1` profiles. INFERENCE: they are inputs
  for AEVE analysis rules, not for `project-test`; this was judged from file names only and the files were not
  opened.

## 3. Measurement plan (all NOT_RUN)

Goal: real numbers for both executors on one category, one seeded failing case, no mutation. The operator runs
these later. Nothing here has been executed. Placeholders are in angle brackets.

Unmet prerequisites (each blocks the step named):

| # | Prerequisite | Blocks | Status |
|---|---|---|---|
| P1 | A clean checkout (no tracked changes, no untracked files) at one exact commit `<HEAD40>`, outside any dirty working copy | A and B | NOT_RUN, not prepared |
| P2 | Dependency target and offline wheelhouse for `tools/qa/requirements.lock`, both absolute and outside the repo, disjoint | A | UNMET per core/DECISION_LOG.md:887 (re-check) |
| P3 | `C:\Python314\python.exe` is CPython 3.14.3 | A | not verified here |
| P4 | Docker Desktop running; CLI at `C:\Program Files\Docker\Docker\resources\bin\docker.exe` | B | not verified here |
| P5 | AEVE checkout clean; its head and matrix digest recorded as `aeve_pin` | B | not verified here |
| P6 | A tracked profile JSON in the candidate (schema `g4.project_test_profile.v1`, `max_mutants` 0, `mutation_paths` `[]`, wheels/lock tracked) | B | does not exist |
| P7 | A seeded failing case: a scratch clone with one deliberately failing test (for A also a regenerated registry), committed there, so HEAD is clean | A and B failing case | does not exist; the catalog has none |
| P8 | Forbidden-run reminder: no pytest outside the runner, no mutation, no CI, no full suite. The pytest run in step A1 is the executor's own and needs the operator's explicit permission under the 2026-11-10 decision | A | operator-only decision |

Commands (PowerShell, run from a directory that is NOT the candidate, VST process started with `-P`):

```
# Common: pin the head and the category
$repo = "<ABSOLUTE_CANDIDATE_ROOT>"
$head = (git -C $repo rev-parse HEAD)          # must be the clean exact HEAD, 40 hex

# A1. Executor A, healthy category (category value: one of functional, integration, api, e2e,
#     identity, qa-tooling, seeded-failure, regression; example: seeded-failure)
C:\Python314\python.exe -P -s -B -c "import sys; sys.path.insert(0, r'D:\Repo\Virtual_scrum_team'); from tools.qa.executor import get_executor; import json; r = get_executor('vst-native').run('seeded-failure', repo_root=r'<ABSOLUTE_CANDIDATE_ROOT>', expected_head='<HEAD40>', dependency_target=r'<ABS_TARGET>', dependency_wheelhouse=r'<ABS_WHEELHOUSE>', scratch_root=r'<ABS_SCRATCH>', run_id='u3-7-a1'); from tools.qa.executor import judge; print(r.result, r.exit_code, len(r.passed_ids or ()), judge(r)); print(r.raw_record.get('duration_seconds'))"

# A2. Executor A, failing case: same call on the P7 clone, new <HEAD40>, run_id 'u3-7-a2'
#     (a different clean checkout, because A1 leaves evidence files in the candidate)

# B1. Executor B, healthy: same repo, profile path relative to repo root
C:\Python314\python.exe -P -s -B -c "import sys; sys.path.insert(0, r'D:\Repo\Virtual_scrum_team'); from tools.qa.executor import get_executor, judge; r = get_executor('aeve-sandbox').run('seeded-failure', repo_root=r'<ABSOLUTE_CANDIDATE_ROOT>', expected_head='<HEAD40>', profile='<REPO_RELATIVE_PROFILE.json>', aeve_pin={'head': '<AEVE_HEAD40>', 'matrix_digest_sha256': '<AEVE_MATRIX_SHA256>'}, wall_timeout_seconds=60); print(r.result, r.exit_code, r.not_available, judge(r))"

# B2. Executor B, failing case: same call on the P7 clone and its profile
```

Wall-clock numbers for B (not in the envelope) must be taken by the operator around the command, for example
with `Measure-Command { ... }` on A1/B1/A2/B2. Record for each run: exact command, `<HEAD40>`, result,
exit code, id counts (A only), `judge` verdict and reasons, and duration. Anything not obtained stays
NOT_RUN. No loops and no repeated runs to average (operator rule: one test, one run).

Expected shape, as INFERENCE only: A1 PASS (or INCONCLUSIVE if the category holds policy NOT_RUN selectors,
run.py:1166-1172) with verdict COARSE_ONLY unless both pins are supplied; A2 FAIL with the failing id named;
B1 PASS or a refusal if the profile or Docker prerequisites fail; B2 FAIL without any id.

## 4. Decision matrix

The selection is the operator's. This document does not choose. Evidence supports only the statements in
the table.

| Option | What you get | What you give up | Open risks (from the code read) |
|---|---|---|---|
| Keep A only | Per-test ids for passed, failed, skipped, xfail and uncollected; registry binding; the only path to an APPROVABLE verdict (needs both pins); duration in the raw record; no Docker. | Stronger sandbox isolation; independence from the candidate's own runner and registry unless both pins are used. | Needs the pinned Windows interpreter, the offline wheelhouse (reported unavailable, DECISION_LOG.md:887), and a clean checkout per category; a malicious or buggy test shares the operator's account (run.py:16-17). |
| Keep B only | Container isolation (no network, read-only, capped CPU/memory/pids); runs the candidate's tests away from the host account. | Any per-id evidence; any APPROVABLE verdict (COARSE_ONLY ceiling); registry/category semantics; duration in the envelope. | No profile exists; AEVE limits (60 s, 100 s overall, 512 MiB) may not fit real categories (unknown); Docker Desktop and an AEVE pin are required; failure reports cannot say which test failed. |
| Keep both | A supplies accounting and the only APPROVABLE path; B supplies an independent, isolated coarse signal on the same head. | Simplicity: two sets of prerequisites and two clean-checkout rules to maintain. | The two results answer different questions (ids versus profile baseline); a B PASS does not confirm any specific id that A reports. Cost of keeping B unused is maintenance only; not measured. |

Evidence-supported statements only: B can never be APPROVABLE (executor.py:349-353); A can be APPROVABLE
only with both pins (executor.py:354-367). Nothing in the code read shows which executor is faster, cheaper
or more reliable on real categories; that needs the section 3 runs.

## 5. Contradictions found between EXECUTORS.md and the code

1. Ceiling (c). EXECUTORS.md:34 says any report with a per-id field NOT_AVAILABLE is capped at COARSE_ONLY.
   Code: for a native report, any `not_available` field gives NON_APPROVING `NATIVE_FIELDS_MISSING`
   (executor.py:344-345, returns at :347-348); the COARSE_ONLY branch for missing ids (executor.py:362-366)
   is unreachable for both known executors (AEVE returns earlier at :349, native with missing fields has
   already failed). Code wins; the doc line is stale.
2. EXECUTORS.md:120-122 lists "a non-zero baseline" under COMPLETE as FAIL. In AEVE a failing baseline is
   reported as NEEDS_REVIEW/BASELINE_FAILED (AEVE project_test.py:43), which the wrapper maps to FAIL
   through a different branch (executor_aeve.py:271-272). The COMPLETE-with-non-zero branch
   (executor_aeve.py:238-240) is defensive; INFERENCE: it is not reached by AEVE's own status table.
   The doc is not wrong in outcome, but it names the wrong path.
3. EXECUTORS.md:119-121 says PASS needs baseline exit codes 0, CLI exit 0, cleanup AUTO_REMOVED, digests,
   image digest and profile hash. The code additionally requires `baseline_runs == len(codes)`, every run
   non-empty, `executed_project_code` true, a `source_head`, and `head_after == expected_head`; otherwise the
   result is INCONCLUSIVE, not PASS (executor_aeve.py:234-260). Omission in the doc.
4. EXECUTORS.md:38-40 lists the common typed refusals but not `EXECUTOR_ID_MISMATCH`
   (executor.py:389); every other common code is listed. Minor omission.
5. EXECUTORS.md:136-137 says B returns "no stdout/stderr artifacts"; the code confirms this by omission
   (artifact digests come only from AEVE digest keys, executor_aeve.py:274-279), no contradiction. Noted so
   it is not re-checked.
6. Not a contradiction but a gap: EXECUTORS.md does not say that the report `exit_code` for A is the pytest
   exit code from the record rather than the runner process exit code (executor_native.py:352 versus
   run.py:1185), and does not say B has no duration.
