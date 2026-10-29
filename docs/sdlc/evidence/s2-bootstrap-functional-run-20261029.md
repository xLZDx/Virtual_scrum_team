# S2 source and bootstrap-contract focused test run — 2026-10-29

Sprint: S2; Agentic_Framework tracking ID `39b7cc253f5d`.
Gate mapping: TP-06/07/18/19/24/25; REQ-005/006; source-contract coverage for S2-3/S2-4.

## Tested source and files

The product source freeze recorded by Agentic_Framework was HEAD `0fe1d7e5f44f15a22986d145b403dd1b13dc798b`. The reviewed follow-up corrections were committed as `7fbe1e9b99baa37746ee718abfd4558870065ce2` (stage-only guard) and `7e9c5194ab8548ef59f72219528d25ddf5cfcf5b` (independent policy/assignment revocation IDs). The test payload included these source contents; it was relayed from the canonical working checkout into a private WSL temp directory rather than read from a Windows mount.

The test payload included only `tools/vst/*.py`, `tools/qa/prepare_wsl_runtime_plan.py`, and these newly authored files:

- `tests/vst/test_s2_source_staging_plan.py` — working Git archive inputs, deterministic digest binding, canonical checkout/head, missing-artifact refusals and no file output.
- `tests/vst/test_s2_runtime_bundle.py` — closed manifest fields, digest/head/path/unit binding, integer-not-boolean metadata, hard-link and parent metadata refusals.
- `tests/vst/test_s2_machine_source_contracts.py` — closed delegation/assignment schema and time checks, duplicate JSON keys, real synthetic Ed25519 signature verification, wrong-purpose/revoked/bad-signature refusals, read-only Store-snapshot binding, observation raw hashes and fail-closed `UNKNOWN` with no E5 PASS.

Git blob IDs at the tested content were: source plan test `a7bcaec8600d352ccba25ee31d098e754865ae51`, runtime bundle test `a72654e5df8ea099d98b77c9e2f684c53fce80a2`, machine contracts test `a4eb52dabd2115dcf5d3c401b3c8b11866f8cb4f`; runtime bundle source `5bd5af2b63cf525d7abd1ebb2eac8ddc221afabd`, source-plan module `5256446e4c06ad6b4b8bf9c4678ff9aabef1b8a6`, machine observation source `1458bdc64fc4effcab4e42cf52bef5219793d429`. Machine authorization source was corrected in change 0545 and is committed at HEAD 7e9c5194ab8548ef59f72219528d25ddf5cfcf5b (blob 234c406fc0218b9e07392d42f1d749f985e655b5).

## Commands and results

Windows command, from canonical repository root:

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_machine_source_contracts.py
```

Result: **30 passed, 6 skipped, exit 0**; Python 3.14.3, pytest 8.4.2. The six skipped tests exercise the real OpenSSL verification boundary, which requires POSIX root-controlled paths.

POSIX WSL run: the host relayed a tar stream containing only the listed source/test files over stdin into a unique root-owned WSL temporary directory (no Windows-drive mount or second checkout). The command inside that directory was:

```text
/usr/bin/python3.12 -I -S -m pytest -q --basetemp /root/vst-s2-test-<unique-id> tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_machine_source_contracts.py
```

Result: **36 passed, exit 0**; Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4, OpenSSL 3.0.13. This included the real synthetic Ed25519 public-key verification path. Initial attempts found a test expectation mismatch and then a source bug conflating assignment and policy revocation IDs. The test expectation was corrected; Codex fixed the source comparison while retaining separate revocation checks. The final WSL run passed with distinct policy and assignment revocation IDs.

## Limits

These are deterministic source/contract tests, not tests of actual Windows/WSL collectors, runtime installation, systemd, PID 1 credentials, a provisioned Store, owner-to-Runner dispatch, a production signer, or E5. The machine records remain candidate contracts. No identity/key/config was created; no WSL runtime was staged or selected; no service was activated; no Store was opened or changed. Current human E5 remains active. Process-kill, crash/power-loss, mutation, E8 and restricted policy selectors remain `NOT_RUN`. S2 is not accepted by this evidence.

The separate E2E owner covers stage-only preflight and bootstrap-selector journal behavior in their own test file; this record claims none of those executions.
