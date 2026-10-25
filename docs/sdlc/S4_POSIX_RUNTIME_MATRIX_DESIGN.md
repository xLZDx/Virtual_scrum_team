# S4 POSIX runtime matrix design

**Date:** 2026-10-25  
**Status:** implementation design; not runtime acceptance  
**Scope:** S4 QA runner and test evidence only

## Goal

Complete S4 coverage for required selectors that are valid only on POSIX while preserving the
existing Windows CPython 3.14 profile, exact candidate identity, locked dependencies, and the rule
that a required selector cannot pass through `skip`, `NOT_RUN`, or an absent run.

## Non-goals

No CI, process-kill/timeout/`os._exit` execution, change to VST receipt contracts, dependency
installation during a QA invocation, use of a Git worktree, or claim that S2/S3 external acceptance
is complete. Development remains in `D:\Repo\Virtual_scrum_team`. A disposable candidate clone is
only a test input and must not be used for source changes.

## Current behavior and evidence

- `docs/QA_RUNNER_DESIGN.md` and S4.2.1 specify `C:\Python314\python.exe`; `tools/qa/run.py`
  rejects any other interpreter/profile at lines 772–775.
- S4 AC-11 and AC-14 make skipped or `NOT_RUN` required selectors non-approving. The exact-head
  Windows evidence still has POSIX skips and prohibited selectors; S4 remains open (change 0271).
- Read-only WSL observations: Ubuntu-24.04 has CPython 3.12.3 and ambient pytest 7.4.4. Its
  `/etc/wsl.conf` sets `automount.enabled=false` and `interop.enabled=false`. The `vst-runner`
  account is UID 997 with `nologin` and `/nonexistent`; WSL `--user vst-runner` fails, while
  `setpriv --reuid=997 --regid=988 --clear-groups /usr/bin/id` succeeds and drops supplementary
  groups. Windows can access the distro files under `\\wsl$\Ubuntu-24.04\`.
- The locked pytest 9.0.3 supports Python 3.10 and later according to the [official pytest
  compatibility documentation](https://docs.pytest.org/en/latest/backwards-compatibility.html).
  Ambient pytest 7.4.4 is not accepted; WSL must use a separate target prepared from the committed
  hash lock before tests start.

## Options and choice

1. Keep Windows-only execution and retain current skips/`NOT_RUN`. This is truthful but cannot close
   S4's complete required-selector acceptance.
2. Add a POSIX-only runner beside the current runner. This duplicates runtime, accounting, and
   report logic and risks drift.
3. **Extend the existing runner with explicit platform profiles and a matrix aggregator.** Choose
   this because the same registry, plugin, report accounting, and lock can stay authoritative while
   each selector executes only on its declared platform. No platform-specific skip is converted to
   pass; the matrix passes only when each registered selector passes on every assigned profile.

## Design

- Define strict runtime profiles for Windows CPython 3.14.3, unprivileged Ubuntu-24.04 WSL CPython
  3.12.3, and a narrowly bounded Ubuntu-24.04 root harness for the two identity-isolation selectors.
  Resolve each profile from the running interpreter and OS; accept no caller-supplied interpreter
  fallback. The root harness is local QA evidence only, not an S2 worker receipt or independent
  approval.
  Keep the current hash lock and verify the exact packages/versions in an external dependency
  target for each profile. Report the profile ID and privacy-safe interpreter identity.
- Add explicit selector platform assignments to the committed registry. Selectors without an
  explicit platform restriction run on both profiles. A profile run collects its assigned selector
  IDs only; other IDs are recorded as not assigned to that profile, not as skips or passes.
- Add a matrix validator that consumes exact per-profile reports and artifact ranges. It verifies
  candidate HEAD, registry/lock hashes, profile identity, expected selector assignment, exact
  outcome accounting, capture completeness, and artifact integrity. The lock digest normalizes
  Windows CRLF and POSIX LF checkout bytes to the same LF representation and rejects bare carriage
  returns. The matrix fails on missing,
  stale, corrupt, duplicate, skipped, failed, or policy `NOT_RUN` assigned selectors. It may pass
  only when each registry selector has exactly one passing outcome on every assigned profile.
- Transfer the candidate to WSL as a Git bundle created from the canonical checkout, then clone
  beneath the fixed distro-local `/tmp/vst-s4-candidate` test root and verify full HEAD equality
  before execution. The runner must verify that the candidate resolves under that root and inspect
  `/proc/self/mountinfo` to reject Windows-drive `drvfs`/`9p` mounts, including any mount covering
  the candidate; unrelated WSL `9p` mounts are allowed. Bind the candidate path and mount-table hash
  into the run report and the root-harness proof. Transfer and artifact-return paths must preserve
  bundle/report hashes. No source edits occur in the disposable clone.
- Launch ordinary WSL selectors through a root-owned `setpriv` command that drops to UID 997/GID
  988 and clears supplementary groups before Python starts. Two identity-isolation selectors need
  a separate root harness restricted to exactly `CAP_CHOWN`, `CAP_SETGID`, and `CAP_SETUID`, a
  private network namespace with only the loopback interface, and a passing ephemeral loopback
  socket canary. The absence of any non-loopback interface plus the lack of `CAP_NET_ADMIN` proves
  external egress is unavailable without making an external network request. Its proof is
  run-nonce and candidate-head bound. The wrapper passes an inherited network-namespace file
  descriptor across `unshare --net`; it validates the descriptor target and inode, then compares
  the current namespace with the captured parent after dropping capabilities. This avoids relying
  on `/proc/1/ns/net`, which is inaccessible to the restricted process. The helper source remains
  in this repository but must be installed as a root-owned, non-group/world-writable
  `/usr/local/libexec/vst-s4-root-harness.py` and started with isolated Python (`-I`). It uses only
  fixed system executable paths and standard-library preflight before launching candidate code
  under the reduced capability set. Do not run other tests as root or as UID 997 with the signer
  supplementary group.
- Keep prohibited process-termination selectors in the registry as policy `NOT_RUN`; a matrix
  containing any such required selector remains non-approving. The current generated inventory
  assigns 51 selectors to policy `NOT_RUN` (49 previously identified selectors plus two
  source-documented exclusions), so passing all runnable rows cannot by itself approve S4.

## Failure modes and rollback

An unrecognized OS/Python version, mismatched locked dependency, unsafe identity/group set, bundle
or report hash mismatch, stale head, missing profile report, skipped assigned test, or unaccounted
selector blocks the matrix. The change is local and reversible: revert the new profile/assignment,
matrix, and runner commits while preserving the prior Windows reports as historical evidence.

## Test plan and unknowns

`functional-test-reviewer` owns profile detection, selector assignment, root-proof validation, and
matrix negative tests. `e2e-runner` owns exact-head Windows and WSL matrix execution after all S4
coding and registry refresh are complete. First verify candidate-bundle transfer, the distro-local
candidate/mount boundary, and UID-997 launch with harmless preflight commands; then prepare the
pinned external WSL dependency target separately. No tests, checks, or dependency installs have
been performed for this design. The technical owner for QA runtime/lock maintenance is not
established in canonical records; the operator remains accountable for the delegated sprint and
Codex executes it. Transfer integrity and the exact WSL interpreter path still need an
implementation-level preflight.
