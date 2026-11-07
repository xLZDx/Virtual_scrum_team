# Change 0211: Triage S2 E4 WSL containment skips

## What changed and why

Recorded an exact inventory of the four E4 skips from the 109-pass WSL subset so the remaining work is correctly classified. They are scenario values within an unconditional skip placeholder, not four independent runnable tests.

## Affected contracts and paths

- S2 E4 platform-containment acceptance.
- `docs/sdlc/evidence/s2-e4-skip-triage-2026-10-25.md`
- `docs/sdlc/STATE.md`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`
- Bilingual S2 checkpoint report and `governance/DOCUMENT_REGISTRY.md`

## Findings and decisions

- Two scenarios require process-group/descendant cleanup and remain prohibited.
- The worker key-file boundary has a real passing WSL identity selector; the synthetic placeholder adds no evidence.
- Windows parent Job Object nesting requires a Windows host and cannot be proven in Ubuntu WSL.
- Test files were unchanged between prior WSL HEAD `ed723a9` and repository HEAD `50647fb`; no test was run during triage.
- E4 remains partial; no production containment claim is made.

## Verification state and ownership

`e2e-runner` (GPT-6 Luna) performed read-only triage. No code or test files changed. The operator remains accountable for delegated S2 work; technical platform owner is `UNKNOWN` in repository records.
