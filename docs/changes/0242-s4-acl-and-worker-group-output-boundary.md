# Change 0242: Close S4 ACL and worker-group artifact boundaries

## What changed

- Extended `tools/vst/sandbox.py` signer IPC validation to reject present POSIX access ACLs on traversed parent directories and the endpoint, and default ACLs on the immediate parent. Missing or unsupported ACL xattrs are handled explicitly; other inspection errors fail closed.
- Changed `tools/qa/wsl_snapshot.py` to set and verify the runner-owned snapshot repository root as worker-group mode `2750`, allowing setgid group inheritance while keeping the worker read-only at the source root.
- Changed `tools/qa/run.py` to create and verify the runner-owned `.vst-qa-runs` base as worker-group mode `2710` and per-run artifact directories as mode `0730`; removed the `chown` requirement and its need for `CAP_CHOWN`.
- Updated the S4 technical design to describe the ACL and output-group contracts and their remaining runtime proof requirements.

## Why

The read-only S4 security review at `abc9b410d40252539c617be146338c3f0cb6e256` identified that mode-bit checks alone did not reject named POSIX ACL grants to the worker. Separately, the report-bound CLI reached artifact setup but failed because runner UID 997 could not `chown` its run directory to worker GID 989. The fixes preserve the least-privilege worker identity transition: the worker gets read/traverse access to source and write/traverse access only to its isolated run artifacts, without broadening the runner unit's capabilities.

## Decisions and ownership

- Preserve mode/owner checks and reject ACL-bearing signer paths rather than treating the signer peer-UID check as a substitute for the filesystem isolation contract.
- Carry the worker group from a setgid snapshot root instead of adding `CAP_CHOWN` or changing the runner's primary group.
- Accountable task owner: operator under delegated S4 work. Executor: Codex via `implementation-engineer`.
- Test author and executor: `e2e-runner` or `functional-test-reviewer`. Canonical technical owner of the S4 QA runner/signer infrastructure: UNKNOWN in repository records.

## Affected contracts and paths

- Signer socket parent and endpoint access checks in `tools/vst/sandbox.py`.
- Read-only snapshot source and isolated QA output ownership/modes in `tools/qa/wsl_snapshot.py` and `tools/qa/run.py`.
- S4 design: `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`.

## Verification state

- Base source HEAD: `abc9b410d40252539c617be146338c3f0cb6e256`.
- Before these changes, the two focused worker capability/socket selectors passed on a clean Ubuntu-24.04 WSL snapshot at `abc9b410d40252539c617be146338c3f0cb6e256` (2 passed, 0.33 seconds). That run predates this ACL and artifact ownership patch and does not verify it.
- An earlier isolated synthetic `tools.qa.run` attempt on candidate `8b95c80509b5d2b316f631c060399329a7cb6f03` was blocked at `_safe_output_dir`: `os.chown(..., -1, 989)` returned `EPERM`; no report or receipt was produced. Evidence was captured by `e2e-runner` under the S4 WSL snapshot's `.vst-qa-runs/cli-functional-52f61a4ecbf04d548b5b5a313149d44e/functional-cli-blocked-evidence.json`.
- The ACL guard, group inheritance, mapped regression coverage, and report-bound retry remain pending fresh exact-head execution. No trusted signer, aggregate regression, or full E2E denominator claim is made by this change.
- A read-only errno probe on Ubuntu-24.04 observed `ENODATA` (61) for absent ACL xattrs in the selected directories and `ENOTSUP` (95) on `/proc` and `/sys`; this is narrow API behavior evidence, not a test of the committed guard.
- No product tests, builds, or checks were run against this patch while coding.
