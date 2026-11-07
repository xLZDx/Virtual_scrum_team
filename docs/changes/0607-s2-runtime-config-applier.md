# Change 0607 — Add a pinned S2 runtime configuration applier

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.11a, ordered preparation for S2-4.11b

## Acceptance delta

The existing runtime installer selects the staged source and installs the six base units, but it
does not install the S2 candidate's 18 non-secret configuration files, five unit drop-ins, or
three absent-only units. The accepted candidate must be installed without overwriting unknown
target content or transferring private keys.

## Code delivered

- Added `tools/qa/apply_s2_runtime_configuration.py`.
- The host reads source bytes from `git show <exact-commit>:<path>`, requires the installer itself
  to match the committed `HEAD` blob, and pins the reviewed runtime-config bundle and layout
  SHA-256 values.
- The root-side WSL implementation independently checks the pinned manifest digests and exact
  26-file destination map, the inventory bytes and five-minute age, the selected 80c2 runtime,
  current WSL boot identity, all target fingerprints, and inactive/no-job systemd state before
  changing any file.
- Installation payloads contain only the 18 configuration files, five drop-ins, and three
  candidate units. Private material is excluded and private-key PEM headers are rejected.
- The tool leaves systemd services inactive, calls `daemon-reload` after file hashes verify, and
  verifies all nine relevant units are loaded-inactive. Store data and private material are not
  read or modified.

## Verification and review

- Focused command: `python -m pytest -q tests/vst/test_s2_runtime_configuration_apply.py`.
- Result: 9 passed, exit code 0, one existing pytest-asyncio deprecation warning. The designated
  functional-test reviewer ran it against working-tree changes at base HEAD
  `cb7e2ed4e786f87d8ea6183d3b943a6f9c915416`. This validates local payload preparation only; WSL
  application was not exercised by the suite.
- Security review: no remaining concrete finding after exact-commit, manifest-map, inventory, and
  systemd reload safeguards were added.
- These local tests and review do not prove that WSL configuration was installed or that the
  runtime journey passed.
- Independent read-only target inventory: `docs/sdlc/evidence/s2-runtime-config-target-inventory-20261030T0320Z.json`,
  SHA-256 `4f1ebdbdc70f84bce6cf53f122e35356a49d814c24acdb9b60ea32ab3e2e4ad0`, captured
  `2026-10-30T03:24:02.766141Z`. It found 19/26 candidate matches; seven known configs differ.
  Five drop-ins and three absent-only units match exactly. Selector remained on a600774, six S2
  units were inactive, there were no pending jobs, and the Store target was absent. Private
  material was inspected only through metadata; its bytes were not read or hashed.

## Current boundary and next action

This change adds the tested installer but does not select the runtime, install configuration,
start services, access Store data, or claim runtime acceptance. S2-4.11b owns the bounded existing
runtime transition, a fresh post-selection inventory, and exact configuration application.
Current-run E5 and the one permitted owner-to-Runner journey remain pending. Restricted process,
crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`.
