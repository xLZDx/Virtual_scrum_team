# Change 0476: Record exact-head S2 helper tests and WSL installation

## What changed

- Recorded the focused functional test result for change 0475 at exact committed
  code/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Recorded the exact-head Ubuntu-24.04 WSL runtime installation, versioned
  helper identity, archive LF evidence, and before/after comparison proving the
  existing legacy helper was preserved.
- Updated S2 state, backlog, lessons, and the generated document registry to
  distinguish these completed checks from still-missing production/runtime
  acceptance.

## Why

The initial test runs on the dirty diff exposed assertion and fixture defects.
After their correction, a clean committed-head run passed. A separate exact-head
WSL installation then proved the installer can publish the new helper without
replacing the older root-owned setuid artifact. These results need durable
provenance before exact-head specialist review and GPT-PM adjudication.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-versioned-worker-helper-execution-20261028-attempt5.md`
- `docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`
- `docs/changes/0475-version-s2-worker-helper-by-commit.md`
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/BACKLOG.md`,
  `core/STATE.md`, `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Change 0475 exact committed HEAD:
  `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Focused command:
  `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py`.
  Result: **179 passed, 0 failed, 6 skipped**, exit 0, CPython 3.14.3. The
  six platform-conditional skips are not passes. Full command, hashes and
  warning are in the attempt-5 evidence file.
- Exact-head WSL installation succeeded in the existing Ubuntu-24.04 WSL2
  distribution. The legacy helper retained its prior owner/group/mode, digest,
  and embedded version. The new versioned helper and runtime files matched the
  exact commit and archive digests. Three systemd unit files were installed
  but not enabled or started. See the linked install evidence for all commands,
  hashes, preflight facts and scope limits.
- No Runner root configuration, signing keys, signed E5 attestation, service
  activation, manifest execution, effective egress probe, Windows containment
  proof, or prohibited process/crash/mutation/E8/policy selector was performed.
- `S2-DISPATCH-M01` remains MAJOR/OPEN: no production coordinator source or
  trusted caller identity exists in the in-scope repository. No new scheduler,
  CLI, queue, spool, or assignment authority was created.
- Fresh specialist reviews found no confirmed code BLOCKER/MAJOR; their scope and one
  non-blocking operational limitation are recorded in change 0477. The exact-head GPT-PM final S2
  gate remains pending.
  No push, PR, or merge is authorized by this evidence-only change.

## Next action and owner

Codex requests GPT-PM's final S2 gate on the reviewed exact source/evidence
head. The operator owns the actual
root-owned Runner configuration/credentials and current-run E5 signature; until
those exist, service execution, signed inventory and effective network
acceptance remain unproven. Keep prohibited selectors `NOT_RUN` and do not
start S3.

## Commit attribution

Executor: Codex
