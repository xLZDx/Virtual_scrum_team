REVIEW ITEM: U1-2 "[VST] AEVE environment probe", VERIFICATION ROUND for your two MAJOR findings of request 888be2d4 (diff base b028eb1, head 128f039, limited to tools/uc/aeve_probe.py and tests/uc/test_aeve_probe.py).

Your findings and the changes:
1. Probe could return READY after AEVE modified its own checkout. Now HEAD and the sorted full status (git status --porcelain --untracked-files=all) are captured before and after doctor/matrix; any difference raises CHECKOUT_CHANGED_DURING_PROBE. Tests: stub doctor and stub matrix each modify a tracked source file or create an untracked file under src/ and exit 0 with valid JSON (4 cases), HEAD moved during the probe, and a control with no change that stays READY.
2. git could be taken from the AEVE checkout through an absolute PATH entry. Now _find_git(exclude=<aeve root>) skips candidates inside the checkout and _git() re-resolves if the cached path is inside it; none left gives GIT_NOT_FOUND. Tests: checkout directory first on PATH with a planted git, real git later; only the checkout on PATH.

Evidence: tests/uc 815 passed, 0 failed, 3 skipped (symlink creation not permitted on this host). Please check only that these two findings are closed and that the fix introduced no BLOCKER/MAJOR regression. Do not ask for full test runs, lint, typecheck or verification scripts (prohibited by the operator).
