# 0239 S4 isolated dependency target

**Date:** 2026-10-25  
**Executor:** Codex  
**Branch/head before this fix:** `s4-reproducible-qa-automation` / `c814443`

## What changed

- Added required `--dependency-target` to the S4 QA CLI. It must identify an existing directory outside the candidate repository.
- The runner verifies that the target contains exactly the names and versions from `tools/qa/requirements.lock`, inserts that target for its own metadata resolution, and passes it to pytest through `PYTHONPATH` with `PYTHONNOUSERSITE=1`.
- Reports identify the environment as an isolated external target without recording its machine-specific path.
- Documented the environment preparation/run boundary and updated the decision and lesson logs.

## Why

S4's exact lock must be usable without installing packages into the global `C:\Python314` installation. The prior runner verified packages visible to the interpreter but could not connect an isolated target to the subprocess. This follow-up makes that separation explicit and rejects unexpected or missing target distributions.

## Affected paths

- `tools/qa/run.py`
- `docs/QA_RUNNER_DESIGN.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Verification state

- Static source inspection only. No tests, checks, build, CI, package installation, or runtime command was run.
- No global Python installation was modified.
- The previously existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.

## Acceptance and ownership

- S4 AC-5/AC-6 now have an explicit isolated dependency path in code; runtime evidence remains NOT_RUN until the test phase.
- Accountable task owner: operator under the delegated S2-S5 continuation. Executor: Codex.
- Test authors/executors remain `functional-test-reviewer` and `e2e-runner` after coding is committed.
- Next: commit this bounded runner correction, then delegate the accepted test matrix against that exact code head.
