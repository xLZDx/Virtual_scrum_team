# Change 0575: accept a correlated PM reply header in the S2-1 adapter

> Follow-up: persisted PM Bridge job output also includes the `ChatGPT said:` transport wrapper before `REQUEST_ID`. Change 0577 adds exact-wrapper handling, mandatory matching-ID enforcement and a regression fixture for that stored reply shape; the 38/38 result below validates the inner-header-only revision, not the wrapper extension.

## Why

The S2-1 exact-head GPT-PM request completed and returned a correlated reply, but the local AF adapter required `VERDICT` on line one. The reply format placed its matching `REQUEST_ID` first, so the adapter rejected the review as `NOT_RUN` / `UNRECOGNIZED`, wrote no receipt, and could not preserve the actual PM disposition. This blocked the ordered S2-1 task; it did not indicate an authorization to self-approve or bypass the exact-head gate.

## Change

- `tools/af_attachment_review.mjs` now accepts one leading UUIDv4 request header only when it exactly matches the persisted review intent, with an optional single blank line before the verdict. It continues to require one unquoted top-level verdict consistent with the PM Bridge parser.
- `tests/vst/test_af_attachment_review.mjs` adds parser and `runAdapter` regression cases for exact match, mismatch, duplicate and malformed headers, arbitrary preambles, and refusal without a receipt/approval artifact.
- `docs/sdlc/test-plan.md` adds TP-37 for request-correlation acceptance. `docs/sdlc/backlog.md` and `docs/sdlc/verify-evidence.md` record the current result and remaining gates. `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md` preserves the exact test, reviewer and PM provenance. Change 0574 links this follow-up to the original source-fidelity work.

## Verification before commit

- Owner: `functional-test-reviewer` (`gpt-6-luna`, medium).
- Command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Result: 38 passed, 0 failed, 0 cancelled, 0 skipped; duration 167146.7255 ms.
- Pre-commit run revision: worktree HEAD `206a746fdae942fd6ab6f36c882bb0c3d18ec539`; adapter and tests were present but uncommitted. The exact committed-head rerun subsequently passed at `6952469312cd4701bbdb93cea4ce4f197516b5d2` (38 passed, 0 failed/cancelled/skipped; 222609.4192 ms); full details are in `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`.
- Environment: Windows NT 10.0.26300.0; PowerShell; Node v24.13.1; Git 2.53.0.windows.1.
- Test SHA-256: `D772051C88F0831FB7C7110B8DBA289CA9C02558C106B3043DD98B7DDAD2E6F3`.
- Adapter SHA-256: `6DDF6DA1E351BCD4FAD7FBBF362D284F0F9CBEBE301BB96DF90121B3B1425796`.
- `git diff --check` emitted only a Git line-ending warning for `docs/sdlc/verify-evidence.md`; it reported no whitespace errors. No other test/check/build was run by the primary agent.

## Review and exact-head disposition

- `code-reviewer` (`gpt-6-luna`, medium) reviewed the parser fix and the 74-path changed `tests/`/`tools/` inventory, including full static reads of the three large lifecycle/store test files after its initial partial review. No additional confirmed BLOCKER/MAJOR was reported. Its review was static, not test execution.
- `security-reviewer`, `database-reviewer`, and `reliability-reviewer` (`gpt-6-luna`, medium) reported no confirmed BLOCKER/MAJOR in their assigned trust-boundary, Store, lifecycle, installer/helper, or systemd scopes. Their static conclusions do not establish deployed runtime behavior.
- GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` at exact HEAD `206a746fdae942fd6ab6f36c882bb0c3d18ec539` resolved S2-REVIEW-01 at source-fidelity/static-review level but kept S2-REVIEW-02 `MAJOR/OPEN` because GPT-PM had not personally completed independent full-range review. The adapter rejection result had `review_status=NOT_RUN`, `verdict=UNRECOGNIZED`, and `receipt_written=false`; no AF approval was created. The subsequent corrected commit must receive a fresh exact-head review; previous approval state cannot be inferred.

## Remaining acceptance

S2-1 remains current. The exact committed-head test rerun at `6952469312cd4701bbdb93cea4ce4f197516b5d2` passed 38/38. Codex now updates the local AF evidence packet and requests a fresh exact-head GPT-PM review through the corrected adapter. Push only after the actual correlated approval and any enforced AF verification succeed; never write approval files manually or bypass hooks. No S2-2 work begins before S2-1 push succeeds. Runtime, production identity, root configuration, current E5, and restricted selectors remain separately unproven or `NOT_RUN`.
