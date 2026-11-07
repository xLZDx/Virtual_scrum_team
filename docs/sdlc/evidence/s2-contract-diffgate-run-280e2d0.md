# S2 contract, gate and diff-gate functional test run

## Run identity

- Source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1` (`Authenticate and episode-bind breaker overrides`).
- The test file `tests/vst/test_s2_contract_gate.py` had this turn's new S6.2 cases in the working tree. Other E2E-owned test files were also modified concurrently; their diffs did not alter the imported `_authority_fixture` or `_authority_receipt` helpers used here.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py`
- Result: exit 0; **60 passed, 0 skipped, 1 warning** in 0.64 seconds.
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Warning: pytest-asyncio reported a deprecation warning for `asyncio.get_event_loop_policy`; it did not affect the result.

## Acceptance mapping

| S2 criterion | Coverage in this run | Result |
|---|---|---|
| E1 reviewer registry and trust roots | Valid signed registry mapping, wrong key, stale registry version, digest mismatch, duplicate principal, unknown/author principal, and all pairwise trust-root key collisions | PASS |
| S2.D1 mandatory commands and parser pins | Missing command plus unknown parser ID, mismatched version and digest are rejected; caller-supplied parser catalog is rejected | PASS |
| S2.D2 signed waiver scope | `FAIL`, `MODIFY`, `NO_GO`, and `PASS` are denied; only `NOT_RUN`, `INCONCLUSIVE`, and `BLOCKED` are accepted | PASS |
| E6.1 diff allowlist and blocked classes | Stable normalized result; blocked CI/hook/lockfile/install classes; explicitly scoped blocked path; path traversal/absolute/ambiguous paths; out-of-scope path; rename into blocked hook; symlink change | PASS |
| E6.2 typed, signed diff evidence bound to manifest and head | Evidence carries manifest digest, candidate head and diff digest; gate rejects missing evidence, stale manifest/head, failing verdict, and invalid signature | PASS |
| E6.3 read-only reviewer cannot write to worktree/store | This Windows focused suite does not execute reviewer credentials under a separate POSIX identity; runtime evidence is owned by the E2E sandbox run and remains NOT_RUN here | NOT_RUN in this run |

## Authoring correction

The first run of the newly added S6.2 parameterization produced 59 passes and 1 failed assertion because the test expected the lower-level diff-gate diagnostic for missing evidence, while the gate correctly rejected the receipt during contract validation with `missing field(s): diff_gate`. The assertion was corrected to accept the precise contract rejection for the missing-field case. No product code changed. The final run above is green.

Agent attribution: functional-test-reviewer (`gpt-6-luna`); test additions in this turn by Codex.
