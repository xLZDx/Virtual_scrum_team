# S2-3: bind runtime staging to the reviewed source and target inventory

## Task and baseline

- Sprint task: S2-3, immutable non-secret runtime bundle and bounded WSL qualification
  preparation.
- Repository: `D:\Repo\Virtual_scrum_team`.
- Baseline HEAD: `c97836029a5d94ff84dee5cb15d1757efd5525c3` on
  `s2-canonical-continuation`.
- The baseline tracked worktree was clean. Pre-existing untracked PM Bridge artifacts and
  the baseline plan/inventory artifacts were preserved.
- The source/tests and this record were committed as `f34cefd0827f631466e66b39a03b1d999c770388`.
  That commit is not yet accepted or pushed. No S2-3 stage, runtime selection, systemd
  installation/activation, Store operation, key operation, or E5 attestation was performed.

## Acceptance addressed

The fresh GPT-PM review request `8e75b1f0-7272-48bd-98d1-15a74454967d`, bound to baseline
HEAD above and input SHA-256
`f5532216c6bf52e302eaa3eec1f7bcfd4c295ba6d6dc1ccd8e43d79ea534f0b5`, returned `MODIFY` and
identified two MAJOR findings:

1. The approved source plan did not let the WSL receiver prove every extracted archive member
   still matched the reviewed source bytes and type.
2. A newly created staged runtime tree did not receive the same complete fail-closed check
   required for an already existing destination before publication.

The review also confirmed the previously reported `parseAcknowledgements()` redaction was not
present in the committed expression; that separate source-fidelity conclusion is not changed by
this task.

## Code and contract changes

- `tools/qa/prepare_wsl_runtime_plan.py` emits source-plan V2 with a complete archive member map
  containing each member's path, type, size, and SHA-256.
- `tools/qa/verify_wsl_source_bundle.py` verifies the extracted bundle against the exact map,
  including required members and rejection of missing, extra, changed, symlink, hard-link, and
  special-file entries.
- `tools/qa/verify_wsl_runtime_stage.py` checks the complete fresh runtime tree and marker
  against the same reviewed map before publication; the existing-destination path retains its
  exact identity and tree comparison.
- `tools/qa/install_wsl_runtime.ps1` transports the reviewed source plan and non-secret target
  inventory together, verifies their exact hashes and source identity, and rejects an inventory
  older than 300 seconds (or more than 30 seconds in the future). The WSL receiver repeats the
  freshness/source checks after transfer.
- `tools/qa/install_wsl_worker_helper.sh` checks the executing compiler's selector, resolved path,
  root-owned metadata, and binary digest against the reviewed inventory before compiling.
- `tools/qa/install_wsl_runner_runtime.sh`, `tools/vst/runtime_bundle.py`, and
  `tools/vst/bootstrap_runtime.py` carry source-plan, target-inventory, and compiler provenance
  through the immutable runtime marker and post-stage selection manifest. The bootstrap verifier
  requires exact schema-3 marker equality with all provenance fields from the reviewed manifest;
  it no longer accepts the obsolete schema-1 marker shape.
- `docs/sdlc/backlog.md`, `docs/sdlc/design.md`, `docs/sdlc/test-plan.md`, and
  `docs/sdlc/verify-evidence.md` record the current task state and mapped acceptance.

## Review and verification

- Independent `code-reviewer` follow-up confirmed both PM findings are addressed in the current
  delta and found no remaining blocking install-contract issue. It separately confirmed the
  existing-runtime schema-3 marker has the same exact fields written by the installer and checked
  by the stage verifier. This is static review, not runtime proof.
- The designated `e2e-runner` executed the focused selection in Ubuntu 24.04 WSL with Python
  3.12.3 and pytest 7.4.4 at source baseline `c97836029a5d94ff84dee5cb15d1757efd5525c3`.
  Initial result: 46 passed and 8 failed; two were hard-link assertion-message mismatches and six
  exposed the obsolete schema-1 bootstrap check. After changing only those two test matchers and
  correcting bootstrap schema-3 provenance comparison, the same selection passed: **54 passed,
  0 failed, 0 skipped**. The exact command was:
  `python -m pytest -q tests/vst/test_s2_wsl_bundle_verifiers.py tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_bootstrap_runtime.py tests/vst/test_s2_stage_only_install.py`.
  The auditable run used and removed `/run/vst-test-d6d3fea7d21c4d01900b37860a29c2fa`. No
  installer, runtime, system service, Store, or key operation was performed. Its exact input-file
  inventory, transfer-manifest digest, and run ID are recorded in
  `docs/sdlc/evidence/s2-3-focused-posix-rerun-d6d3fea7d21c4d01900b37860a29c2fa.md`.
- Independent `code-reviewer` reviewed the final bootstrap marker delta: exact schema-3 fields
  match the bundle builder and stage verifier, with missing, extra, or mismatched fields rejected;
  no blocker was found. This is static review, not runtime proof.
- `git diff --check` completed without whitespace errors; Git warned that
  `docs/sdlc/verify-evidence.md` will be normalized from CRLF to LF on a future Git write.
- Exact-head GPT-PM review request `d4577012-d47b-4b43-b598-bfcbb8d064c9` returned `MODIFY` on
  commit `f34cefd0827f631466e66b39a03b1d999c770388`. It confirmed both original MAJOR findings
  resolved, and found M-S2-3-03 in the existing-runtime verification branch: `inventory_sha` was
  referenced but omitted from the embedded Python argument list/unpacking. The focused fix and
  required direct matching/mismatching marker regression are recorded in
  `docs/changes/0581-s2-3-existing-runtime-provenance-pin.md`. S2-3 remains open; the 54-case test
  result above does not cover this branch and was not run against commit f34.
- The actual WSL target inventory must be recollected with the final source HEAD, include
  `source_head` and `observed_utc`, and remain within the five-minute window at stage time.

## Remaining acceptance and next actions

1. Finish the direct existing-runtime regression and argument fix tracked in change record 0581;
   execute that direct regression against its committed source via `e2e-runner`.
2. Obtain a focused correlated GPT-PM exact-head re-review of only M-S2-3-03 and its direct
   regression; the current `MODIFY` is not approval.
3. After code review acceptance, generate a new exact source plan and fresh source-head-bound WSL
   inventory. Obtain a fresh
   correlated GPT-PM verdict for the exact bundle before running only the previously authorized
   stage-only operation.
4. After stage-only, create the complete runtime/helper manifest and obtain its separate review.
   Do not select the runtime, activate services, touch an existing Store, generate production keys,
   or claim current E5 from this record.

S2-3 remains open until these acceptance steps are complete.
