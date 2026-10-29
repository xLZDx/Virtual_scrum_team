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

- The extraction correction is committed with this record before its next execution.
- The exact committed-source rerun of the direct selection is pending. No pass is inferred from the
  test-extractor failure or from the earlier 54-case overlay run.
- The runtime product fix remains limited to passing/unpacking the existing target-inventory digest;
  no stage, selection, service, Store, key, E5, or production action is authorized.

## Next actions

1. Run `python -m pytest -q tests/vst/test_s2_stage_only_install.py -k existing_runtime` through
   `e2e-runner` against the new committed HEAD and preserve exact input hashes.
2. If the direct cases pass, update the verification and backlog records and send GPT-PM a focused
   exact-head re-review of M-S2-3-03.
3. Keep S2-3 current until the required exact package review and only conditionally authorized
   stage-only evidence are complete; do not begin S2-4.
