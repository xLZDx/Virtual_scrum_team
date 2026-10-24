# 0120 S5 v3 analyzer evidence contract and gate

## What changed

- Added an opt-in v3 TaskManifest analyzer policy and a strict v3 `StaticAnalysis` receipt while keeping v1/v2 receipt shapes and signed bodies unchanged.
- Added a separate analyzer signature domain and gate trust mapping; analyzer key IDs and profile/source/report/run/head/epoch/scope provenance are bound to the signed receipt.
- Required complete checked/unsupported rule partitions, typed findings with evidence digests, static acceptance IDs pinned by the manifest, and non-approval when findings exist.
- Added gate resolution for report/finding artifacts and a trusted source-tree digest callback.
- Added a deterministic bounded SHA-256 source-tree digest utility, and allowed the existing v2 TestRun runner/store path to operate under a v3 manifest while retaining v2 TestRun receipts.
- Reject duplicate covered acceptance IDs in v3 StaticAnalysis evidence; keep older receipt contracts unchanged.
- Updated the human-readable schema and S5 plan/backlog to record the contract, trust boundary, and actual unsupported runtime scope.

## Why

S5 needs a versioned, independently authenticated static-analysis evidence boundary. V1/v2 cannot gain provenance fields without changing their signed bytes, and the VST gate must not trust analyzer-supplied digests or claim real AEVE availability that is not evidenced in this checkout.

## Affected contracts and paths

- `tools/vst/contracts.py`: v3 manifest/receipt dispatch, strict analyzer provenance, rule partition, findings, and result derivation.
- `tools/vst/signing.py`: `ANALYZER_V3_LABEL` domain.
- `tools/vst/gate.py`: separate analyzer trust roots, v3 manifest binding, report/finding/source digest resolvers, and acceptance contribution.
- `tools/vst/source_tree.py`: versioned digest of exact regular files from a supplied snapshot, with path, symlink, mutation, file-count, and byte ceilings.
- `tools/vst/runner.py` and `tools/vst/store.py`: retain v2 TestRun receipts and store behavior under a v3 manifest; the store defers analyzer signature verification to the authoritative gate trust input.
- `tools/vst/schemas/README.md`, `docs/S5_AEVE_GATE_PLAN_2026-10-24.md`, and `core/BACKLOG.md`: schema and remaining integration gates.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- `analysis_scope` describes analyzer inputs and is independent of `change_scope.allowed_paths`, which constrains candidate edits.
- A v3 StaticAnalysis attestor uses a manifest-pinned analyzer key ID and `ANALYZER_V3_LABEL`; the analyzer executable receives no signing key. Analyzer keys are separate from worker, supervisor, operator, event, reviewer, and runner-signer roots.
- `vst-source-tree-c14n-sha256-v1` hashes sorted path/size/raw-byte-digest records using canonical JSON. The helper hashes a supplied snapshot; it does not create or enforce its read-only boundary.
- Any finding derives `FAIL`; partial required coverage derives `INCONCLUSIVE`. Optional unsupported rules do not reduce coverage for manifest-required rules.
- No AEVE source, adapter, key, private provisioning value, or external technical owner is inferred. Those runtime identities remain `UNKNOWN / NOT_VERIFIED`.

## Verification state

- Manual source/document review only. No tests, builds, CI, migrations, package installation, analyzer execution, or sandbox runs were performed. The primary session accidentally invoked `git diff --check` during review; it returned no output. No other check command was run.
- V1/v2 canonical compatibility, v3 gate behavior, source-tree hashing, signer distinctness, and exact-head rejection require functional/E2E agent verification after S5 coding is complete.
- Actual AEVE adapter/runtime and analyzer attestor provisioning remain `NOT_RUN` pending an authorized in-scope source identity and trust boundary.

## Follow-up

1. Have functional-test-reviewer and e2e-runner author and run the S5 mapped denominator on the final committed candidate.
2. Complete relevant specialist reviews and fix valid BLOCKER/MAJOR findings on one exact head.
3. Keep real analyzer coverage `NOT_RUN` until its source identity, license, capability inventory, attestor owner, and isolated runtime are evidenced.
