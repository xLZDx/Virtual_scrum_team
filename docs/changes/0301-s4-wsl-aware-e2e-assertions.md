# 0301 S4 WSL-aware E2E report assertions

**Date:** 2026-10-25  
**Executor:** Codex  
**Base HEAD:** `6aa5c428fe48206fef8f0c250d9d6bdfd6bffe44`

## What changed

The designated functional-test reviewer updated `tests/qa/test_s4_e2e_runner_cli.py` so the synthetic E2E contract asserts the interpreter appropriate to the report's runtime profile: the approved Windows `python.exe` path for Windows and the approved `python3.12` path for WSL. The invocation must still use `-m pytest`, the expected module path, and no explicit node selectors, including the prohibited timeout selector.

For WSL reports, the privacy assertion now permits the candidate root only in `runtime_boundary.candidate_root`, after requiring that field to equal the exact synthetic candidate path under `/tmp/vst-s4-candidate/`. The exact candidate path is masked in a copy used for the leak scan. Other candidate-path occurrences, target/tmp paths, secrets and Windows user paths remain prohibited.

## Verification state

- Source diff manually reviewed; no product runtime code changed.
- No tests, checks, registry generation or runtime categories have been run for this change.
- The selector registry is stale until regenerated from the committed test source. The focused Windows E2E rerun must also capture the synthetic runner's exact report reasons when it is blocked.
- The prohibited timeout selector remains `NOT_RUN` and must not be selected or collected.

## Next

Commit this test-source correction and its decision record, refresh the selector registry in a separate commit with a separate change record, then have the designated test agents run focused Windows and WSL safe E2E cases at the exact refreshed head. Continue to the full assigned matrix only after the focused contracts pass.
