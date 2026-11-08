# U1-2 Remaining Findings (23 items) — 2026-11-08

**Review baseline**: HEAD f1ff359 (58217ff + fixes applied)  
**Scope**: Documented non-blocking findings for future iteration; 3 BLOCKERs + 3 key MAJORs fixed; acceptance complete.

## Remaining 8 MAJOR issues (brief summary)

- M4 (contracts.py) — Unvalidated criteria length limit  
- M5 (router.py) — Uncovered list not deduplicated  
- M6 (adapter.py) — Child env inheritance from parent  
- M7 (router.py) — Finding dedup key doesn't match sort order  
- M8 (contracts.py) — Path validation doesn't reject relative traversal  
- M9 (router.py) — Exit code doesn't reflect FINDINGS status  
- M10 (adapter.py) — Timeout signal handling incomplete  
- M11 (router.py) — Iteration ID truncation silent failure  

## Remaining 15 MINOR issues (brief summary)

Ni-01 through Ni-15: Style, documentation, edge-case error messages.

**Acceptance**: All BLOCKER and primary MAJOR issues (M1-M3) fixed; code functionally complete; remaining findings logged for backlog prioritization.

**Next**: Await functional-test-reviewer and e2e-runner to write and run U1-2 focused tests (534 baseline + new test coverage), then internal agent review consensus, then GPT-PM final gate before push.
