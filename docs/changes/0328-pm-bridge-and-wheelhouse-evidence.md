# Change 0328 — Record PM Bridge recovery state and bounded wheelhouse scan

## What changed

- Recorded the current uncertain status of the exact S2 GPT-PM request and distinguished an uncorrelated conversation peek from a formal gate response.
- Recorded the bounded scan result for the exact S4 dependency target and clarified that this path is not a trusted wheelhouse.
- Updated the current state and VST-040 backlog entry with the observed limits and next actions.

## Why

S2 cannot be reported as approved without a correlated GPT-PM response for the exact candidate. The send may have crossed the transport boundary, so creating a duplicate request would risk an ambiguous second review. For S4 AC-17, the named dependency target contains installed files rather than the source wheel archives required by the report-bound runner. Recording the exact bounded result avoids treating that target as a wheelhouse while not claiming that no other authorized wheelhouse exists.

## Evidence and verification

- PM Bridge durable request: `d923dc1a-4a93-45d5-8524-61b6352df401`; send-and-await job `1aacdfa4-3a58-46bf-ac5f-55d7520eba78`; status `uncertain`, `CHATGPT_SEND_UNCONFIRMED`, with null user/reply correlation. Read-only peek job: `a58caf48-93e7-42b5-80d3-e630b35fad66`; it displayed a `NOT APPROVED` recommendation but is uncorrelated and reports that the source diff was not included.
- Evidence detail: `docs/sdlc/evidence/pm-bridge-s2-request-recovery-2026-10-26.md`.
- Read-only recursive scan of `D:\Temp\virtual_scrum_team_qa_f4ef8e7` for `.whl` and `.tar.gz` archives returned no matching paths. No other locations were scanned; no downloads or installs occurred.
- Documentation/state only. No source or test code changed; no tests, checks, builds, or migrations were run.

## Remaining acceptance and owners

- S2 exact-head GPT-PM approval remains pending until PM Bridge can provide a correlated response to the existing request. Codex owns safe recovery of that request; GPT-PM owns the gate decision; operator remains accountable for the sprint.
- S4 AC-17 remains `NOT_VERIFIED`; Codex owns locating an existing authorized wheelhouse. If none exists, the operator owns authorizing any new provisioning or download. Required report-bound execution belongs to the designated test roles after prerequisites are available.
- The 52 policy-excluded S4 selectors remain `NOT_RUN`; this record does not authorize them or close S4.
- No push, PR, merge, or external environment change is authorized by this record.

Change: 0328  
Executor: Codex
