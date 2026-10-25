# 0277 S4 empty supplementary-group runtime contract

**Date:** 2026-10-25  
**Executor:** Codex  
**Baseline HEAD:** `1727776`

## What changed

- Corrected `tools/qa/run.py` to identify the unprivileged WSL profile only when the process is UID
  997, primary GID 988, and has `os.getgroups() == []` after `setpriv --clear-groups`.
- Corrected `tools/qa/matrix.py` to require an empty supplementary-group list in unprivileged WSL
  reports.
- Regenerated `docs/qa/categories.json` from committed sources after the test-fixture change in
  change 0276. The manifest binds test-source commit `1727776` and covers 919 total regression
  selectors: 868 profile-assigned runnable selectors and 51 policy `NOT_RUN` selectors.
- Updated backlog and state records with the exact runtime identity and current test/environment
  status.

## Why

The WSL preparation agent observed `setpriv --reuid=997 --regid=988 --clear-groups` yields primary
GID 988 and an empty supplementary-group list. GID 988 is the `vst-runner` group; adding `[988]` as
a supplementary group would not mean that groups were cleared. The previous runner contract
incorrectly expected `[988]`. The signer account belongs to group 988, so preserving the empty list
is the safer boundary.

## Evidence and verification state

- Test author `functional-test-reviewer` updated the fixture in change 0276 to accept `[]` and reject
  `[988]`; no tests were run.
- The environment agent reported that the hash-verified Linux dependency target is at
  `/var/tmp/vst-s4-qa-deps-6e23fdd3`, readable by UID 997. It contains pytest 9.0.3, pluggy 1.6.0,
  packaging 26.2, iniconfig 2.3.0 and Pygments 2.20.0. Lock SHA-256:
  `6E23FDD343A14E9D85A27F6D86CFB4498C1AF9D33281E05CA5A3FF331C45E691`. Windows pip used its cache;
  no external package download, apt install, or system-Python change occurred.
- The candidate parent `/tmp/vst-s4-candidate` was observed on distro-local ext4 and created for
  `vst-runner:vst-runner`; WSL may clean `/tmp` after idle, so the test agent must recreate/check it
  immediately before cloning and running.
- Product tests, checks, builds, CI, migrations, pytest, WSL runner, and matrix execution were not
  run for this change.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains preserved.

## Shortcoming recorded

Change 0274's initial implementation expected `[988]` despite the approved `--clear-groups` launch.
The environment-preparation evidence caught this before tests ran. Change 0276 corrected the test
fixture; this change corrects the runtime and matrix contract. Do not launch the WSL profile with
`--groups=988` to satisfy the incorrect expectation.

## Next step

Commit the corrected code and manifest, then run the focused functional contract suite at that exact
HEAD. Only after it passes, run the exact-head Windows and WSL category profiles through `e2e-runner`.
