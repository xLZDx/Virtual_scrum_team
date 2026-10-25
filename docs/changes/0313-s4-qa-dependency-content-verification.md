# Change record 0313: verify S4 QA dependency contents

## What changed

- Added `tools/qa/dependencies.py` to select hash-pinned purelib wheels from an existing wheelhouse, validate wheel metadata and internal `RECORD` entries, prepare a new target without pip/network, and compare exact target file bytes with verified wheel members.
- Added `tools/qa/prepare_dependencies.py` as the explicit offline preparation command. Target creation is exclusive; a partial target is left untouched and is not reusable.
- Updated `tools/qa/run.py` to require an external wheelhouse, verify lock/wheel/target contents before pytest and after execution, report only package/wheel/content digests, and disable bytecode writes in the test child.
- Updated `tools/qa/root_harness.py` to pass the wheelhouse through its restricted runner invocation.
- Updated `tools/qa/matrix.py` to require category report schema 3, matrix schema 2, profile-specific lock wheel digests, and matching pre/post target-content evidence.
- Bound wheel parsing to the exact in-memory byte snapshot whose digest matched the lock, avoiding a path-replacement race between hashing and ZIP parsing.
- Added a second preflight immediately before `_run_bounded`, after command and WSL-boundary setup, and require it to match the first verification.
- Updated the S4 plan and QA runner design for AC-17 and the new CLI contract.

## Why

GPT-PM MAJOR-02 found that matching package names and versions did not prove installed file contents matched the lock's wheel hashes. This change compares the external target directly with the locked wheel archives and rejects unsupported layouts or any inventory/content mismatch.

## Contracts and paths

- `tools/qa/dependencies.py`
- `tools/qa/prepare_dependencies.py`
- `tools/qa/run.py`
- `tools/qa/root_harness.py`
- `tools/qa/matrix.py`
- `tools/qa/requirements.lock`
- `docs/S4_QA_DEPENDENCY_PROVENANCE_DESIGN.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` (S4.2.4 / AC-17)
- `docs/QA_RUNNER_DESIGN.md`

## Verification state

Implementation is present in the canonical checkout. Read-only code-reviewer and security-reviewer agents (GPT-6 Luna, medium effort) reviewed the implementation. They confirmed the wheel snapshot and final-preflight fixes and found no other in-scope finding; they agreed that same-identity change-and-restore during pytest is outside this narrowed AC and stays `NOT_VERIFIED`. No test, build, dependency installation, or runtime command was run for this change. Functional-test-reviewer/e2e-runner coverage and exact-head execution remain pending. The pre-existing S4 policy exclusions remain unchanged.

## Ownership and next action

Operator is accountable; Codex is executor. External wheelhouse/target infrastructure technical ownership is not identified in canonical records. Next: finish all S4 source coding, then delegate test authoring/execution to the authorized roles. Runtime preparation requires an already-present trusted wheelhouse; no external download is authorized by this change.
