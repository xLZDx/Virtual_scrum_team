# Change 0251: Reject worker-writable signer path ancestors

## What changed

- Added a path-component validator in `tools/vst/sandbox.py` that checks every lexical and resolved parent directory leading to the signer socket.
- Rejects parent directories owned by the worker or writable by its primary group/world unless a sticky bit protects the next runner-owned path entry.
- Preserves safe sticky `/tmp` ancestors when the next path entry is runner-owned.
- Verifies that the lexical and resolved signer socket paths identify the same device/inode before applying the endpoint checks.
- Retains ACL inspection, endpoint mode, ownership and group checks.

## Why

The fresh security re-review at `c2eefda17d1294e81fe11f5b7dc16552e0916ca8` closed the earlier parser MINOR but found a conditional MINOR: all traversed ancestors were ACL-checked, while mode permissions were checked only on the immediate parent and socket. If an intermediate parent were writable by the worker, the worker could potentially replace a lower path component after the runner's one-time check and redirect a later signer connection. No such deployed path was demonstrated; the supported contract accepts a signer socket path from trusted runner configuration, but the validator should fail closed on worker-writable ancestors.

## Decisions and ownership

- Treat a sticky world/group-writable directory as safe only when the next existing path entry is runner-owned; sticky semantics then prevent the worker from replacing that entry.
- Do not broaden runner capabilities or depend on the worker regaining runner identity.
- Accountable task owner: operator under delegated S4 work. Executor: Codex via `implementation-engineer` (GPT-6 Luna, medium effort). Test owner: `e2e-runner`.
- Canonical S4 QA infrastructure owner remains UNKNOWN in repository records.

## Affected contracts and paths

- Signer socket path validation in `tools/vst/sandbox.py`.
- ACL/group path regression selectors and functional source provenance in `tests/qa/test_s4_worker_boundary_contracts.py` and `docs/qa/categories.json` (follow-up test change).

## Verification state

- Base source HEAD: `c2eefda17d1294e81fe11f5b7dc16552e0916ca8`.
- At that head, eight focused selectors and the synthetic report-bound functional CLI passed; full evidence is recorded in `docs/sdlc/evidence/s4-reportbound-functional-c2eefda.md`. Those results predate this ancestor-mode change.
- This source fix has not been tested. Test owner must add mapped cases for rejecting a non-sticky worker-writable ancestor and allowing a normal sticky `/tmp` ancestor, then execute them on a fresh exact-head WSL snapshot.
- The path guard does not establish deployed signer peer-UID enforcement. Trusted signer, authoritative task gate, aggregate regression and full E2E denominator remain open.
