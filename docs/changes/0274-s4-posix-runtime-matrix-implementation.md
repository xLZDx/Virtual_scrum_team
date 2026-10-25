# 0274 S4 POSIX runtime matrix implementation

**Date:** 2026-10-25  
**Executor:** Codex  
**Baseline HEAD:** `95989989a483135a06729dfb533f9028318344e`

## What changed

- Upgraded the QA selector manifest to schema 2 with explicit Windows CPython 3.14.3,
  unprivileged Ubuntu-24.04 WSL CPython 3.12.3, and restricted WSL root-harness profiles.
- Assigned seven POSIX-only selectors to WSL, two identity-isolation selectors to the narrow root
  profile, and the thread-start/Job Object selector to Windows. Existing prohibited process-death,
  timeout, E8, and fresh-sandbox rows remain explicit policy `NOT_RUN`.
- Extended registry validation and native runner reports with profile-specific selector accounting,
  runtime identity, root-harness proof binding, and the exact interpreter profile.
- Added `tools/qa/matrix.py` to validate exact-head report references, selector/case outcomes,
  category artifact byte ranges, and overall matrix coverage. The matrix fails closed for missing,
  stale, duplicate, skipped, failed, uncollected, unassigned, or policy `NOT_RUN` acceptance rows.
- Bound WSL evidence to a candidate beneath distro-local `/tmp/vst-s4-candidate`. The runner checks
  mount information before and after execution, rejects Windows-drive mounts and `drvfs`/`9p`
  mounts covering the candidate, and binds the candidate path and mount-table hash into reports and
  the restricted root proof. Unrelated WSL `9p` mounts are allowed.
- The root-harness preflight now verifies the current network namespace has only loopback and
  successfully exercises an ephemeral loopback socket. With no non-loopback interface and no
  `CAP_NET_ADMIN`, the harness has no external egress route; no external canary request is made.
- Updated the S4 plan, QA runner design, matrix design, state, and backlog. Regenerated
  `docs/qa/categories.json` from committed test sources.

## Why

The Windows-only run leaves required POSIX selectors skipped, and S4 acceptance does not allow a
skip to count as a pass. A shared registry and exact-head matrix can combine assigned native
profiles without treating a selector skipped on another platform as evidence. The root harness is
limited to two selectors that test filesystem and key read/write isolation; its proof is explicitly
local QA evidence and does not replace an S2 worker receipt or human approval.

The candidate is constrained to a distro-local `/tmp` directory because the canonical development
checkout remains in `D:\Repo\Virtual_scrum_team` and WSL automount/interop are disabled. A
read-only WSL `findmnt -rn -o FSTYPE,SOURCE` observation showed an unrelated `9p drivers` mount in
the distro, so the code rejects only Windows-drive sources globally and `drvfs`/`9p` mounts that
cover the candidate; rejecting every `9p` mount would make the approved WSL runtime unusable.

## Acceptance and verification state

- **Implemented in working tree:** runtime profile assignments, profile-aware registry and runner,
  matrix validator, WSL candidate/mount boundary, and root-harness proof contract.
- **Generated:** `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`
  completed with exit code 0 and wrote `docs/qa/categories.json`. The manifest inventories 904
  regression selectors: 853 assigned runnable selectors and 51 policy `NOT_RUN` selectors (49
  existing prohibited rows plus two source-documented sandbox/E8 exclusions).
- **Read-only environment observation:** `wsl.exe -d Ubuntu-24.04 -- findmnt -rn -o FSTYPE,SOURCE`
  reported an unrelated `9p drivers` mount. No WSL installation, mount change, test, or runtime
  acceptance was performed.
- **Not run:** product tests, checks, builds, CI, migrations, pytest execution, WSL runner execution,
  dependency installation, matrix execution, root-harness preflight, push, PR, or merge.
- **Process deviation:** the primary agent invoked `git diff --check` once while reviewing an
  intermediate diff before coding was complete. It returned no diagnostics and changed no files.
  This was out of sequence; it is recorded in `core/LESSONS_LOG.md`. No test was executed.
- The untracked pre-existing `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and
  excluded from this change.

## Remaining acceptance

The runtime matrix is not tested, installed, or runtime-proven. `functional-test-reviewer` must
author and run focused profile/registry/matrix contract tests after the coding commit; `e2e-runner`
must prepare the disposable WSL candidate beneath `/tmp/vst-s4-candidate`, prepare the locked
external dependency target, and run assigned exact-head profiles. Fifty-one policy `NOT_RUN`
selectors remain non-approving. Their operator/safety prohibitions are separate S4 blockers and
must not be waived or relabeled by this code.
