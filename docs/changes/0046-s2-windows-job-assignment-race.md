# 0046 S2 Windows Job Object assignment race

## What changed

- `tools/vst/runner.py`: strict Windows runs now create the requested command with the documented `CREATE_SUSPENDED` flag, assign the process to its kill-on-close Job Object, then resume its primary thread using documented Toolhelp and thread APIs. If Job Object creation/configuration/assignment or thread discovery/resume fails, the runner terminates the suspended process and returns a refused, capture-incomplete result without executing command code.
- Non-strict Windows callers retain ordinary process creation and their existing best-effort `taskkill` fallback. POSIX launch behavior is unchanged.
- The module and helper documentation now describe strict containment and the pinned Python behavior.

## Why

Reliability review found that normal `Popen` creation allowed command code to spawn descendants before Job Object assignment. The strict sandbox must establish containment before any requested command code executes. Inspection of `C:\Python314\Lib\subprocess.py` confirmed that Python 3.14's Windows `Popen._execute_child` calls `_winapi.CreateProcess` with its creation flags, then closes the returned primary-thread handle. The implementation therefore uses the documented creation flag and documented Win32 Toolhelp/OpenThread/ResumeThread APIs; it does not access CPython private handles or fall back to unsuspended execution in strict mode.

## Affected contracts and paths

- Strict sandbox process-tree containment in `tools/vst/runner.py`.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and generated `governance/DOCUMENT_REGISTRY.md` record the decision and implementation lesson.

## Verification state

- Source/API inspection only: pinned Python 3.14 `subprocess.py` confirms the creation-flags flow and closure of the primary thread handle.
- No tests, checks, builds, CI, migrations, or Windows runtime probes were run under the task restriction. Correct Windows runtime behavior remains NOT_RUN and must be established by the designated test agent on a Windows host.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation-engineer (`gpt-6-luna`).
- Runtime evidence owner: designated functional/E2E test agent; host provisioning owner is not established in repository records.
- Next: test agent exercises suspended start, child-spawn containment, assignment failure, and resume failure on Windows; record exact host/runtime evidence or NOT_RUN if unavailable.

Agent-Attribution: implementation-engineer (gpt-6-luna); Codex executor
