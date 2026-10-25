# S4 WSL worker identity helper design

Status: implementation authorized by the operator for one report-bound UID-boundary scenario. This does not authorize process-kill, timeout, mutation, or other existing `NOT_RUN` scenarios.

## Goal

Add a report-bound S4 test proving that a child launched by the unprivileged WSL QA runner (`vst-runner`, UID/GID 997:988) can run only as the fixed worker identity (`vst-worker`, UID/GID 999:989). The child must have no supplementary groups and must be unable to read runner-owned key material or connect to a runner-only Unix socket.

Current behavior: `tools/qa/run.py::_run_bounded` launches pytest as its current identity. `tools/vst/runner.py::_run_one` can drop directly to a worker identity only when its parent is already privileged. There is no S4 selector for the 997-to-999 boundary. The separate `tools/qa/root_harness.py` is a restricted-root report harness and does not provide this transition.

## Non-goals

- Do not run the whole pytest process as UID 999 or change the ownership contract for selection, event, scratch, or report artifacts.
- Do not add arbitrary UID/GID or executable selection to a privileged helper.
- Do not change existing policy exclusions or run process-kill, timeout, process-death, mutation, or E8 bake-off selectors.
- Do not grant capabilities to Python, `setpriv`, the runner, or the worker; do not add sudoers/polkit rules.

## Design

Add a small C helper source under `tools/qa/` and an installer for the selected Ubuntu 24.04 WSL distribution. The installed file has fixed path `/usr/local/libexec/vst-s4-worker-exec`, owner `root`, group `vst-runner`, and mode `4750`. Installation is allowed only after checking the exact WSL identity/configuration, account IDs, clean candidate HEAD and source hash. No repository path is mounted into WSL; test code is staged into the distro-local candidate root.

The helper accepts only the fixed Python 3.12 interpreter, isolated `-I -c` invocation, script and its arguments. It accepts no target identity, executable path, shell command, or environment override. It verifies the caller real UID/GID are 997:988 and effective UID is root, clears supplementary groups, sets all real/effective/saved GIDs to 989 and UIDs to 999, sets `no_new_privs`, replaces the environment with a small fixed allowlist, then uses `execve` without a shell. Failure before `execve` exits non-zero and never starts the child.

Add one S4 functional selector that runs under the ordinary WSL profile as `vst-runner`. The test creates disposable runner-owned file/socket sentinels in its temporary directory, invokes the installed helper, and checks the child's UID/GID/groups and denied file/socket access. The test emits ordinary pytest evidence through the existing report-bound runner; `_run_bounded` and the runner-owned report/scratch artifacts remain owned by UID 997.

## Options considered

1. Fixed setuid launcher for one interpreter and one identity transition — selected because it grants only the requested 997-to-999 drop and keeps the report runner and its artifacts in their existing ownership domain.
2. Set capabilities on Python or `setpriv`, or run the whole category as root — rejected because it grants a broad privilege to a general interpreter/tool or changes the entire runner trust boundary.

## Failure modes

- Missing, stale, writable, wrongly owned, wrongly grouped, or incorrectly permissioned helper: the report-bound selector fails; no fallback runner or identity is used.
- Wrong caller identity, missing target IDs, inability to clear groups, or failed `setresgid`/`setresuid`/`no_new_privs`: helper exits non-zero before executing Python.
- A later source change invalidates helper hash and exact-head evidence; the helper must be rebuilt and reinstalled from the new reviewed source.

## Rollout and rollback

Commit the design first, then helper source and installer. Install only in the already selected `Ubuntu-24.04` distribution. Disable the installed helper by changing its mode from `4750` to `0750` if runtime review finds a defect; preserve the binary for audit and do not delete it. Reinstallation requires the exact candidate HEAD/hash. No production or external account is involved.

## Verification plan

After all implementation changes are committed, `functional-test-reviewer` authors the report-bound selector and registry mapping; `e2e-runner` installs/stages the exact candidate as authorized and runs the focused WSL report. The test proves fixed UID/GID, empty groups, file denial, socket denial, and ordinary report binding. Relevant security review then examines the exact diff and helper installation boundary. Existing prohibited selectors stay `NOT_RUN`.

## Ownership and unknowns

Operator is the accountable task owner; Codex is executor. The repository does not identify a named WSL infrastructure service owner. The technical owner of that environment remains `UNKNOWN`. The exact helper implementation is derived from the approved identity transition and the constraints above; no other privilege is authorized.
