# S4 source ACL preflight and functional runtime evidence at `bc32f6f`

## Scope and provenance

- Source fix: `c51105abfef72aceb295633bbdf637666ad843a2` (reject extended ACLs in QA source preflight).
- Test/mapping commit under test: `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`. It contains the `97c2c24` platform-portable test adjustment, the `180e330` resolvable-selector correction, and the test-only ACL error assertion alignment in change 0260.
- Exact-head WSL snapshot run: `2b4c4e0d4bf7432aa6c0bb2dda433123`.
- Transferred bundle: 1,342,542 bytes; SHA-256 `ddeeb1789a562fe50616986502e7b8ec9969bcdd92f4fe7f107b08b132e7949d`.
- WSL source snapshot HEAD: `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`; pre-run and post-run tracked status were clean.
- Runtime: Ubuntu-24.04, `/usr/bin/python3` 3.12.3, pytest 7.4.4; dependency lock SHA-256 `174e70c15c9498fb77ebd2414be8c255d3c38baea025527e6e620b8d1ff21882`.
- Test author/executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator; executor: Codex.

## ACL, worker, signer, and parser selectors

The current functional category contains 33 IDs. Fourteen focused selectors below are mapped in that category; the worker-to-synthetic-signer socket denial selector is additional focused evidence and is not mapped in the current category.

The exact focused command was `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider`, followed by:

1. `tests/qa/test_s4_worker_exec.py::test_s4_worker_trampoline_drops_capabilities_before_manifest_exec`
2. `tests/qa/test_s4_worker_exec.py::test_s4_worker_cannot_traverse_synthetic_signer_socket` (focused extra; not in category mapping)
3. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_access_acl_on_socket`
4. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_default_acl_on_socket_parent`
5. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_access_acl_on_traversed_ancestor`
6. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_nonsticky_world_writable_ancestor`
7. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_allows_runner_owned_entry_under_sticky_tmp`
8. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_fails_closed_when_acl_inspection_is_denied`
9. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_qa_preflight_rejects_named_user_acl_on_tracked_source`
10. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_qa_preflight_rejects_named_group_acl_on_tracked_source`
11. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_qa_preflight_rejects_directory_default_acl`
12. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_qa_preflight_fails_closed_when_acl_inspection_is_denied`
13. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_qa_preflight_accepts_source_without_extended_acls`
14. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_snapshot_and_qa_output_directories_inherit_worker_group`
15. `tests/qa/test_s4_pass_line_parser.py::test_s4_pass_line_parser_accepts_one_quiet_dot_and_rejects_lookalikes`

The process ran in transient systemd unit `vst-s4-acl-preflight-bc32.service` as `vst-runner` UID:GID `997:988`, with `CAP_SETUID` and `CAP_SETGID` as its only ambient and bounding capabilities, `NoNewPrivileges=yes`, private network/devices/tmp, `RestrictAddressFamilies=AF_UNIX`, strict system/home protection, 2 GiB memory, 64 tasks, and a 180-second runtime limit. Result: **15 passed in 0.52 seconds**, systemd result `success`, exit status 0. The completed unit's `InvocationID` was blank; the unit name is the correlation.

### Failure triage and test correction

An earlier focused run at HEAD `180e330f5bf1f4f74c6245eba2ffb099a1bffad6`, snapshot run `15e0b1e3d2a443c4b52dcbe6af43a759`, returned 12 passed and 3 failed. Unit `vst-s4-acl-preflight-180e330.service`, InvocationID `ee47ffe926a64e44bc8e953a633a4e1d`. Each failure was in a signer ACL assertion whose regex expected `extended ACL`; the guard correctly raised `path has an extended POSIX ACL`. This is a **test defect** caused by stale expected wording, not a product failure. Change 0260 updated only those three expectations to the exact ACL rejection phrase. The corrected 15-selector run above passed; no product source changed in that correction.

## Synthetic outer functional CLI

After the focused selectors passed, a synthetic report-bound functional-category run executed `tools.qa.run` in transient unit `vst-s4-cli-functional-bc32.service` on the same exact-head snapshot. Unit result: `success`, exit status 0; post-completion systemd `InvocationID` was blank. The run-specific harness reused the preserved S4 functional harness from snapshot `7a2b9a3d76044959b6556d716a375ccb` and changed its `BASE_HEAD` to `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`. It derived its required selector and command projections from the committed registry; the functional denominator was **33 IDs**. No operator or deployed key was used.

- Harness invocation: `/usr/bin/python3 .vst-qa-runs/functional_cli_harness.py`.
- CLI invocation: `/usr/bin/python3 -m tools.qa.run --cwd <candidate> --category functional --manifest .vst-qa-runs/s4-v2-manifest-a6699b0725734679bd4808b20beba68f.json --registry docs/qa/categories.json --signer-socket <ephemeral-private-tmpfs-socket> --runner-id s4-e2e-synthetic-runner --worker-uid 999 --worker-gid 989 --attempt 1 --epoch 1 --resolved-model test-only-synthetic`.
- Source snapshot/test HEAD: `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`.
- Synthetic CLI run ID: `a6699b0725734679bd4808b20beba68f`.
- Candidate HEAD: `1b4e908ada06259b79b5579ea640dc68cd81cc4c`; tracked diff contains only the run-specific v2 manifest and its linked change record.
- Manifest file: `.vst-qa-runs/s4-v2-manifest-a6699b0725734679bd4808b20beba68f.json`; 52,766 bytes; file SHA-256 `1a9f3159bfb9717de36d4dc0ecaec462c9982012b28108b27e9cb5c07631bde6`; canonical manifest SHA-256 `f397eabfc087ef3e103f1f4165e1d5c100cc2c1527d57fd87aeaca97b5112686`.
- Functional report: **PASS**, 33 expected / 33 executed, zero failed, skipped, xfailed, uncollected, or unexpected IDs.
- TestRun receipt: **PASS**. Receipt ID `S4-SYNTHETIC-REPORT-a6699b0725734679bd4808b20beba68f:functional:1:272944c9722949d49c57a0025726c0a5`; internal QA invocation `272944c9722949d49c57a0025726c0a5`.
- Manifest diff gate: **PASS**, diff SHA-256 `83b81a9c756abeb07ee94be9e0642b2c4d20465d978dd62b0f4578d4062a7b4e`.
- Signer: ephemeral in-process `AuthenticatedSigner` with a run-specific synthetic key private to the transient unit; no production/operator key accessed or persisted.
- Worker probe: UID:GID `999:989`, no supplementary groups, `CapInh=CapPrm=CapEff=CapAmb=0`, `NoNewPrivileges=1`; `setuid(997)` returned `EPERM`, effective UID remained `999`.
- Outer evidence JSON: `.vst-qa-runs/cli-functional-a6699b0725734679bd4808b20beba68f/synthetic-functional-cli-evidence.json`; 80,537 bytes; SHA-256 `9013a3ad964a7b42f282e1afa6fdb20099254074bf960296537b5f60d815f151`.

### Artifact digests

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `functional-events.json` | 6,721 | `b30052571435c9383cec144bf6925349f7a65e2b9eee4952be09f74872d7284f` |
| `functional-report.json` | 16,248 | `b3ffe19a2bcfe7b67178d27d5dc774f0374f1d925068cab5bdbf620ac533cf4d` |
| `functional-stderr-ref.json` | 193 | `c440d98d8fda4131381395760a7e87139f0f3682cd47a5639e2b5e14c7b61991` |
| `functional-stdout-ref.json` | 196 | `4c33aa7dc6b9b6a61c9715e18619b5d87da873e11f0e054addfad7dc1d307809` |
| Captured test stdout referenced by the receipt | 3,505 | `b0077569a7e16829620ded5829eae93df8e0ace89ee8a9e49072b2d9e2f7e7e9` |
| Captured test stderr referenced by the receipt | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Registry | 18,634 | `4f27086369df4136c4b3e170c3ae0dcf670c9c2818384a91191a419e52a65cf0` |
| Seeded failure catalog | 3,549 | `ca1e287b05d9af4bcaa4e8c5b8f042f5e694ab119b115e2b381aadc374829199` |
| Requirements lock | 566 | `174e70c15c9498fb77ebd2414be8c255d3c38baea025527e6e620b8d1ff21882` |

The snapshot and candidate tracked source remained unchanged. Generated harness and CLI outputs are preserved under the snapshot's `.vst-qa-runs/`; the source snapshot and candidate report untracked generated QA artifacts after the run.

## Limits

- The report-bound run exercised only the **functional** category using a synthetic signer.
- E2E category was not attempted because its registry coverage remains `PARTIAL`; trusted signer was `NOT_USED`, aggregate regression `NOT_RUN`, authoritative gate consumption `NOT_RUN`.
- No claim is made for deployed signer, production key, aggregate regression, or complete E2E denominator acceptance.
