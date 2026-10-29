# Change 0577: accept the confirmed PM Bridge reply wrapper safely

## Why

The AF review for GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` was marked `NOT_RUN` because its correlated reply was not recognized. PM Bridge's persisted `result.reply` includes a transport label (`ChatGPT said:`) and blank line before the requested `REQUEST_ID`. Change 0575 covered the inner request-ID header but its test did not include the transport wrapper. A subsequent exact-head review would still fail without this correction.

## Change

- `tools/af_attachment_review.mjs` recognizes only the exact optional `ChatGPT said:\n\n` wrapper, and requires a valid UUIDv4 `REQUEST_ID` immediately after it that matches the persisted request intent. It then permits a top-level verdict immediately or after one blank line. A wrapper without ID, a mismatched/malformed/duplicate ID, arbitrary wrapper/preamble, or missing/repeated/conflicting verdict remains refused.
- `tests/vst/test_af_attachment_review.mjs` updates both `runAdapter` reply fixtures to the exact persisted wrapper format and covers matching acceptance, mismatch refusal without receipt/approval, wrapper without ID and arbitrary `Assistant said` preamble.
- `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md` records the actual PM Bridge reply shape, adapter correction, independent review, test run and limits. S2-1 backlog/test-plan/verification updates are included in the same task change.

## Verification before commit

- Owner: `functional-test-reviewer` (`gpt-6-luna`, medium).
- Command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Result: 38 passed, 0 failed, 0 cancelled, 0 skipped; duration 139463.6885 ms.
- Revision at run: worktree HEAD `74fdbf6aaf79e558d8b62da826879937e48e9c4a`; production and test changes were uncommitted. Exact committed-head rerun remains required.
- Environment: Windows NT 10.0.26300.0; PowerShell; Node v24.13.1; Git 2.53.0.windows.1.
- Test SHA-256: `5FA69F2F34722AD96FEFAF2A2C8A98C9B18D29298F5E726FDDC0BEFBC30FAEA1`.
- Adapter SHA-256: `1933B1775C87E21088C82BC435B36C056A1795E306334716B26724E07DD08631`.
- During the run, the tester discarded an initial result produced by a process with stale in-memory source, confirmed the current source enforcement, started a fresh Node process, and recorded only this final 38/38 result. No production or documentation files were edited by the tester.

## Review

- `code-reviewer` (`gpt-6-luna`, medium) inspected the wrapper delta after identifying that wrapper-without-ID could otherwise accept a verdict. The corrected code now requires an ID whenever the exact wrapper is present; the reviewer confirmed the matching-ID path, mismatch/malformed/duplicate refusal and absence of a new false-approval path. It did not run tests.

## Remaining acceptance

After this task commit, `functional-test-reviewer` reruns the focused suite on the exact committed HEAD. Codex then refreshes local `docs/sdlc/verify-evidence.json` and submits one fresh exact-head GPT-PM review through the corrected adapter. No approval file may be written manually. Push only after the actual correlated approval and required AF verification succeed. S2-2 must not start first. Runtime, production identity, root configuration, current E5 and restricted selectors remain independently unproven or `NOT_RUN`.
