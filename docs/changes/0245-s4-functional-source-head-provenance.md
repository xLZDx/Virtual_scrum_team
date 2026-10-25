# Change 0245: Pin S4 functional selectors to the ACL/group source head

## What changed

- Updated the functional category's `source_head` in `docs/qa/categories.json` from the earlier capability-fix source to code commit `288e33d81243a7939972461767a748f4a029ffce`, which includes the signer ACL guard and snapshot/output worker-group implementation.
- Regenerated the document registry.

## Why

The five ACL and worker-group selectors added in change 0243 must be associated with the latest source code they are intended to exercise. The functional category already mapped these selectors, but its source provenance still pointed to the earlier `cadd801` code head after changes 0242 and 0244.

## Decisions and ownership

- Keep the category's provenance pinned to the code commit immediately before this documentation-only mapping commit; the following exact-head test run includes both that code and this mapping update.
- Accountable task owner: operator under delegated S4 work. Executor: Codex. Test execution owner: `e2e-runner`.

## Affected contracts and paths

- Functional source provenance and test-ID mapping in `docs/qa/categories.json`.
- Generated document index in `governance/DOCUMENT_REGISTRY.md`.

## Verification state

- Code source HEAD: `288e33d81243a7939972461767a748f4a029ffce`.
- `tools/qa/wsl_snapshot.py` transferred that source head to Ubuntu-24.04 WSL as run `b0e3f075d111418f940bfaa1d9f67b9d`; bundle size was 1,272,104 bytes and SHA-256 was `2687769af251aeb914d92ba2e5815d79a9d882fc17d6e575e906d61407bfee0e`.
- The transfer proves only snapshot creation at source HEAD `288e33d`. No tests were run against that snapshot. The required mapped selector run will use a fresh snapshot at the commit containing this mapping update.
- Report-bound CLI, trusted signer, signed report/receipt, authoritative gate consumption, aggregate regression and full E2E denominator remain open.
