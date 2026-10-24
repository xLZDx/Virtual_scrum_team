# Change record 0007: blueprint consistency fixes after ADR-0001

## What changed
Five fixes in the master blueprint, each confirmed against the file before editing:
- Section 7 `GateDecision.verdict` now includes `APPROVED_WITH_WAIVER` and a `waiver_record` field, matching ADR-0001 (the enum previously could not express the waiver).
- Section 4: removed the stale statement that the roster describes `tdd-guide` as a test author.
- Section 13.5 C-1: removed the contradiction "RESOLVED" versus "precedence is undecided".
- CI wording: the blueprint states that no CI is authorized; the 5-CI-runner limit and the CI/CD engineer role are marked inactive.
- Section 12 next step 4 points to ADR-0001.

## Why
An external Round 3 verification of `e4be280` listed four remaining inconsistencies (verdict enum, stale tdd-guide sentence, contradictory C-1 line, CI wording); all four were confirmed by reading the file.

## Affected contracts and paths
Blueprint text only. The installed roster copy, the workspace `AGENTS.md` and the global contract remain unchanged and still disagree with ADR-0001.

## Verification state
Documentation only; checked by grep after the edit; nothing run. The remaining PM Bridge mentions in sections 1, 3, 9 and 11 were not re-audited beyond the phase-10 table fixed earlier. Not independently reviewed. Nothing pushed.
