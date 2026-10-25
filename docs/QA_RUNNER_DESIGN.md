# S4 QA runner implementation design

## Goal

Implement the S4 category runner and evidence envelope so the six declared lanes use native
pytest discovery, exact committed selectors, reproducible local inputs, and fail-closed test
accounting. Acceptance is defined by `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` AC-1 through AC-15.

## Non-goals

No CI, mutation tests, dependency installation during a run, external service calls, test execution
during the coding phase, VST receipt-schema change, or claim that candidate/sandbox-dependent S3
acceptance has passed. The HTTP API lane remains unsupported because the repository exposes only
Python module APIs in `tools/vst/`.

## Design

- `docs/qa/categories.json` is the committed source of truth. Each test selector has one stable ID,
  a source path, one `primary_category`, and source-commit provenance. Regression is a separate
  aggregate reference to functional, integration, API, and E2E selector IDs.
- Registered IDs are function or unittest-method selectors. The pytest plugin records every
  concrete collected node ID and its final outcome, then maps each case to exactly one registered
  selector. A selector is emitted as `PASS <selector-id>` only when it expanded to at least one
  case and every case passed. Any failed, skipped, xfailed, uncollected, duplicated, or unmapped
  case prevents that selector from passing. Concrete IDs and outcomes remain in the report.
- `tools/qa/registry.py` validates the exact manifest schema, uniqueness, category membership,
  source files, source commit bindings, and current candidate HEAD binding. `tools/qa/run.py` is the
  single CLI. `tools/qa/pytest_plugin.py` captures collection and per-case outcomes. Report
  normalization and digest validation live in `tools/qa/report.py`; synthetic negative inputs are
  data fixtures consumed through unchanged VST product interfaces.
- The runner invokes pytest as a child using the approved interpreter `C:\Python314\python.exe`,
  an explicit isolated dependency target outside the repository, and the repository lock
  (`tools/qa/requirements.lock`). The environment baseline is CPython 3.14.3. Pytest is pinned
  to 9.0.3: the official 9.0.3 release supports Python 3.14 and its PyPI advisory record lists no
  vulnerabilities, while 8.4.2's record identifies a UNIX temporary-directory vulnerability fixed
  in 9.0.3. The transitive test-only packages are pinned and wheel-hash-locked from the official
  PyPI JSON release records (`pytest`, `pluggy`, `packaging`, `iniconfig`, `Pygments`, `colorama`).
  This excludes source distributions and build-time dependencies. The runner never resolves
  or installs dependencies. Environment preparation installs the hash-locked wheels into an
  external target; each runner call names that target with `--dependency-target` and verifies it
  contains exactly the locked distributions and versions. The child process receives only that
  target through `PYTHONPATH`, with user-site loading disabled. The runner applies a timeout,
  output cap, minimal environment, repository-relative selectors, and an exact candidate working
  directory. Git reads
  that need a worker-owned checkout use a per-invocation `safe.directory` value scoped to that
  canonical checkout; no global Git configuration is changed.
- The QA JSON report is an artifact, not a signed VST receipt. When invoked from the existing VST
  runner, selector-level `PASS` lines use the existing trusted pass-lines parser; the VST runner
  signs the standard receipt and binds the report digest as an artifact. This preserves the current
  receipt contract while retaining concrete pytest outcomes for audit.
- Reports contain relative artifact paths, exact candidate HEAD, registry hash, lock hash,
  interpreter/tool versions, command, exit status, expected selectors, concrete collected and
  executed node IDs, per-case outcomes, and a typed result. Output logs are append-only per
  category. Each report binds to the exact stdout/stderr byte ranges written by that invocation
  and their chunk hashes; byte offsets and run timestamps are excluded from normalized report
  digests so earlier log history does not change the current run's semantic digest. The fixed
  paths are `docs/sdlc/evidence/qa/{category}.report.jsonl`, `{category}.stdout.txt`, and
  `{category}.stderr.txt` for all six categories. Environment values, credentials, and user-specific
  absolute paths are never serialized.

When a QA invocation runs through VST, its exact task manifest must explicitly include the three
output paths for that category in `change_scope.allowed_paths`. The manifest may additionally
include the exact source paths and lock path required for that task. This per-invocation declaration
does not widen or change VST diffgate rules. The runner rejects any output path other than the fixed
category paths.

New QA contract tests belong under `tests/qa/` and use the `test_s4_` filename convention. The
deterministic registry builder classifies those files into the matching S4 lane; seeded-failure
tests use `tests/qa/seeded_failure/` or the `test_s4_seeded_failure` prefix. Unknown test paths fail
registry generation rather than silently receiving a category.

## Failure modes

Unknown or duplicate selectors, stale candidate/registry provenance, absent interpreter or locked
dependency, zero-case selectors, unmapped cases, incomplete collection, timeout, truncated output,
or any non-passing required case produce a typed non-approving report and a non-zero command exit.
No empty-success fallback or interpreter fallback exists.

## Rollout and rollback

Add the runner and registry as new modules without changing existing VST receipt validators. The
initial rollout is local and synthetic. Rollback removes the S4 category slots/callers and new QA
modules; existing VST runner behavior and v1/v2 contracts remain unchanged.

## Test plan

After all S4 code is committed, `functional-test-reviewer` authors/runs focused registry, mapping,
normalization, and non-approving-result cases. `e2e-runner` then runs each native category and the
aggregate regression/seeded-failure flows through isolated temporary repositories. Tests are
mapped to AC-1 through AC-15; candidate comparison and fresh sandbox-bound cases remain `NOT_RUN`
until their exact external prerequisites are satisfied. No tests have been run for this design.

## Unknowns and ownership

The pinned Python 3.14.3 environment reports pytest 8.4.2, pluggy 1.6.0, packaging 26.2,
iniconfig 2.3.0, Pygments 2.20.0, and colorama 0.4.6. QA runs will use the new hash-pinned
pytest 9.0.3 lock in an isolated target, not the pre-existing pytest installation. The operator is
accountable for the delegated sprint; Codex coordinates implementation. PyPI exact-release pages:
`https://pypi.org/pypi/pytest/9.0.3/json`, `https://pypi.org/pypi/pluggy/1.6.0/json`,
`https://pypi.org/pypi/packaging/26.2/json`, `https://pypi.org/pypi/iniconfig/2.3.0/json`,
`https://pypi.org/pypi/pygments/2.20.0/json`, and
`https://pypi.org/pypi/colorama/0.4.6/json`. The canonical
technical owner for QA lock maintenance remains UNKNOWN in repository records. The
`functional-test-reviewer` and `e2e-runner` roles own required test authorship and execution.
