# Change 0334 — Include ordinary untracked files in DiffGate evidence

## What changed

- Corrected `_diff_paths()` to enumerate ordinary untracked and ignored files separately and include their sorted union in changed-path and supplemental content-digest evidence.
- Added five signed temporary-Git integration cases covering ordinary out-of-scope, blocked, allowed, ignored/ordinary combined, and ignored out-of-scope files.
- Recorded the correlated GPT-PM MAJOR, test results, and the implementation agent's accidental non-evidentiary `git diff --check` invocation.

## Why

GPT-PM identified that `git ls-files --others --ignored --exclude-standard` returns ignored paths but misses ordinary non-ignored untracked files. Since `_diff_paths()` supplies the paths to the scope gate and hashes supplemental file content, the missing class could let an out-of-scope untracked file escape signed DiffGate evidence.

## Evidence and verification

- Correlated GPT-PM request `172f1abb-0023-48b8-ab8b-57b6b5b1f528`, reply `da8c2bb2-56f9-5c3b-923a-a0674163ba9c`: NOT APPROVED; MAJOR S2-M01 confirmed.
- Working-tree source HEAD: `7d801671125435da3fc5152813ecd52d4e481dd7` (dirty).
- Designated `e2e-runner` reports 5 new integration cases passed, full DiffGate module 22 passed, DiffGate gate selection 5 passed and runner provenance selection 7 passed; Python 3.14.3, one warning per command.
- Exact commands, scope and limits: `docs/sdlc/evidence/s2-diffgate-untracked-fix-tests-7d80167.md`.
- The implementation agent inadvertently ran `git diff --check`; no output was recorded and it is not used as verification evidence. No other checks, builds or migrations were run.
- Exact committed-head tests and review are pending.

## Remaining acceptance and owners

- Operator remains accountable; Codex owns remediation and coordination; designated test roles own test authoring/execution; GPT-PM owns the exact-head gate decision.
- S2 source MAJOR S2-M01 is addressed in the working tree but is not yet accepted at a committed head. Windows Job Object, POSIX containment, run-bound resource/egress, and policy-prohibited scenarios remain independently open or `NOT_RUN`.
- No push, PR, merge, waiver, or external system change is authorized by this record.

Change: 0334  
Executor: Codex
