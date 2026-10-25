# 0276 S4 WSL identity test fixture correction

**Date:** 2026-10-25  
**Executor:** Codex with `functional-test-reviewer` as test author  
**Baseline HEAD:** `e21f6c1`

## What changed

Updated the WSL identity test fixture in `tests/qa/test_s4_functional_runtime_matrix.py` so UID
997/GID 988 is accepted only with an empty supplementary-group list. The fixture explicitly rejects
`[988]` as an additional group and records `[]` in unprivileged WSL report examples.

## Why

The WSL preparation agent observed that `setpriv --reuid=997 --regid=988 --clear-groups` produces
UID 997, primary GID 988, and `os.getgroups() == []`. GID 988's group membership includes
`vst-signer`; using `--groups=988` would add it as supplementary membership. The test contract now
requires genuinely cleared supplementary groups.

## Verification state

- Test author: `functional-test-reviewer` (GPT-6 Luna; exact effort is `UNKNOWN` in launch evidence).
- Manual source and environment review only; no tests, checks, builds, or runtime QA were run.
- No implementation source or registry change is included. Regenerate the selector manifest after
  this test-source commit and update the implementation in the next coherent commit.
- WSL environment preparation also staged locked Linux wheels at
  `/var/tmp/vst-s4-qa-deps-6e23fdd3` (pytest 9.0.3, pluggy 1.6.0, packaging 26.2, iniconfig 2.3.0,
  Pygments 2.20.0). The candidate parent under `/tmp` can be cleaned after idle and must be
  recreated immediately before candidate cloning. No apt or system Python changes occurred.
- The existing untracked S2 evidence file remains untouched.

## Next step

Commit this test-source correction. Then regenerate the manifest from committed tests, update runner
and matrix identity expectations to `supplementary_groups: []`, and commit the corrected profile
contract before running tests.
