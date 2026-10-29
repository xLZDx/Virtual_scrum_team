# Change 0475: Version the S2 worker helper by source commit

## What changed

- Bind the POSIX worker helper to a deterministic installation path ending in
  the full 40-character source commit ID. The root-owned Runner configuration
  must contain that exact path, source commit, source digest, and binary digest.
- Verify helper file type, owner, runner group, setuid mode, link count, bytes,
  and embedded build identity when loading configuration and immediately
  before each child spawn. Capture the verified inode identity when the service
  starts; refuse a changed helper and never fall back to the legacy path.
- Publish a newly built helper only to an absent versioned path by a
  no-replace hard link from private staging. Treat an existing artifact as
  idempotent only when its complete metadata, digest, and build identity match;
  do not change metadata or bytes of existing helpers.
- Pin both `core.autocrlf=false` and `core.eol=lf` for the exact-HEAD WSL source
  archive so POSIX shell sources retain their committed line endings.
- Update sandbox, schema, and systemd deployment contracts. Document that the
  installer does not generate privileged Runner configuration; deployment must
  provision the root-owned config from the audited helper build record.

## Why

The dedicated WSL environment already contains a root-owned setuid helper from
an older build. The fixed-path installer correctly refused to overwrite that
different privileged binary. The first scoped archive correction also proved
insufficient: `core.autocrlf=false` alone still produced CRLF shell members.
Versioned paths preserve the old executable and allow a future exact build to
be installed without replacement; the two Git settings preserve LF bytes.

## Affected contracts and paths

- `tools/vst/runner.py`
- `tools/vst/runner_service.py`
- `tools/qa/install_wsl_worker_helper.sh`
- `tools/qa/install_wsl_runtime.ps1`
- `tools/vst/systemd/README.md`
- `tools/vst/schemas/README.md`
- `docs/SANDBOX_SPEC.md`
- `docs/sdlc/S2_VERSIONED_WORKER_HELPER_DESIGN.md`
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`,
  `core/BACKLOG.md`, `docs/sdlc/STATE.md`

The Runner configuration producer is not present in this repository. Its
root-owned path/head/source-digest/binary-digest fields remain a deployment
dependency and are not synthesized by a worker request or by this installer.

## Decisions and safety limits

GPT-PM correlated request `b84e73a1-55ac-47b0-87f8-20261028f003` and reply
`fc67f0f3-fd09-4c38-81cb-5988d8fe61d9` accepted the versioned-path design only:
preserve the old helper, install by full commit ID, bind path and hashes in
root configuration, verify before execution, use no-replace publication, and
do not add fallback or request-selected paths. The response does not approve
S2, the missing production coordinator, signed E5, effective egress, Windows
or POSIX process containment, restricted scenarios, push, PR, or merge.

## Verification state

- Base HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`.
- Committed code/test HEAD: `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- The functional-test-reviewer authored acceptance tests in
  `docs/sdlc/evidence/s2-versioned-worker-helper-functional-20261028.md`.
  E2E-runner executed the two focused modules four times while fixing test
  fixture defects; attempts 1–3 failed for documented assertion/fixture
  reasons. Attempt 4 passed **179, failed 0, skipped 6** on the dirty base.
  Attempt 5 passed **179, failed 0, skipped 6** using
  `C:\Python314\python.exe` (CPython 3.14.3), exit 0, on exact committed HEAD
  `d5001797cb94113efd9a8dc26e4a15f2dc130976`. Exact command, file hashes and
  all attempts are retained in the corresponding
  `docs/sdlc/evidence/s2-versioned-worker-helper-execution-20261028*.md`
  files. The six platform skips are not passes.
- Exact-head WSL install at `d5001797cb94113efd9a8dc26e4a15f2dc130976`
  succeeded in the already provisioned Ubuntu-24.04 WSL2 environment. The new
  versioned helper, runtime tree, and three units match the recorded hashes;
  the old helper remains unchanged. Units were not enabled or started. Full
  commands, preflight and results are in
  `docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`.
- No keys, root Runner configuration, signed E5 attestation, manifest run, or
  traffic probe were performed.
- Fresh architect, security, reliability, Python, silent-failure, and general code reviews on
  source/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` (evidence-only HEAD
  `59e26ab6897d5cbfb7a12f1d24c67fcb7b50293d`) found no confirmed code BLOCKER/MAJOR. The
  reliability review noted a non-blocking operational limitation: a later runtime revision switch
  procedure should be documented before another rollout; see change 0477. Final GPT-PM S2 gate is
  still pending.
- Existing read-only archive evidence is in
  `docs/sdlc/evidence/s2-wsl-archive-eol-repro-9a5c41d-20261028.md`; it does
  not establish installed/runtime behavior.
- The root-owned Runner configuration has no in-repository producer. The
  required exact path/head/source digest/binary digest contract is documented,
  but root-owned provisioning and any needed keys remain external and have not
  been performed.
- S2-DISPATCH-M01, E5 operator signature, effective egress, platform
  containment, and restricted process/crash/mutation/E8/policy scenarios remain
  separate open criteria. Restricted scenarios remain `NOT_RUN`.

## Commit attribution

Executor: Codex
