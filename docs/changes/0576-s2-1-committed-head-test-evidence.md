# Change 0576: record S2-1 committed-head adapter verification

## Why

Change 0575 corrected AF handling of the PM Bridge's matching leading `REQUEST_ID` header. Its initial 38-case result was executed against the pre-commit worktree, so S2-1 needed an exact committed-head rerun before the next GPT-PM adjudication.

## Change

- Recorded the exact committed-head test result in `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`.
- Reconciled S2-1 backlog, test-plan TP-37, verification matrix, and the 0575 change record with that result.
- Refreshed the delivery sequence: local AF evidence must bind HEAD `6952469`; GPT-PM must then review that exact new packet through the corrected adapter; no approval or push is inferred from the passing test.

## Verification evidence

- Test owner: `functional-test-reviewer` (`gpt-6-luna`, medium).
- Exact command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Exact tested HEAD: `6952469312cd4701bbdb93cea4ce4f197516b5d2`.
- Result: 38 passed, 0 failed, 0 cancelled, 0 skipped; duration 222609.4192 ms.
- Environment: Windows NT 10.0.26300.0, PowerShell, Node v24.13.1, Git 2.53.0.windows.1.
- Test SHA-256: `D772051C88F0831FB7C7110B8DBA289CA9C02558C106B3043DD98B7DDAD2E6F3`.
- Adapter SHA-256: `6DDF6DA1E351BCD4FAD7FBBF362D284F0F9CBEBE301BB96DF90121B3B1425796`.
- The test role made no edits during this exact-head rerun. This test does not establish GPT-PM approval, AF receipt creation, runtime activation, production identity, E5, or restricted-scenario acceptance.

## Remaining acceptance

S2-1 remains current. Codex refreshes local `docs/sdlc/verify-evidence.json` with this exact test and reviewer provenance, submits a new immutable exact-head package through `tools/af_attachment_review.mjs`, and records the actual correlated verdict. If GPT-PM approves and AF verifies, Codex normally pushes the task commits. If GPT-PM retains a code finding, S2-1 stays current for focused remediation. S2-2 must not start before the normal push succeeds.
