# S2 safe-selector denominator audit — 2026-10-27

## Decision scope

`e2e-runner` performed a read-only audit of the current S2 acceptance denominator and active restrictions after source/test HEAD `79155fdf9f1f4a7ba71358592ccd54c669a76291`. The audit executed no tests and changed no files.

## Recent correction regressions

| Selector | Exact execution revision | Result |
|---|---|---|
| `test_runner_drops_uid_change_capabilities_before_worker_command` | `dc1741b` | PASS; scoped to the recorded WSL runner profile |
| `test_anchor_append_separates_valid_tail_without_final_newline` | `dc1741b` | PASS; fixture only |
| `test_bounded_git_reader_start_failure_kills_reaps_and_closes` | `dc1741b`, rerun at `79155fd` | PASS at both revisions; fake process |
| `test_bounded_git_reader_failure_kills_reaps_and_fails_closed` | `dc1741b`, rerun at `79155fd` | PASS at both revisions; fake process |
| `test_bounded_git_thread_constructor_failure_kills_reaps_and_closes` | `79155fd` | PASS; fake process |

This is five unique regression selectors and seven executions across the two revisions (four at `dc1741b`; three at `79155fd`). Results are not merged across source/test heads.

## Remaining permitted work

The audit found no additional non-duplicative acceptance selector safe to execute under the current restrictions. Earlier permitted subsets are recorded in `s2-permitted-posix-runtime-evidence-f0bbac8-20261026.md` (56 runner, 19 Store, 38 contract-gate, 14 sandbox-probe and 4 operation-recovery selectors). Repeating those without a new code path would duplicate evidence.

The remaining E4/E8 scenarios require real process-group/descendant termination, Windows Job Object nesting, process-kill, crash/resume, mutation or timeout/restart. They remain `NOT_RUN` under the active restriction. Full egress, workspace, direct-writer, resource-enforcement and persistent-deployment criteria require actual system/environment evidence and cannot be satisfied by synthetic fixtures.

## Attribution

Audit role: `e2e-runner`, GPT-6 Luna, medium effort. Coordinator: Codex. No test command was run for this audit.
