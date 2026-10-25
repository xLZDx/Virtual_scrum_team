# Change 0201: S4 POSIX symlink selector evidence

## Scope and acceptance mapping

- `test_artifact_through_a_symlink_or_junction_to_outside_is_refused`: prove artifact paths cannot traverse a directory link to an outside target, command execution is refused, and containment returns no path.
- `test_artifact_through_an_internal_symlink_is_also_refused`: prove internal directory links are refused while the corresponding regular file is accepted.
- `test_link_created_by_the_command_itself_gets_a_zero_digest`: related `_can_symlink` probe and post-command symlink behavior.

## Exact-head and environment evidence

- Repository: S4 worktree, branch `s4-native-qa-runner`.
- Branch: `s4-native-qa-runner`.
- HEAD observed before attempted execution: `1c97ee968e6c9f8ab133a3b6d7452e17a17ee600`.
- Baseline worktree: pre-existing untracked `.codex-s4-final-review.patch`; preserved.
- Framework: pytest, imported by `tests/vst/test_e4_runner.py`.
- WSL distribution present: `Ubuntu-24.04`; `/usr/bin/python3`, pytest 7.4.4.
- The distro has no mounted Windows repository, so an initial direct invocation could not load the repository.
- A clean detached worktree was created for the exact committed HEAD under the authorized temporary scratch root; it did not include or alter the separate untracked patch in the baseline worktree.
- Staging command: `git archive --format=tar HEAD | wsl.exe -d Ubuntu-24.04 -- tar -x -C <temporary-wsl-source-root>`. The Windows and WSL SHA-256 for `tests/vst/test_e4_runner.py` matched: `244200b49b600c6b5e639f90159c5f6dbb98a7a84612071fee438e02804fbbe8`; an archive-level hash was not recorded. The temporary worktree and staged WSL source were removed after execution.

## Execution record

- Collection command: `wsl.exe -d Ubuntu-24.04 -- bash -lc "cd <temporary-wsl-source-root> && python3 -m pytest --collect-only -q -p no:cacheprovider tests/vst/test_e4_runner.py::test_artifact_through_a_symlink_or_junction_to_outside_is_refused tests/vst/test_e4_runner.py::test_artifact_through_an_internal_symlink_is_also_refused tests/vst/test_e4_runner.py::test_link_created_by_the_command_itself_gets_a_zero_digest"`.
- Collection result: 3 tests collected in 0.42 seconds.
- Execution command: `wsl.exe -d Ubuntu-24.04 -- bash -lc "cd <temporary-wsl-source-root> && python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_e4_runner.py::test_artifact_through_a_symlink_or_junction_to_outside_is_refused tests/vst/test_e4_runner.py::test_artifact_through_an_internal_symlink_is_also_refused tests/vst/test_e4_runner.py::test_link_created_by_the_command_itself_gets_a_zero_digest"`.
- Execution result: **3 passed, 0 failed, 0 skipped** in 0.30 seconds; Python 3.12.3, pytest 7.4.4, Ubuntu-24.04 WSL2, root UID 0. This is a focused POSIX selector result, not report-bound S4 acceptance or sandbox deployment evidence.
- The original direct invocation failed before collection because `/mnt/d/Repo/Virtual_scrum_team-s4` is absent. Staging from the clean exact-head worktree resolved that environment issue. No source or test files changed; no product/test failure was observed.
- Process UID transition is not implicated in these selectors; this run does not exercise report serialization, trusted signer identity, or runner-to-worker privilege transition.

## Next action and ownership

Operator is accountable for the delegated task; Codex executed the focused test run. Technical owner of the staging service is not established by the inspected sources. The three POSIX symlink selectors are now runtime-proven on the exact committed HEAD. Remaining S4 report-bound and signer/identity acceptance is a separate blocker; preserve `.codex-s4-final-review.patch` and do not infer that this focused result clears those gates.
