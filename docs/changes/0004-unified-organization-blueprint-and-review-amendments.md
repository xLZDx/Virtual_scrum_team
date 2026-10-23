# Change record 0004: unified organization blueprint, review dossier and devil's-advocate amendments

## What changed
- Added `docs/UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md` (proposed integration architecture, S0-S9 roadmap) and `docs/INDEPENDENT_REVIEW_DECISION_PROVENANCE_2026-10-23.md` (decision history, options, contradictions C-01..C-18, reviewer brief).
- Added `docs/FULL_TEAM_EXPANSION_PLAN_2026-10-23.md` (39-role expansion proposal; content unchanged by this commit, first tracked here).
- `docs/INDEX.md`: three rows for the documents above.
- Review amendments from six read-only reviewer agents (all verdicts MODIFY DESIGN): blueprint section 13 (required pre-S3 items R-1..R-6, roadmap amendments, open operator decisions O-1..O-3); dossier section 11 and contradictions C-13..C-18; "DESIGN GO" verdict withdrawn; model-policy citation corrected (three sources disagree); unreproducible "verified" claims relabelled; "13 gates" and the 5+5 limit marked as undefined/unsourced.
- Privacy hygiene: personal name and location removed from the blueprint header; one private absolute path removed from `core/STATE.md`.
- New `core/LESSONS_LOG.md` and entries in `core/DECISION_LOG.md`; regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why
The operator asked for a full devil's-advocate review of the proposed architecture, run through the relevant specialist agents, and then for the confirmed findings to be fixed and committed locally.

## Affected contracts and paths
Documentation only. No agent, skill, hook or policy file was changed. The proposed receipt and gate contracts in blueprint section 7 remain unimplemented proposals; section 13 lists what must change before they are implemented.

## Verification state
Reviewed by architect, security-reviewer, reliability-reviewer, functional-test-reviewer, code-reviewer (consistency) and silent-failure-hunter, all Sonnet 5.5 at medium effort, read-only. Coordinator re-checked: model-policy sources, SKILL.md phase-7 prohibition, agent and skill counts, VST-007/VST-008 status, line endings, personal name and private path. Not done: final GPT review, operator design acceptance, document-registry check beyond regeneration. No tests were run; documentation only. Nothing was pushed.
