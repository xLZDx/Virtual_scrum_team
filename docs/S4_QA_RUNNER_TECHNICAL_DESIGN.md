# S4 QA runner technical design

## Goal

Bind every native QA category run to a reproducible, exact-head VST `TestRun` receipt without changing existing v1/v2 signed bytes or consuming S5's planned v3 static-analysis provenance.

## Non-goals

- No CI, mutation testing, provider/network calls, live service, external repository, or product-source fault injection.
- No HTTP API is claimed. API coverage means the existing Python module surface.
- No independent QA authority or phase state machine is introduced.

## Design

- The validated VST task manifest is the canonical category registry. Each `TestRun` slot names one primary category; its `required_tests` are the exact test-ID denominator, and its `allowed_commands` pin the native pytest selector. `regression` is an aggregate selection over functional, integration, API, and E2E IDs and does not assign a second primary category.
- Any human-readable category catalog is a deterministic projection of the validated manifest. Before execution, the runner rejects a selector or ID set that differs from the manifest. The manifest digest therefore binds category, test IDs, and commands without adding a new v2 field.
- The QA entry point uses `tools.vst.runner.run_and_sign` and its existing v2 `TestRun` contract. The signed receipt binds manifest digest, candidate HEAD, allowed command, parser-derived test outcomes, and artifact digests. It never trusts a caller-provided result or collected-ID list.
- Emit a canonical machine-readable QA report as an artifact. Its relative path and digest are included in the signed receipt. The report records schema version, category/slot, manifest digest, exact HEAD and dirty state, interpreter/runtime and pinned dependency-lock identity, argv, duration/exit result, expected/collected/executed/skipped/xfail/unexpected IDs, artifact digests, and typed state. Paths are repository-relative; environment values and secrets are not copied.
- The authoritative gate remains `tools.vst.gate.evaluate`. It must receive the v2 receipt, exact current HEAD, and an artifact resolver that recomputes the report digest. Existing gate rules reject stale HEAD, missing/skipped required IDs, invalid signatures, and missing/hash-invalid deciding artifacts. Unsupported or `NOT_RUN` categories have no passing receipt and remain unmet; waivers remain only those permitted by ADR-0001.
- Seeded-failure IDs are ordinary manifest-required tests. A passing test means unchanged product code returned the expected rejection; its report artifact includes fixture ID and input digest.

## Failure modes

Unknown category, selector/manifest mismatch, duplicate/missing/unexpected IDs, skipped/xfail required IDs, wrong interpreter, changed lock, command failure, malformed parser output, missing artifact, digest mismatch, stale HEAD, or invalid signature is typed and non-approving. No fallback interpreter, install, download, empty-success result, or silent category substitution is allowed.

## Rollout and rollback

Introduce the runner and report artifact as new S4 paths. Preserve existing v1/v2 schema and signatures. If report construction or signing fails, do not append a receipt; the category remains `NOT_RUN`/`BLOCKED`. Roll back by removing the new runner and registry projection; no database migration or state conversion is needed.

## Test plan

After all S4 source coding: functional tests cover manifest/category mapping, parser accounting, report canonicalization, and rejection states; E2E tests cover native pytest discovery, report artifact signing/hash validation, exact-head gate acceptance and stale/missing/corrupt artifact rejection. Only the designated functional and E2E agents author/run these tests. No tests are run during coding.

## Unknowns and ownership

- The S4 plan does not identify a canonical technical service owner for the runner or lock; owner remains `UNKNOWN`. Operator is accountable under delegated sprint work; Codex coordinates and `implementation-engineer` executes.
- The exact pytest dependency versions are read from the named interpreter's installed environment; a hash-pinned lock must be generated and reviewed before it is accepted. No dependency installation is implied by this design.
- The gate validates the signed receipt and artifact digest, while the trusted runner/parser produces the report. It does not independently interpret arbitrary QA report JSON; this trust boundary must stay explicit.
