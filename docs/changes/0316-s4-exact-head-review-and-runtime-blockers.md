# Change 0316 — Record exact-head S4 review and runtime prerequisites

## What changed

- Recorded the correlated GPT-PM review of exact head `ece606584a7c0dd86e76ce475d6f6728c6804508` and its raw reply in `docs/sdlc/evidence/s4-gptpm-final-review-ece6065.md`.
- Reconciled S4 state and backlog with exact-head functional/E2E reruns, code/security reviews, the WSL helper installation attempt, and the still-missing runtime inputs.
- Corrected the WSL helper design status without changing its security contract or any `NOT_RUN` policy exclusion.

## Why

The earlier record covered test-agent runs on a dirty working tree. New designated-role reruns were performed at exact committed head `ece6065`; separate code and security reviewers also reviewed that head. The final GPT-PM reply rejected S4 closure because policy and runtime acceptance remains incomplete, while confirming no new source-level BLOCKER/MAJOR defect.

## Evidence

- Functional-test-reviewer, GPT-6 Luna, low effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_dependency_provenance.py` — 7 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; Python 3.14.3; HEAD before/after `ece606584a7c0dd86e76ce475d6f6728c6804508`; only the preserved S2 evidence file was untracked.
- E2E-runner, GPT-6 Luna, low effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_requires_explicit_dependency_wheelhouse tests/qa/test_s4_e2e_runner_cli.py::test_s4_worker_helper_selector_is_wsl_only` — 2 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; same exact HEAD and status.
- Code-reviewer, GPT-6 Luna, medium effort: no evidence-backed BLOCKER/MAJOR/MINOR in the full AC-16/AC-17 source mechanism and integrations at exact head; no tests/checks/builds run.
- Security-reviewer, GPT-6 Luna, medium effort: no reachable BLOCKER/MAJOR/MINOR in the reviewed AC-16/AC-17 trust boundaries at exact head; no tests/build/install/runtime run.
- GPT-PM review request `5d258643-62e4-45cd-8360-ba624a2ed491`, correlated reply `612b234a-d0ca-5ea7-96bd-3ca1a67ee791`, input SHA-256 `d9c7a08ba70a6d97505771282e483b257f1b605af00a559082499bc60e370b18`; range `3b8d80ff5456192c2419d9515b47fb843939ee16..ece606584a7c0dd86e76ce475d6f6728c6804508`. Raw reply explicitly says `REJECT`. Structured CLI receipt says `final=false`, `final_overridden=true`, parser verdict `UNRECOGNIZED`; therefore no approval is recorded.
- The raw reply keeps MAJOR-01 open for 52 policy-prohibited selectors; it says MAJOR-02 source remediation is supported but runtime closure is not verified.
- The authorized helper install reached compilation on a distro-local candidate whose full HEAD and clean status matched `ece606584a7c0dd86e76ce475d6f6728c6804508`. It stopped with `/usr/bin/env: '/usr/bin/cc': No such file or directory`. Read-only checks found no `cc`, `gcc`, or `clang`, no installed `gcc`/`build-essential`, and no corresponding package in the distro's local apt archive. No helper was installed, no package was installed, and no download was made.
- The exact project-referenced `D:\Temp\virtual_scrum_team_qa_f4ef8e7` directory is an installed dependency target; the required existing trusted wheelhouse path is not established.
- The canonical checkout is `D:\Repo\Virtual_scrum_team`. No development worktree was created or used. The pre-existing untracked S2 evidence file remains unchanged.

## Remaining acceptance and owners

- AC-16 WSL identity: source-reviewed and selector registered, but report-bound runtime remains `NOT_RUN`. Codex owns locating an already-authorized compatible offline compiler or preparing a precise prerequisite request; the operator owns supplying/authorizing any new system package source if one is required. After the compiler is available, the E2E runner installs only the exact committed helper and the designated test roles run the report-bound selector.
- AC-17 dependency provenance: source-reviewed and 7/7 focused contract tests pass, but full report-bound WSL/runtime remains `NOT_RUN`. Codex owns identifying an existing trusted wheelhouse; if none exists, the operator owns providing/authorizing an offline source. Do not download packages.
- S4 MAJOR-01: operator owns any policy authorization or signed waiver for the 52 excluded selectors. Until then, keep them `NOT_RUN` and do not rerun the full matrix as if those rows passed.
- GPT-PM owns any future exact-head approval; the current correlated response is REJECT, so no push/PR/merge gate is satisfied.

This change is documentation/evidence only. It does not close S4 or authorize promotion.
