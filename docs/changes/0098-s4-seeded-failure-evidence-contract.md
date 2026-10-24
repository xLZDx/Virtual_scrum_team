# 0098 S4 seeded-failure evidence contract

## What changed

- Added a bounded committed catalog at `docs/qa/seeded_failures.json`. It is explicitly `NOT_RUN` and empty until designated test owners author concrete unchanged-product fixtures and link test IDs.
- Added strict catalog validation for state, fixture count, unique stable IDs, canonical JSON input records up to 16 KiB each, SHA-256 input digests, stable rejection codes, and exact one-to-one fixture/test-ID mapping.
- Added `record_seeded_failure_observation()` to the pinned pytest plugin. It accepts a bounded observation only while the exact linked test node is running and emits the event protocol as schema version 2.
- Added report-bound catalog digest and fixture metadata, and included the catalog in the signed v2 artifact set. The report compares the full expected fixture set with observed IDs, input hashes, expected/observed rejection codes, and test IDs. Missing, extra, duplicated, or mismatched evidence prevents a passing report and a report/v2-result disagreement aborts signing.
- Updated the S4 plan, technical design, backlog, decision and lessons records. Regenerated the document registry.

## Why

S4 acceptance requires each known-defect fixture to remain an ordinary test against unchanged product code and to record its controlled input hash, expected rejection, observed rejection and test ID. A green aggregate count alone does not retain this mapping. Mutation testing and product-source fault injection remain prohibited by ADR-0001.

## Affected contracts and paths

- `docs/qa/seeded_failures.json`: committed catalog and provenance artifact.
- `tools/qa/registry.py`: catalog parser and category/test-ID consistency checks.
- `tools/qa/pytest_pass_plugin.py`: event observation helper and event schema version 2.
- `tools/qa/run.py`: catalog loading and signed artifact inclusion.
- `tools/vst/runner.py`: catalog validation, event comparison, report fields and fail-closed result agreement.
- S4 design, sprint plan, backlog, decision log, lessons log and generated document registry.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- `functional-test-reviewer` and `e2e-runner` own concrete fixture/test authoring and execution after all S4 source coding is complete.
- Catalog source/fixture service owner is not established in canonical project records (`UNKNOWN`).
- No product source is patched, monkeypatched, or rewritten to inject defects. The event observation is accepted only from the matching active pytest node, and the test owner must exercise the unchanged product boundary.
- The empty catalog remains `NOT_RUN`; source plumbing does not imply that fixture scenarios or S4 acceptance are complete.

## Verification state

- Manual source and diff inspection only. No tests, checks, builds, CI, dependency installation, migration, or QA execution were run.
- The fixture API/event/report path, input hashing, mismatch rejection, and signed catalog artifact remain unverified at runtime. Required tests belong to the designated test agents after the S4 code freeze.

## Follow-up

1. Complete the remaining S4 source implementation.
2. Have the designated test roles add real synthetic fixture inputs and exact test IDs, change the catalog/category state only when the full denominator exists, then author and run focused tests.
3. Provision the authorized in-scope WSL source snapshot and signer socket for native v2 runtime acceptance; technical platform/service owner remains `UNKNOWN`.
