# S4 QA runner technical design

## Goal

Bind every native QA category run to a reproducible, exact-head VST `TestRun` receipt without changing existing v1/v2 signed bytes or consuming S5's planned v3 static-analysis provenance.

## Non-goals

- No CI, mutation testing, provider/network calls, live service, external repository, or product-source fault injection.
- No HTTP API is claimed. API coverage means the existing Python module surface.
- No independent QA authority or phase state machine is introduced.

## Design

- The committed `docs/qa/categories.json` is the canonical static category and test-ID inventory. It records one primary category, committed pytest node-ID selectors, source-commit provenance, test-owner role, and explicit partial/`NOT_RUN` states. The registry source head and every supported category source head must be ancestors of the candidate HEAD. `regression` is an aggregate over functional, integration, API, and E2E IDs and does not assign a second primary category.
- Each run supplies a run-specific VST v2 task manifest. Before execution, the runner requires the manifest's `TestRun` slots, required test IDs, and exact pytest argv selectors to equal the supported projection of `categories.json`. The registry itself is a predeclared signed artifact; its SHA-256 is written in the report. The receipt's current candidate HEAD is separate from the registry's source-provenance HEAD.
- The QA entry point uses `tools.vst.runner.run_manifest_commands` and the existing v2 `TestRun` contract. The signed request binds manifest digest, candidate HEAD, allowed command, parser-derived outcomes, and artifact digests. It never trusts a caller-provided result or collected-ID list.
- The QA runner is POSIX-only and targets the named `Ubuntu-24.04` WSL runtime, CPython 3.12.3 and pytest 7.4.4. It fails closed on Windows or any other runtime. The Windows `C:\Python314` interpreter named in the original plan is not compatible with the existing v2 signer boundary and is superseded by observed WSL inventory evidence.
- Emit a canonical machine-readable QA report plus bounded stdout/stderr integrity-reference artifacts. The references contain output hashes, byte counts, and capture status, not raw test output. The report records schema version, category/slot, registry and VST manifest digests, source and candidate HEADs, dirty state, interpreter/runtime and lock identity, argv, duration/exit result, expected/collected/executed/skipped/xfail/unexpected IDs, artifact digests, and typed state. Paths are repository-relative; environment values and secrets are not copied.
- The exact per-run report, event, and stream-reference paths are excluded from candidate source-diff evidence only after pre-run validation that each is predeclared, untracked, absent, contained, and unique. Their bytes remain individually included in the signed v2 artifact digests. Any other generated/untracked path remains part of candidate diff scope and can fail the VST diff gate.
- The authoritative gate remains `tools.vst.gate.evaluate`. It must receive the v2 receipt, exact current HEAD, and an artifact resolver that recomputes the report digest. Existing gate rules reject stale HEAD, missing/skipped required IDs, invalid signatures, and missing/hash-invalid deciding artifacts. Unsupported or `NOT_RUN` categories have no passing receipt and remain unmet; waivers remain only those permitted by ADR-0001.
- Seeded-failure IDs are ordinary manifest-required tests. A passing test means unchanged product code returned the expected rejection; its report artifact includes fixture ID and input digest.

## Failure modes

Unknown category, selector/manifest mismatch, duplicate/missing/unexpected IDs, skipped/xfail required IDs, wrong interpreter, changed lock/registry, command failure, malformed parser/event output, missing artifact, digest mismatch, stale HEAD, or invalid signature is typed and non-approving. Structurally valid failures remain v2 `FAIL` where `derive_result()` supports it; zero executed test IDs remain `INCONCLUSIVE` under that contract. Report and receipt outcomes must agree before the signer is called. Partial registries cannot produce signed passing receipts. No fallback interpreter, install, download, empty-success result, or silent category substitution is allowed.

## Rollout and rollback

Introduce the runner and report artifact as new S4 paths. Preserve existing v1/v2 schema and signatures. If report construction or signing fails, do not append a receipt; the category remains unaccepted. A structurally valid failing run may produce a signed `FAIL` receipt, which is non-approving. Roll back by removing the new runner and registry projection; no database migration or state conversion is needed.

## Test plan

After all S4 source coding: functional tests cover manifest/category mapping, parser accounting, report canonicalization, and rejection states; E2E tests cover native pytest discovery, report artifact signing/hash validation, exact-head gate acceptance and stale/missing/corrupt artifact rejection. Only the designated functional and E2E agents author/run these tests. No tests are run during coding.

## Unknowns and ownership

- The S4 plan does not identify a canonical technical service owner for the runner or lock; owner remains `UNKNOWN`. Operator is accountable under delegated sprint work; Codex coordinates and `implementation-engineer` executes.
- Named WSL inventory reported CPython 3.12.3, pytest 7.4.4, iniconfig 1.1.1, packaging 24.0, and pluggy 1.4.0; pytest-asyncio is absent and no current test uses asyncio markers. The hash-pinned lock records pytest plus its required runtime dependencies. No dependency installation is authorized in this source slice.
- The Windows checkout-to-WSL snapshot transfer is not implemented by this runner. Runtime acceptance remains `NOT_RUN` until an approved in-scope source snapshot and signer socket are available inside the named WSL environment; the transfer/system owner is not established in repository records.
- The gate validates the signed receipt and artifact digest, while the trusted runner/parser produces the report. It does not independently interpret arbitrary QA report JSON; this trust boundary must stay explicit.
