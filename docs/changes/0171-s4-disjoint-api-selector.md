# 0171 — Keep API and integration primary IDs disjoint

## What changed

Replaced the API-category runner selector with `tests/vst/test_e4_runner.py::test_failing_command_nonzero_exit_gives_fail`. The original candidate selector was already registered as the integration category's signed happy-path receipt test. The canonical registry correctly rejects assigning one test ID to two primary categories; no registry or product-code behavior was changed.

## Why

The first focused category execution on commit `c310b6098754036eacbe74ea09062cca929163f6` produced 17 passed, 4 failed, and 1 skipped. All four failures were registry fixtures whose candidate inventory included the duplicate runner ID; the committed-registry validation also exposed that overlap. The registry contract behaved as intended. A distinct runner negative-path test better complements the existing integration happy path while preserving exactly one primary category per ID.

## Verification state

The corrected registry and this record must be committed before rerunning the focused API plus seeded-failure selectors. The rerun's exact command, interpreter, HEAD, and counts will be recorded in a separate evidence artifact.

## Remaining scope

The API category remains `PARTIAL`. The five selected module-level scenarios provide representative coverage, not an exhaustive inventory of every public callable in the named VST modules. The network API remains `UNSUPPORTED`; signer/report-bound acceptance remains outside this local API test run.
