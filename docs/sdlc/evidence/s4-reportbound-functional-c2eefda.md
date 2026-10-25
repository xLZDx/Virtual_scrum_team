# S4 report-bound functional runtime evidence at `c2eefda`

## Scope and provenance

- Source/test HEAD: `c2eefda17d1294e81fe11f5b7dc16552e0916ca8`.
- Fresh WSL snapshot: `7a2b9a3d76044959b6556d716a375ccb`.
- Snapshot bundle: 1,304,276 bytes; SHA-256 `121368add7ae641e51ce80de4fca9aa5ba19e7c4ebab2caff4ef13ba9b656300`.
- Runtime: `Ubuntu-24.04`, CPython 3.12.3, pytest 7.4.4.
- Test author/executor: `e2e-runner` (GPT-6 Luna, medium effort). The source snapshot was clean before execution.

## Focused boundary and parser selectors

The command was run as `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider` with eight selectors:

1. `tests/qa/test_s4_worker_exec.py::test_s4_worker_trampoline_drops_capabilities_before_manifest_exec`
2. `tests/qa/test_s4_worker_exec.py::test_s4_worker_cannot_traverse_synthetic_signer_socket`
3. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_access_acl_on_socket`
4. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_default_acl_on_socket_parent`
5. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_rejects_access_acl_on_traversed_ancestor`
6. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_signer_guard_fails_closed_when_acl_inspection_is_denied`
7. `tests/qa/test_s4_worker_boundary_contracts.py::test_s4_snapshot_and_qa_output_directories_inherit_worker_group`
8. `tests/qa/test_s4_pass_line_parser.py::test_s4_pass_line_parser_accepts_one_quiet_dot_and_rejects_lookalikes`

Unit: `vst-s4-boundary-parser-c2ee.service`; invocation ID `e4b3f9df04a6476eb856a0de8d033a1a`. Result: **8 passed in 0.77 seconds**, systemd result `success`.

## Synthetic report-bound functional CLI

- Unit: `vst-s4-cli-functional-c2ee.service`; invocation ID `9afefd4da15c4173b6e5c8f10dad28db`.
- Unit command: `/usr/bin/python3 .vst-qa-runs/functional_cli_harness.py`.
- Runner: UID:GID `997:988`; worker: UID:GID `999:989`; worker had no supplementary groups, `CapInh/CapPrm/CapEff/CapAmb=0`, `NoNewPrivileges=1`; `setuid(997)` returned `EPERM` and effective UID stayed `999`.
- The bounded unit retained only `CAP_SETUID`/`CAP_SETGID`, with private network/devices/tmp, strict filesystem protections, 2 GiB memory limit, 64 tasks and 360-second runtime limit. It used no `CAP_CHOWN` and did not change runner group membership.
- The signer was an in-process ephemeral `AuthenticatedSigner` with a synthetic key private to the unit's `PrivateTmp`; no deployed/operator key was used or persisted.
- Run ID: `626c0775d9d6416aa0985d2b40656134`.
- Source snapshot HEAD: `c2eefda17d1294e81fe11f5b7dc16552e0916ca8`.
- Candidate HEAD: `a02d7e6f4e5a55ec36e105c0fe5cb945bc21161a`. Its tracked diff contained only the run-specific manifest and linked change record.
- Manifest: `.vst-qa-runs/s4-v2-manifest-626c0775d9d6416aa0985d2b40656134.json`, 49,837 bytes, SHA-256 `362818227c8687cd7f8e4cf5fae094695e913e6dcdeab35f0488c5df48bb9eea`.
- Diff gate: **PASS**, diff SHA-256 `8fe5557293e05b8cfeffe8c9c47b62a0400ec8bf9ca200f721128a5fd74d1c0a`.
- Functional category: **26 expected / 26 executed**, all events passed, zero failed/skipped/xfail; QA report **PASS**, TestRun receipt **PASS**, diff gate **PASS**.
- Internal QA invocation: `9afefd4da15c4173b6e5c8f10dad28db`; receipt ID `S4-SYNTHETIC-REPORT-626c0775d9d6416aa0985d2b40656134:functional:1:9afefd4da15c4173b6e5c8f10dad28db`.
- Captured test stdout: 2,709 bytes, SHA-256 `3fabfb9d9ccc0b18174c159adce1a6e9d5445e6e33a1e25236d0e2eea763aaf8`; stderr: 0 bytes, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; neither stream was truncated or incomplete.

## Artifact digests

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Full evidence JSON | 65,177 | `a4202fca80631c69e853153af1f2edcef47711714587a5a603348d7652fa22fb` |
| QA report | 13,176 | `b279c49885d33b9a442cdf24f060db8cd7d184aba40d70f3619b849b72a1c1f2` |
| Pytest events | 5,185 | `b4255398311e6bc1ae92f2d438ff36d3975564482ffd0df628cd08fb174dfb83` |
| Stdout reference | 196 | `f25f05ae2358330e9f7ae61db853cd625efd6602f0e45ef9082933a2a14d7029` |
| Stderr reference | 193 | `c440d98d8fda4131381395760a7e87139f0f3682cd47a5639e2b5e14c7b61991` |
| Normalized report | — | `e66064c96b6c45982b4b105c55d111eb7703b52fdd76535c5387e9ae4c64cdc4` |

The report binds category registry SHA-256 `46e04fb2dccc9e6f8ae3006dd862998be500c6a606d5f9cc945b5e9986a916d9`, seeded catalog SHA-256 `ca1e287b05d9af4bcaa4e8c5b8f042f5e694ab119b115e2b381aadc374829199`, and dependency lock SHA-256 `174e70c15c9498fb77ebd2414be8c255d3c38baea025527e6e620b8d1ff21882`.

## Limits and remaining acceptance

- This is runtime evidence for the **functional** category and a synthetic signer only. It does not prove a trusted deployed signer or production signer ACL/peer-UID configuration.
- The run did **not** evaluate the authoritative task gate, run aggregate regression, or close the E2E denominator. The E2E category remains `PARTIAL`.
- A reusable E2E pytest selector that invokes a nested `tools.qa.run` is incompatible with the current identity boundary: mapped tests run as worker UID 999 without capabilities, while the nested CLI requires runner-owned identity, signer access and artifact ownership. Closing this denominator gap requires an accepted runner-owned orchestration contract that preserves the worker boundary, or a compatible alternative approved through project design.
- The report and complete artifact evidence are preserved in the WSL snapshot at `.vst-qa-runs/cli-functional-626c0775d9d6416aa0985d2b40656134/`. The source snapshot had no tracked post-run changes; generated `.vst-qa-runs/` output remained untracked/ignored.
