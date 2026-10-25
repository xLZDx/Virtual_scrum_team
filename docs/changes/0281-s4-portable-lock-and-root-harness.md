# 0281 S4 cross-platform lock binding and restricted root harness

**Date:** 2026-10-25  
**Executor:** Codex with GPT-6 Luna implementation and test agents  
**Baseline HEAD:** `29bf95ed4ea6c4ac6c4d5f07edb73808e74b300f`

## What changed

- Canonicalized the QA dependency-lock digest by normalizing CRLF to LF in the runner and matrix; bare carriage returns remain invalid.
- Replaced the root runner's post-drop `/proc/1/ns/net` read with a version-4 proof bound to the parent network-namespace inode and helper SHA-256 captured before `unshare`.
- Added a shell-free Ubuntu-24.04 WSL helper source that opens and passes a namespace file descriptor, verifies its `net:[inode]` target, enables only loopback before dropping capabilities, and launches the runner through `setpriv` with only `CAP_CHOWN`, `CAP_SETGID`, and `CAP_SETUID` in its bounding set. The repo copy refuses privileged execution; root use requires installing the exact candidate-matching source at the fixed root-owned path with isolated Python startup.
- Changed pytest diagnostics from `--tb=no` to `--tb=short` so failures retain bounded traceback context under the existing redaction and capture limits.
- Added functional contract coverage for cross-platform lock hashing, root-proof inode binding, wrapper argument/process boundaries, capability arguments and traceback selection.
- Updated the S4 runtime design to document these contracts. All development changes are in the canonical `D:\Repo\Virtual_scrum_team` checkout; no sprint worktree was created.

## Why

The candidate reports at `29bf95e` showed Windows and WSL lock hashes differed although the lock text was equivalent, because the Windows checkout contained CRLF where WSL used LF. Root preflight also failed closed when the reduced-capability process could not inspect `/proc/1/ns/net`, and `--tb=no` hid the assertions behind the seven shared functional failures and nine WSL E2E failures. The trusted installed helper captures the parent namespace before dropping capabilities and binds its own bytes to the candidate source; candidate code runs only after the `0xc1` capability restriction.

## Affected contracts

S4 AC-4, AC-11 and AC-14; VST-032, VST-033 and VST-037; `tools/qa/run.py`, `tools/qa/matrix.py`, `tools/qa/report.py`, and the root-profile launcher. Policy `NOT_RUN` selectors are unchanged.

## Verification state

- GPT-6 Luna `code-reviewer` found two MAJOR helper-boundary issues and one MINOR exact-version binding gap. The helper was changed to require a root-owned installed path and isolated Python, avoid candidate imports before `setpriv`, use fixed binaries and sanitized subprocess environments, and bind the installed helper hash to the candidate source. A fresh static review of the final production diff found no remaining BLOCKER, MAJOR, or MINOR finding. No tests or runtime behavior were verified by review.
- The designated functional-test reviewer authored 16 new selector contracts but did not execute them.
- The WSL setup agent's prior environment preflight observed parent namespace inode `4026531840`, child namespace inode `4026532795`, loopback-only networking, and post-`setpriv` `CapEff=CapBnd=0xc1`; it did not exercise the new wrapper or runner. The helper has not been installed at the fixed root-owned path.
- The earlier exact-candidate matrix at `29bf95e` remains non-approving. Root reports were `NOT_RUN`; Windows/WSL had seven shared functional failures, WSL had nine additional E2E failures, and WSL raw lock hashes were stale under the old byte-hash contract.
- Focused tests, registry regeneration, root wrapper execution, category reruns, and the new matrix remain pending. No CI, build, migration, external call, push, PR, or merge was performed.
- Documentation registry generation: `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (257 lines). This is registry generation only, not test or runtime evidence.

## Next step

Regenerate the test-selector registry after committing the authored test source, run the focused module through `functional-test-reviewer`, fix every valid failure, then have `e2e-runner` execute the assigned profiles and root selectors at the exact committed candidate. Preserve all policy `NOT_RUN` results.
