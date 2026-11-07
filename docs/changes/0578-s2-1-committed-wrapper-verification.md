# Change 0578: record committed S2-1 PM Bridge wrapper verification

## Why

Change 0577 fixed the AF attachment adapter's handling of the actual PM Bridge reply envelope. Its initial recorded test run was pre-commit, so S2-1 still needed exact committed-head evidence and reconciled task records before the fresh PM decision.

## Change

- Recorded the exact committed-head functional test result in `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`, `docs/sdlc/test-plan.md`, `docs/sdlc/verify-evidence.md`, and `docs/sdlc/backlog.md`.
- Updated change record 0577 to point to the committed-head proof and preserve the remaining acceptance boundary.
- Recorded fresh code and specialist review scope, the historical GPT-PM `MAJOR/HOLD`, and the fact that the new evidence is not an approval.
- Kept runtime identity, production configuration, E5, restricted selectors, and all previously `NOT_RUN` work explicitly outside the claims supported by this source/test fix.

## Verification evidence

- Code/test head: `0da595e6574856ed0c85a181941e822031b80787`.
- Actual test owner: `functional-test-reviewer` (`gpt-6-luna`, medium).
- Command: `node --test tests/vst/test_af_attachment_review.mjs`.
- Result: 38 passed, 0 failed, 0 cancelled, 0 skipped; duration 149843.3314 ms.
- The tester verified the test and adapter Git blobs matched `HEAD` before and after the run; no tracked files changed during execution. Test SHA-256: `5FA69F2F34722AD96FEFAF2A2C8A98C9B18D29298F5E726FDDC0BEFBC30FAEA1`; adapter SHA-256: `1933B1775C87E21088C82BC435B36C056A1795E306334716B26724E07DD08631`.
- The exact wrapper requires a matching UUIDv4 request ID after `ChatGPT said:`. A wrapper without the ID and mismatched, malformed, repeated, or arbitrary preamble forms remain rejected; the negative path does not write a receipt or approval.
- Independent static code-review follow-up found no additional confirmed BLOCKER/MAJOR after the wrapper correction. This is review evidence, not execution evidence.
- No new test was run for this documentation-only reconciliation. `git diff --check` is run before this documentation commit; the AF packet remains local and untracked.

## Remaining acceptance

Codex must refresh the local AF evidence packet and request a new GPT-PM review bound to the exact current code review attachment. GPT-PM's earlier request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` reviewed `206a746fdae942fd6ab6f36c882bb0c3d18ec539`, resolved S2-REVIEW-01, and left S2-REVIEW-02 open with exact-source approval on HOLD; it is not approval for the current head. Do not hand-write an approval. Push S2-1 only after the actual correlated exact-head approval and any repository-enforced verification succeeds. Do not start S2-2 first.
