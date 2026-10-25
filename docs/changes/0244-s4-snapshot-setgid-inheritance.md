# Change 0244: Inherit the S4 snapshot repository setgid at creation

## What changed

- Updated the WSL snapshot receiver to create the empty repository root with mode `2750` beneath the pre-provisioned setgid snapshot-run directory.
- The receiver verifies runner ownership, worker GID and exact mode before cloning into that existing directory, then verifies them again after clone population.
- Removed the attempt to add setgid later with `chmod`; no ownership change or additional capability is required.
- Clarified the creation-time group inheritance contract in the S4 technical design.

## Why

The first snapshot attempt at commit `415916e9cf9b50ea2b5a934378b332054dff0a2d` returned `BLOCKED`. Inspection in the explicitly selected Ubuntu-24.04 WSL distribution showed the run root was correctly `runner:worker` mode `2710`, but the cloned repository root remained `runner:worker` mode `0750`. The runner is not a member of the worker group and cannot reliably set its setgid bit with `chmod` without `CAP_FSETID`. Creating the repository root below the already-setgid run directory lets the kernel establish that boundary at creation time.

## Decisions and ownership

- Preserve the narrow runner capability set. Do not add `CAP_FSETID`, `CAP_CHOWN`, or worker-group membership to the runner.
- Keep the repository source root nonwritable to the worker while inheriting worker-group read/traverse access and setgid for the artifact subtree.
- Accountable task owner: operator under delegated S4 work. Executor: Codex via `implementation-engineer`.
- Test execution owner: `e2e-runner`; canonical QA infrastructure service owner: UNKNOWN in repository records.

## Affected contracts and paths

- WSL snapshot receiver creation and validation in `tools/qa/wsl_snapshot.py`.
- Snapshot and QA artifact directory contract in `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`.

## Verification state

- Base source HEAD: `415916e9cf9b50ea2b5a934378b332054dff0a2d`.
- Snapshot transfer at that head failed with `{"reason":"WSL snapshot transfer failed: source snapshot repository has an unexpected owner or group","schema_version":1,"state":"BLOCKED"}`. A scoped read-only WSL `stat` confirmed owner/group `997:989`, mode `0750` on the repo root; run root was owner/group `997:989`, mode `2710`. No pytest process was started.
- The creation-time inheritance source fix is untested. Required next step: commit this change, transfer a fresh exact-head snapshot, verify exact HEAD/bundle digest and clean status as `vst-runner`, then have the test owner run mapped ACL/artifact and capability/socket selectors. Retry the synthetic report-bound CLI only after those selectors pass.
- Trusted signer, signed report/receipt, authoritative gate consumption, aggregate regression, full E2E denominator and exact-head specialist/GPT-PM review remain separate open gates.
