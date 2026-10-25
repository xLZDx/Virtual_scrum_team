# S4 report-bound functional runtime evidence at `7b0fe23`

## Source snapshot

- Source/test HEAD: `7b0fe2339980b6b5d7278c0aeaaa58cc5fab8b71`.
- Snapshot run: `b5bcb1fc2b42449894785c588e20a65f`.
- Git bundle: 1,313,612 bytes; SHA-256 `a057d158cb1ec24509b01b298b4a50199740930d68b9671c41a8a068c37f2819`.
- Runtime: Ubuntu-24.04, CPython 3.12.3, pytest 7.4.4.
- Executor: `e2e-runner` (GPT-6 Luna, medium effort). Snapshot tracked tree was clean.

## Focused worker, signer-path, and parser regressions

- Unit: `vst-s4-boundary-ancestor-7b0.service`; invocation correlation by unit name because post-exit `InvocationID` was blank.
- Command: `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider` with ten selectors: the worker trampoline and synthetic socket checks; signer ACL checks for socket, parent default ACL, and traversed ancestor; non-sticky world-writable ancestor rejection; sticky `/tmp` runner-owned entry acceptance; ACL inspection failure; snapshot/output worker-group inheritance; and exact parser prefix regression.
- Result: **10 passed in 0.34 seconds**, exit 0.
- Bounded unit: runner UID:GID 997:988, Ambient/Bounding capabilities limited to `CAP_SETUID` and `CAP_SETGID`, `NoNewPrivileges`, private network/devices/tmp, AF_UNIX only, strict filesystem/home protections, 2 GiB memory, 64 tasks and 180-second cap.

## Synthetic functional `tools.qa.run` execution

- Unit: `vst-s4-cli-functional-7b0.service`; post-exit `InvocationID` was blank; the unit name is the systemd correlation.
- Unit command: `/usr/bin/python3 .vst-qa-runs/functional_cli_harness.py`.
- Run ID: `19aef5ed5b7646a0adb04d0e4700d17b`; internal QA invocation: `fb1ba078d2ae4e218d409de8c031106c`.
- Source HEAD: `7b0fe2339980b6b5d7278c0aeaaa58cc5fab8b71`.
- Candidate HEAD: `f0b92ab4d19b6d279785151237281d593b2d893c`; tracked diff contained only the run-specific manifest and its linked change record.
- Manifest: `.vst-qa-runs/s4-v2-manifest-19aef5ed5b7646a0adb04d0e4700d17b.json`, 50,697 bytes; file SHA-256 `303d7060bf729d9aa4b1a3cabbfce8b72c90e95d63f4fd0c1cd413d690292391`; canonical manifest SHA-256 `ff7247712e7fba7613e194e4d9bf1d1385a756c73199e8a75409d4dc23318eba`.
- Functional category: **28 expected / 28 executed**, zero failed, skipped, xfailed, uncollected or unexpected IDs. QA report **PASS**, TestRun receipt **PASS**, diff gate **PASS**; diff SHA-256 `906fe79083ba04327095b5273f0f3211a1bd83296ca6582ac5535575ba0cc8e7`.
- Receipt ID: `S4-SYNTHETIC-REPORT-19aef5ed5b7646a0adb04d0e4700d17b:functional:1:fb1ba078d2ae4e218d409de8c031106c`.
- Worker probe: UID:GID 999:989, no supplementary groups, CapInh/CapPrm/CapEff/CapAmb all zero, NNP=1; `setuid(997)` returned `EPERM`, effective UID remained 999.
- Signer: ephemeral in-process synthetic `AuthenticatedSigner`; no operator or deployed key was used or persisted.
- Captured stdout: 2,942 bytes, SHA-256 `7ea38b8e478867106aaba9ae3fd92b3cc30d5c714de1d02a7dfde5b1469ee1b1`, not truncated. Captured stderr: 0 bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, not truncated.
- QA report: 14,076 bytes, SHA-256 `821046fea9c2990db7c05c0458766ced9bc6e03de01796942bb61b6cea871e83`.
- Pytest events: 5,635 bytes, SHA-256 `77db3d31440c5bd1e7cc4e769829770d40a630e06e115aeeff93a9b2a3a3633a`.
- Stdout reference: 196 bytes, SHA-256 `f5be3d6958660a2d3c8f57e020bb10ffe9e612352e4ef42dc408164e0d360389`.
- Stderr reference: 193 bytes, SHA-256 `c440d98d8fda4131381395760a7e87139f0f3682cd47a5639e2b5e14c7b61991`.
- Full evidence JSON: `.vst-qa-runs/cli-functional-19aef5ed5b7646a0adb04d0e4700d17b/synthetic-functional-cli-evidence.json`, 69,677 bytes, SHA-256 `0dba86c6804aeca773cee006bf504e00100d6f7dacd2f2bcd405f78a500aa24e`.

## Review and limits

- Fresh security review at exact code/test HEAD `e7f857f` found no actionable BLOCKER, MAJOR, or MINOR in the reviewed signer ancestor guard, capability trampoline, or exact PASS parser. Review was static; no tests/checks were run by the reviewer. The subsequent `7b0fe23` change only shortens a test fixture; product source is unchanged.
- An earlier run at `e7f857f` had 9 passes and one fixture setup error (`AF_UNIX path too long`) before the guard. Change 0253 shortened the path; both ancestor cases passed in the current 10/10 run.
- This is functional-category evidence with a synthetic signer. It does not establish trusted deployed signer or peer-UID enforcement, authoritative task-gate evaluation, aggregate regression, or E2E-category completion. E2E remains `PARTIAL`.
- Full artifacts remain under WSL snapshot `/var/lib/vst-s4/qa-snapshots/b5bcb1fc2b42449894785c588e20a65f/repo/.vst-qa-runs/`; no cleanup was performed. Source tracked status remained clean; only generated `.vst-qa-runs/` output remained untracked/ignored.
