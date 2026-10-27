# Change 0396: reconcile S3 architecture adjudication and profile

## What changed

- Corrected the candidate comparison terminology: the hand-written worker is a local contract baseline only, not a qualified or active fallback.
- Linked the comparison explicitly to the already existing candidate-independent adapter contract and AC-1–AC-15 scenario denominator.
- Added a proposed Temporal target profile for GPT-PM adjudication; it remains planning-only and does not authorize acquisition or execution.

## Why

GPT-PM accepted the four provisional architectural positions but returned MODIFY for S3 acceptance. Its response was scoped to three attached evidence files and expressly said it could not inspect the repository/complete contract. Local verification found that the S3 plan already defines the adapter contract and common scenario denominator, while the static comparison's “fallback” wording could imply production readiness. The profile proposal closes that terminology gap and makes the currently unresolved target dimensions explicit without claiming runtime evidence.

## Affected paths

- `docs/sdlc/evidence/s3-static-candidate-comparison-20261027.md`
- `docs/sdlc/evidence/s3-temporal-target-profile-proposal-20261027.md`
- `docs/changes/0396-s3-architecture-adjudication-followup.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Local read-only document review confirmed S3 plan sections 3 and 5 define the candidate-independent contract and scenario denominator; section 10 contains a proposed topology explicitly marked NOT APPROVED.
- GPT-PM reply to request `efb3f084-9e88-4e0f-9111-e152d99bc013` returned MODIFY, accepted the four provisional positions, and reported three acceptance gaps. It also disclosed it did not independently inspect the repository.
- No tests, checks, builds, policy selectors, downloads, package installations, or candidate executions were run for this change.
- Existing prohibited scenarios remain `NOT_RUN`; S2 Phase 8 remains NOT APPROVED; S4's 53 policy selectors remain `NOT_RUN`.

## Decision

Do not treat the evidence-scoped GPT-PM response as exact-head approval. Re-adjudicate the profile and M01/M02/M03 classification with the complete S3 plan attached. Continue to withhold any candidate acquisition or execution.
