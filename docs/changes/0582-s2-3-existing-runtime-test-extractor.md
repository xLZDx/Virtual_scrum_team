# S2-3: locate the committed existing-runtime regression block by contract

## Task and evidence

- Sprint task: S2-3, direct regression for GPT-PM finding M-S2-3-03.
- Repository: `D:\Repo\Virtual_scrum_team`.
- Product argument fix and first direct test commit: `eb649d7a4b83549076b9076389315c3b34e31813`.
- The designated `e2e-runner` attempted the direct selection from exact committed `git show`
  inputs. The attempt produced 4 failures and 8 deselections because the test helper selected the
  wrong shell heredoc by numeric position. All four failures were `StopIteration` while locating
  the expected AST nodes; none entered the existing-runtime validator assertions. This was a test
  harness extraction defect, not a product-runtime failure.
- Run ID: `ffeb19eb284e4f01890ecd5164cd679a`.
- Transfer manifest SHA-256: `7c2a9f36e047099c813b6c53c59d5a35af19ff430ac6e84999d980ffccc8f237`.
- The exact transferred source/test hashes and command are retained in the test agent's run
  message. The attempt did not invoke an installer or mutate runtime/system state; its temporary
  directory was removed.

## Test-harness correction

`tests/vst/test_s2_stage_only_install.py` now finds the runner-runtime Python heredoc by parsing
candidate blocks and requiring both the `inventory_sha` tuple-unpack and `path_exists(runtime)`
existing-runtime branch. It no longer relies on heredoc ordering. The actual fixture assertions
remain: a matching schema-3 marker passes, while changed inventory digest or source HEAD refuses.

## Verification status

- The extraction correction is committed at `043980f64b4cc2ac7c42719251f2fb8258660377` before the
  successful rerun.
- The designated `e2e-runner` executed
  `python -m pytest -q tests/vst/test_s2_stage_only_install.py -k existing_runtime` from exact
  `git show HEAD` inputs in Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4: **4 passed, 8 deselected,
  0 skipped**, exit 0. Input hashes matched before and after execution.
- Run ID `3ec0a90d53d142829ce7e5d05a184602`; manifest SHA-256
  `96f3b9c736ecd63536a811514cb80ad0f43be8199c0dc4eae3b40c4910eea4a1`; archive SHA-256
  `478beda7ad1ecc5123fa7df67f549c70767f289da8dba2f716a56196ea3d9433`. Full input hashes are in
  `docs/sdlc/evidence/s2-3-existing-runtime-regression-043980f.md`.
- No pass is inferred from the earlier test-extractor failure or the separate 54-case overlay run.
- The runtime product fix remains limited to passing/unpacking the existing target-inventory digest;
  no stage, selection, service, Store, key, E5, or production action is authorized.

## Next actions

1. Focused exact-head GPT-PM review `17aa39d9-fb95-4d27-ba94-858fe1cc954d` approved HEAD
   `ef465cd8790518e405164c82ec1598f843ae8a58` and closed M-S2-3-03; exact reply and limits are
   recorded in `docs/sdlc/evidence/s2-3-review-m-s2-3-03-17aa39d9.md`.
2. Keep S2-3 current while Codex creates a fresh exact source plan and source-head-bound WSL
   inventory, obtains exact-bundle review, and completes only the separately authorized stage-only
   and post-stage manifest review. Do not begin S2-4 yet.
