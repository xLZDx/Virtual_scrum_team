# 0148 S4 pin registry provenance to corrected test source

## What changed

- Advanced top-level registry and API category `source_head` to test-source commit `921886d7f26126695adfc26d264e772052f8ac09`.
- Kept the API selector denominator unchanged because the corrected test retains its existing node ID.

## Why

The committed registry's source head must include the exact test source under validation. This creates a clean committed candidate for the one authorized focused module run.

## Affected contracts and paths

- `docs/qa/categories.json`: top-level and API provenance pins.
- `docs/changes/0147-s4-provenance-error-assertion.md`: test source change record.

## Verification state

- Registry update is authored but not yet committed or runtime-verified. The sole focused functional module will run after this commit.
- Previous exact-head NOT_PASS evidence remains preserved in records 0145 and 0146; this update does not change those results.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the registry trust boundary is not separately named in canonical ownership records.
- Commit the provenance update, run the focused module once at the resulting clean HEAD, and preserve the exact outcome.
