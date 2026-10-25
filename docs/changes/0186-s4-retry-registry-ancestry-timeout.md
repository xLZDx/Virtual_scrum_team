# Change 0186: Retry transient registry ancestry timeout once

## What changed

- Routed the read-only `git merge-base --is-ancestor` provenance lookup through the existing bounded timeout retry helper.
- Kept each attempt capped at five seconds and retries capped at one. A second timeout and invocation errors still fail closed as a non-ancestor result.
- No provenance acceptance rule changed; only a transient timeout can now recover on the single retry.

## Why

At candidate HEAD `126b67f3a969a067ac1643bebab2ac669a821eaa`, the mapped run reported that registry loading rejected E2E source head `452c8ea...` as outside history. A direct `git merge-base --is-ancestor` at that same HEAD returned exit code 0. The registry helper used a single five-second attempt and mapped both timeout and actual non-ancestry to `False`. The exact transient cause was not independently reproduced, so this correction addresses the evidenced discrepancy using the existing one-retry policy without claiming its root cause is proven.

## Affected contracts and paths

- `tools/qa/registry.py`: ancestry provenance query now shares the same bounded timeout retry as other read-only registry Git lookups.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: record scope and evidence limitations.
- `governance/DOCUMENT_REGISTRY.md`: regenerated document index.

## Decisions and ownership

- Preserve fail-closed behavior after a second timeout, nonzero ancestry exit, or Git invocation error.
- Accountable task owner: operator under delegated S4 continuation; executor: Codex. No technical service owner for this registry is established in the inspected records.

## Verification state

- Implemented; no tests, checks, builds, CI, migrations, or runtime probes were run in this coding pass.
- Functional-test-reviewer must rerun the seeded out-of-scope regression and committed-registry contract at the resulting exact HEAD, then rerun the corrected mapped denominator.

## Provenance

Implemented by Codex from the exact-head discrepancy recorded in change 0185. The fix is a narrow product-source change; the test agent's fixture corrections are separate.
