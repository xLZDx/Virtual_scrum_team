# S2-1 AF correlated-reply parser correction — 2026-10-29

## Finding and correction

The AF exact-head review submission for GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` completed, but the local adapter marked the review `NOT_RUN`, `UNRECOGNIZED`, `correlated=false`, and `receipt_written=false`. Its error was `GPT reply must begin with one unquoted top-level VERDICT line`. The actual correlated GPT-PM reply began with `REQUEST_ID: 4fb1b534-e56e-46da-8a0c-1a0366d9597e`, then a blank line, then `VERDICT: MAJOR — source-fidelity remediation accepted; full code approval remains HOLD`.

The adapter previously accepted only a first-line `VERDICT`, so the request-correlated reply format was rejected before its verdict and acknowledgements could be processed. The narrow correction in `tools/af_attachment_review.mjs` accepts a leading UUIDv4 `REQUEST_ID` only when it exactly matches the persisted `intent.requestId`; it permits either an immediate verdict or one blank line before it, then retains the single top-level verdict/parser-consistency check. Mismatched IDs, duplicate IDs, malformed IDs and arbitrary preambles remain rejected. This changes no secret-redaction behavior and does not synthesize an approval.

## Functional regression evidence

- Owner: `functional-test-reviewer` (`gpt-6-luna`, medium).
- Command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Initial parser regression result: 36 passed, 0 failed, 0 cancelled, 0 skipped; duration 148216.028 ms.
- Follow-up added two `runAdapter` end-to-end cases, then reran the same focused command: 38 passed, 0 failed, 0 cancelled, 0 skipped; duration 167146.7255 ms. The matching case proves the leading reply ID equals both persisted `intent.requestId` and outbound request ID and is accepted; the mismatch case preserves otherwise valid job/ack correlation but is refused, emits no success JSON and writes no receipt/approval artifact.
- Source revision: repository HEAD was `206a746fdae942fd6ab6f36c882bb0c3d18ec539`; adapter and test changes were present in the worktree but not yet committed. This is pre-commit regression evidence; rerun after the task commit for exact committed-head evidence.
- Environment: Windows NT 10.0.26300.0, PowerShell, Node v24.13.1, Git 2.53.0.windows.1.
- Final pre-commit test SHA-256: `D772051C88F0831FB7C7110B8DBA289CA9C02558C106B3043DD98B7DDAD2E6F3` (the earlier 36-case file hash was `44B6D89ADA5499B510E052B6AEC8AE3EE6CBB7CF121658762E276A70D2C04F59`).
- Adapter SHA-256: `6DDF6DA1E351BCD4FAD7FBBF362D284F0F9CBEBE301BB96DF90121B3B1425796`.
- The added cases cover matching IDs with and without one blank line, mismatch refusal through `runAdapter`, no receipt/approval on mismatch, repeated headers, malformed UUIDs, and arbitrary preambles.

The test run does not establish GPT-PM approval or production/runtime acceptance.

## Independent review and PM disposition

- `code-reviewer` (`gpt-6-luna`, medium) inspected the adapter parser diff and regression test by source review. It found the change constrained to the persisted request ID and one top-level verdict, with no false-approval path. This is a code-review conclusion, not a test result.
- The same reviewer inventoried the base-to-HEAD range and counted 74 changed `tests/` and `tools/` paths excluding two README files: 30 test/helper files, 38 source/script files, and six systemd unit files. It directly reviewed the attachment adapter, source-fidelity verifier, runtime plan/bootstrap selector, assignment/dispatch/gate modules, `tools/build_document_registry.py`, and all 30 changed test paths. Its follow-up fully read `test_s2_persistent_runner_service.py` (including previously open groups 798-897, 1154-1230, 1577-1816), `test_s2_runner_lifecycle.py` (1201-2652), and `test_s2_store_lifecycle.py`; no additional confirmed BLOCKER/MAJOR was found. Its review was static, not test execution. Security, database and reliability reviewers separately covered their assigned source, installer/helper and six systemd-unit boundaries; those reviews likewise do not prove runtime behavior. No directly unreviewed path remains in the inventoried 74-path range, while exact task verification and GPT-PM adjudication are still pending.
- GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e`, job `785de995-89f3-4c03-a758-46d2361d6109`, reply `e64d9d11-0007-51e1-98be-9cdb31068d01`, reviewed HEAD `206a746fdae942fd6ab6f36c882bb0c3d18ec539`, base `6117ba24b08a260b42402db6da0bf767864e1c04`, input SHA-256 `0e7e8be1ebd52f8f27f7581c4fef999c9ba0efc2f486aa3ef86e6e660a2e5cd9`, 5,842,177 bytes. GPT-PM closed S2-REVIEW-01 at source-fidelity/static-review level and left S2-REVIEW-02 `MAJOR/OPEN`, exact-head code approval `HOLD`, and S2 Phase 8 `NOT APPROVED`, because its own independent full-range code review was incomplete. The adapter rejected that correlated response, so AF wrote no review receipt or approval. The specialist sweep above is new evidence for a fresh exact-head adjudication; it is not itself GPT-PM approval.

| Reviewer role / model / effort | Reviewed boundary | Result and limit |
|---|---|---|
| `security-reviewer` / `gpt-6-luna` / medium | Supervisor/Runner IPC and identity, grant/signature and dispatch authorization, root issuer, machine authorization, worker-helper and installer boundary; six systemd units; all 41 mapped masked source positions | No confirmed reachable BLOCKER/MAJOR in reviewed scope. Static review only; no production key, runtime identity or E5 proof. |
| `database-reviewer` / `gpt-6-luna` / medium | Store transactions/constraints, dispatch and recovery persistence, assignment/claim/receipt paths and migrations | No confirmed database/concurrency BLOCKER/MAJOR in reviewed scope. No migration or live-Store execution. |
| `reliability-reviewer` / `gpt-6-luna` / medium | Runner timeouts/output bounds/process-tree cleanup, persistent startup recovery, dispatch ambiguity and six service units; supplemental test groups in `test_s2_runner_lifecycle.py:1201-2652` and `test_s2_persistent_runner_service.py:798-897, 1154-1230, 1577-1816` | No confirmed reliability BLOCKER/MAJOR in reviewed scope. Tests were not run by this reviewer; platform-bound selectors remain NOT_RUN. |
| `code-reviewer` / `gpt-6-luna` / medium | 74 changed test/source/unit paths: direct static review across all changed tests, adapter/registry/source-plan/bootstrap/assignment/dispatch/gate paths, and delegated specialist-owned boundaries; full reads of `test_s2_store_lifecycle.py`, `test_s2_runner_lifecycle.py` and `test_s2_persistent_runner_service.py` ranges noted above | No additional confirmed BLOCKER/MAJOR beyond the AF reply parser integration defect, which is now fixed and functionally exercised. Static source review only; no test execution. |

## Acceptance boundary and next action

S2-1 remains the current task. The independent changed-code review coverage is recorded with its static-review limits. Commit the parser correction, tests and linked evidence record together as a task commit; then have `functional-test-reviewer` rerun the focused command on that exact commit. Refresh the local AF evidence packet to that HEAD and resubmit one exact-head GPT-PM review through the fixed adapter. Do not write approval files manually. Normal push and S2-2 remain pending until all S2-1 acceptance criteria are met. Historical runtime, systemd/kernel identity, production configuration, current E5 and restricted selectors remain outside what this evidence proves.
