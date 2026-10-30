# S2-4 Runner task-source snapshot

## Acceptance delta

The clean runtime configuration named `/var/lib/vst-runner/repository` as the Runner working
directory, but the installation layout did not provision that source tree. A clean apply could
therefore complete while a later Runner launch failed because its configured working directory was
absent. This change packages the exact pinned Git tree as a deterministic archive and installs a
single root-owned, read-only runtime snapshot at that path. It does not create a development
checkout or per-sprint worktree; all development remains in `D:\Repo\Virtual_scrum_team`.

## Implementation

- `tools/qa/apply_s2_runtime_configuration.py` builds a canonical `canonical-git-tree-tar-v1`
  archive from the requested Git tree, rejects unsafe/non-portable paths and unsupported Git
  entries, pins the archive size and SHA-256, and includes the verified payload in the existing
  apply protocol.
- The remote applier validates the archive and its members before writing, refuses mismatched
  existing snapshots without overwrite, installs atomically, normalizes directories/files to
  read-only modes, and verifies the installed bytes. It runs before configuration files are
  applied and does not start services.
- `docs/sdlc/runtime-config/deployment-source-manifest.json` pins the archive identity and exact
  destination. `installation-layout.json`, `identity-candidates.json`, and
  `bundle-manifest.json` describe the pre-apply inventory and post-apply snapshot contract.
- `tools/qa/collect_s2_runtime_config_inventory.py` and
  `tools/qa/verify_s2_runtime_config_inventory.py` validate the exact snapshot and layout pins.

Candidate source tree: `80c2b81deac364ed6466600fd46af47aafe805e2`; 724 entries; archive size
7,802,880 bytes; archive SHA-256
`c442a770c5580032b85006fa4522db81770955f7db2a2435c5e1d0e4bfcf3284`.

## Verification and reviews

- The designated `e2e-runner` ran six focused selectors at source HEAD
  `aedf712c07eb0cc531852d18443faa497e19bb2d` plus the pre-existing dirty S2-4 worktree:
  **11 passed, 0 failed**, one `pytest-asyncio` deprecation warning, exit 0, 7.41 seconds.
  Exact command, environment, output, and limitations are recorded in
  `docs/sdlc/evidence/s2-4-task-source-snapshot-windows-owner-map-run2-20261030.json` and `.txt`.
- This run used native Windows Python 3.14.3 / pytest 8.4.2. The focused fixture models ownership
  metadata and `chown`/`fchown` calls; Windows-only shims model POSIX modes, directory descriptors,
  binary writes, and unlink behavior. It does not establish live POSIX ownership or filesystem
  behavior. Ubuntu-24.04 WSL execution and the archive producer cross-check in WSL remain
  `NOT_RUN`; a temporary DrvFS mount did not materialize according to `findmnt`.
- `code-reviewer` and `security-reviewer` independently reviewed the canonical archive producer,
  manifest binding, and remote installer; neither found a new BLOCKER or MAJOR. A separate
  read-only test-fixture review confirmed that ownership calls are asserted and the unsafe-parent
  case uses a root-owned parent with mode `0777`.
- No runtime configuration was applied. No service, systemd unit, Store, Runner, claim, probe,
  report-bound TestRun, current E5 attestation, or production dispatch was run by this change.

## Remaining acceptance

S2-4 remains **IN PROGRESS**. The focused source/package tests do not satisfy the task's runtime
acceptance. A fresh exact-identity runtime authorization and bounded POSIX/WSL qualification must
establish current E5 provenance and a real permitted Owner-to-Runner result. Prior one-shot runtime
authorization `8ee40d1a-27a4-4e1b-9129-292a58959aa3` is consumed and must not be reused. Restricted
process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN` as required by the
current scope.

## Owner and next action

Owner: Codex. Complete the S2-4 candidate evidence and documentation, commit the task change with
this record, and push normally. Then obtain a fresh correlated decision bound to the pushed source,
configuration, and run identities; `e2e-runner` executes only that bounded scope. S2-5 remains
queued until S2-4 acceptance and delivery are recorded.
