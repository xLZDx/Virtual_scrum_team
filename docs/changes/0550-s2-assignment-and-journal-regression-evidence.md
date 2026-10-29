# Change 0550: record S2 assignment and journal regression evidence

## Scope and provenance

The current continuation began at `9c1be0f`. Runtime journal fixes were committed at `5724ba8`;
the read-only Store-backed assignment source and run/generation fix are `c2b1cd2` and `3d5f6c2`.
The primary agent authored no tests and executed no tests. Actual designated functional/E2E
agents authored and executed the focused cases; source fixes were implemented separately.

## Verified focused behavior

- E2E owner: WSL 16 passed at source `c2b1cd2`; Windows 8 passed / 8 expected POSIX skips.
  Tests reproduce the two ordinary partial-write retry failures, then pass after the journal
  fix. Actual harmless Python `-I -S -c` invocation confirms the correct argument mapping;
  the contrary reviewer finding was explicitly retracted and required no source change.
- Functional owner: 21 new assignment-basis cases plus two selected current Store regressions,
  23 passed at `3d5f6c2` in Windows and 23 passed in Ubuntu 24.04 WSL as vst-runner 997:988.
  A valid prior-run handoff originally failed the negative test (DID NOT RAISE); the
  run/generation fence fixes it. Exact POSIX archive/command and source hashes are recorded
  by the same role in the linked evidence.
- Exploratory historical schema-v5 selector failed at its hard-coded version-5 assertion.
  Baseline `9c1be0f` already uses schema 6 and the test blob is unchanged. It is not required
  new-feature coverage, was not weakened, and is explicitly retained as a Codex-owned backlog
  reconciliation item. The final mapped command excludes it and names the two current regressions.

Exact commands, hashes, environments and red/green history:
`docs/sdlc/evidence/s2-bootstrap-e2e-run-20261029.md` and
`docs/sdlc/evidence/s2-assignment-basis-functional-run-20261029.md`.
All cases use disposable/synthetic state; they do not establish live deployment or real upstream
authentication. Restricted process-kill/crash/mutation/E8/policy selectors remain NOT_RUN.

## Environment evidence and remaining gates

The E2E role read compiler/known unit/config path metadata without building/installing or opening
Store data. GCC and PowerShell 7 are present; exact versions and hashes are in
`docs/sdlc/evidence/s2-runtime-inventory-20261029.md`. Store disposition stays UNKNOWN.
The generated unsigned source-plan candidate is a separate review input, not approval; it must
be regenerated for the final staging source HEAD before any deployment action.

Independent code-review recheck resolved both journal MAJORs. Fresh security and database
reviews found no reachable BLOCKER/MAJOR in the bounded read-only assignment source. The future
authenticated bootstrap writer still needs explicit transaction/eligibility/caller provenance
design before implementation authorization. The read API creates no valid upstream record.
Current human E5, production policy/custody, real runtime qualification and exact-head GPT-PM
acceptance remain open. This change authorizes no push, PR, key creation or activation.

Owners: Codex for source/evidence and transaction-contract preparation; GPT-PM for independent
adjudication; operator for exact production-policy authorization and reserved human trust actions.
