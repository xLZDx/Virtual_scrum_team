# S2-4 fresh run identity candidate — 2026-10-30

## Acceptance delta

The prior one-shot runtime authorization `8ee40d1a-27a4-4e1b-9129-292a58959aa3` is consumed.
The prepared non-secret candidate still carried that run, request and nonce, so it was not safe to
submit as a fresh qualification. This change rotates those correlation identities and updates the
configuration bundle and all source pins. It does not run, retry, activate or authorize a runtime.

## Candidate identity

- Run ID: `s2-runtime-20261030-1977eaba61274396b6b58d069c5cede2`.
- Bootstrap request ID: `98b38065170f468c9943aa8f22160ff9`.
- Probe nonce: `a2a0dcab58b9451281ff0a7b079d4aa2`.
- Bundle-manifest SHA-256: `05530c73ea583f0f7f60963ba9e196082dfb7abf92f86f0a0e2a0ae9ad10f91f`.

These are non-secret correlation values. `PREPARATION_NOT_EXECUTION` remains the recorded state.
The config targets the existing Ubuntu-24.04 runtime and does not include private key bytes.

## Changed inputs and pins

- `docs/sdlc/runtime-config/bootstrap-request.json`
- `docs/sdlc/runtime-config/probe-request.json`
- `docs/sdlc/runtime-config/network-profile.json`
- `docs/sdlc/runtime-config/run-binding.json`
- `docs/sdlc/runtime-config/supervisor-service.json`
- `docs/sdlc/runtime-config/bundle-manifest.json` member sizes and hashes for the five files above.
- `tools/qa/collect_s2_runtime_config_inventory.py`: fresh identities, bundle hash, and exact
  current applier/validator/helper source pins.
- `tools/qa/verify_s2_runtime_config_inventory.py`: fresh candidate identity and bundle hash;
  the predecessor baseline was corrected from the stale `212a… / 334296… / b575…` tuple to the
  observed applied `e520… / 2b5e… / 0aac…` tuple; the older tuple remains in the historic replay
  deny set.
- `tools/qa/apply_s2_runtime_configuration.py`: new candidate bundle hash in local and remote
  validators.

The collector/verifier/applier bundle pins agree. The collector's applier and validator pins were
recalculated from the current file bytes. An independent static consistency command confirmed all
five candidate files match their bundle size/SHA records and that the outer digest matches all
three bundle pins. No runtime command was run for this check.

## Verification status

- `functional-test-reviewer` command (rerun against the latest predecessor correction and source
  pin):
  `python -m pytest -q tests/vst/test_s2_runtime_config_bundle.py tests/vst/test_s2_runtime_config_inventory.py tests/vst/test_s2_runtime_configuration_apply.py`
  — **70 passed**, 1 `pytest-asyncio` deprecation warning, 5.78 s. The run was at repository HEAD
  `055e913c69fd6c33f4290b4c71be1048a2582b32`; because the candidate is uncommitted, test fixtures
  read its config blobs from the worktree. This is not exact-HEAD proof. The suite includes the
  exact predecessor bundle/source pins, the normalized 26-destination fingerprint digest, and
  separate refusal assertions for each `run_id`, `request_id` and `nonce` from all four consumed
  identity tuples (12 replay refusals).
- Python source review — **PASS on the corrected predecessor delta**. The reviewer confirmed the
  `7d1d16f` predecessor/bundle pins and baseline tuple match the 8ee attempt, all 26 destination
  fingerprints match its observed post-apply set, historic tuples use request/run/nonce ordering,
  deduplication is sound, and the collector pin matches the exact verifier SHA.
- Security review — **PASS on the corrected predecessor and replay set**. It verified the exact
  predecessor Git object/bundle/layout pins, the same consumed tuple and all 26 destination
  fingerprints in the correlated runtime attempt, plus the retained historical deny list. No
  tests are run by the reviewer.
- GPT-PM exact-source review request `bbf54c64-e270-4ba6-b195-5af764fa3f07` returned
  **MODIFY / MAJOR-01**. The candidate correctly bound fresh run/request/nonce IDs and rejected the
  consumed set, but its expected installed predecessor still pointed at commit `069be3b` and the
  older tuple (`212a… / 334296… / b575…`). The correlated runtime record shows the later applied
  predecessor (`e520… / 2b5e… / 0aac…`) and exact 26-destination inventory before the preflight
  refusal: `docs/sdlc/evidence/s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3.attempt.json`.
  This was a fail-closed acceptance mismatch, not evidence of a security bypass.
- Codex corrected the predecessor pin to source commit `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`,
  bundle SHA `388e6bb00f97b54bbd456994ccdd399317ab2e527c6f37d8a1b71ce20a280e45`, and identity
  `e520… / 2b5e… / 0aac…`. The formerly expected `212a… / 334296… / b575…` remains in the replay
  denial set. The test owner reran the focused three-file suite against this corrected worktree
  candidate: **70 passed**, one deprecation warning, 5.78 s. It verifies the exact predecessor pins
  and each consumed run/request/nonce component. Candidate blobs are uncommitted, so this is
  worktree evidence, not committed exact-HEAD evidence; repeat after the task commit.
- GPT-PM re-adjudication — **ACCEPT; MAJOR-01 RESOLVED; commit eligible**. Correlation: request
  `24c2372b-5cf8-4144-a690-d22a65db90e0`, job `86b484fa-5597-4cc2-bfbb-225c8560e2db`, user turn
  `3a5905f4-6638-4cac-9e36-30ea7612a7d1`, reply `e8448c22-a258-51a4-af4c-fed00e545f51`,
  `correlated=true`, payload SHA-256
  `16534ecf7d0cd0351170f3bb31de96163b7118ad3298ead18fa9141a6f3e7ce3`. GPT-PM found zero
  remaining BLOCKER/MAJOR and no direct regression blocking commit. The adjudication explicitly
  preserves the separate runtime gate: it does not authorize runtime, production, E5 or reuse of
  consumed authorization `8ee40d1a`. GPT-PM did not independently fetch the complete predecessor
  Git blobs; exact committed-head verification remains required after commit.
- Fresh bounded runtime authorization and runtime qualification — **NOT_REQUESTED / NOT_RUN**.
  Authorization `8ee40d1a-27a4-4e1b-9129-292a58959aa3` remains consumed; do not retry it.
- Runtime preflight, bootstrap, issuer, Supervisor/Runner/dispatch, claim/probe and TestRun —
  **NOT_RUN**.

## Next action

The predecessor correction uses the exact 26 observed destination fingerprints and installed
bootstrap identity recorded by runtime attempt
`docs/sdlc/evidence/s2-runtime-qual-3a3a0e67-s2-runtime-20261030-2b5e04a3.attempt.json`; a
read-only comparison normalizing its `PRESENT/regular/octal-mode` representation to the verifier's
`file/integer-mode` representation matched all 26 destination entries. The immediate consumed
tuple is now the predecessor baseline, and the older baseline tuple remains denied for replay.
GPT-PM accepted the focused MAJOR-01 correction as commit-eligible. Next, commit and normally push
the reviewed source/config candidate; then have the test owner repeat acceptance against committed
exact HEAD. Request a fresh one-shot authorization bound to that pushed HEAD. Only `e2e-runner` may
execute the authorized scope. If preflight fails, preserve the refusal and stop; no broad retry,
bypass, restricted selector or production action is included.
