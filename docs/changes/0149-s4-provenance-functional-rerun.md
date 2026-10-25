# 0149 S4 exact-head provenance functional rerun

## What changed

- Recorded the one authorized focused registry-module rerun after provenance fix 0146 and test-only message correction 0147.
- Confirmed the real committed registry loader passes at exact HEAD `56a58a72c337c7c712ce2efb72e99efc179552bd`.
- Preserved earlier NOT_PASS observations in record 0145 and the intermediate stale-expectation failure at `9bb94b3`; no historical result was overwritten.
- Updated S4 backlog and lesson/decision logs, and regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The earlier two runs demonstrated that a separate Git existence probe could reject valid provenance objects. The implementation now relies on the bounded ancestry query, and this exact-head run exercises the committed registry through the same public loader path used by S4 validation.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-provenance-rerun-56a58a7.md`: command, environment, exact revisions, result, warning, skip, and acceptance map.
- `core/BACKLOG.md`: updates VST-032–037 focused registry acceptance while retaining WSL and downstream gates as open.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: exact-head result and symlink limitation.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Verification state

- Exact command: `python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/qa/test_s4_registry_contracts.py` with `PYTHONDONTWRITEBYTECODE=1`.
- At clean HEAD `56a58a72c337c7c712ce2efb72e99efc179552bd`: 15 passed, 1 skipped, 0 failed; Python 3.14.3, pytest 8.4.2; 8.97 seconds.
- The one skip is Windows symlink-creation privilege (WinError 1314). A global pytest-asyncio deprecation warning was emitted.
- This does not establish POSIX symlink behavior, source transfer, signer/report/receipt, authoritative gate, or full sandbox acceptance.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The technical owner for the registry trust boundary is not separately named in canonical ownership records.
- Keep symlink runtime and native signed runner/report/gate evidence open for their designated acceptance lanes; no further action is required on the corrected focused assertion.
