# Change 0406: reconcile G03/G07 design acceptance and terminal cancellation outcomes

## What changed

- Recorded GPT-PM's correlated `ACCEPT` of the exact change 0405 G03/G07 design at HEAD `77b319367b575b9f4c0a193e91405df507c886e6`: zero BLOCKER/MAJOR, one non-blocking MINOR, one INFO.
- Preserved the acceptance boundary: G03/G07 is accepted at design level only; the cancellation method is a one-method design exception, not implementation or activation authorization; exact server/SDK behavior remains `NOT_VERIFIED` / `NOT_RUN`.
- Closed GPT-PM's non-blocking G07-0405-N01 wording note by specifying three terminal ambiguous-outcome dispositions: proven success (consume, no second forward), proven non-success (only bounded identical retry), and insufficient/conflicting evidence (terminal non-approving/blocked with no automatic retry). GPT-PM said this wording clarification does not require reopening architecture unless semantics change.
- Added a durable correlated adjudication record and reconciled the S3 plan, SDLC state, backlog, decision/lesson logs, and bilingual reports.
- Corrected the SDK-Core cancellation source link to the implementation lines that construct and invoke `RespondActivityTaskCanceledRequest` (`client.rs#L784-L808`).
- Added a read-only Windows/WSL state recheck to the S2 evidence record: firewall inbound Block/outbound Allow, WSL default version 2, `docker-desktop` running, `Ubuntu-24.04` stopped. No distro start, network probe, test or system configuration change occurred; S2 acceptance is unchanged.

## Why

GPT-PM accepted the narrow design amendment but left a non-blocking request to make the terminal handling of ambiguous upstream outcomes explicit. Recording the decision and wording avoids treating a retry as safe when the gateway cannot determine whether Temporal accepted the first request. The S2 host recheck records current permitted system observations without overstating egress or process-containment evidence.

## Affected paths

- `docs/sdlc/evidence/s3-g03-g07-adjudication-0405-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`
- `docs/sdlc/evidence/s3-g03-profile-compatibility-design-20261027.md`
- `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated from staged index)
- `docs/changes/0406-s3-g03-pm-adjudication-followup.md`

## Provenance and review

- Starting HEAD: `77b319367b575b9f4c0a193e91405df507c886e6`, branch `s4-canonical-continuation`. The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.
- GPT-PM request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245`; PM Bridge job `cc0802b8-7662-47b8-95ba-88613d58be83`; user turn `8de9ea84-35b0-45fe-8eb0-87cc0bb182c0`; correlated reply `14aedf85-c52b-5d64-b84b-40baf9a99455`; durable metadata reports `succeeded`, `correlated=true`. GPT-PM reviewed the supplied docs and exact declared HEAD but did not independently inspect the Windows checkout or Git object; Codex ran `git rev-parse HEAD` immediately before sending.
- The review accepted change 0405 at design level with 0 BLOCKER/MAJOR, 1 non-blocking MINOR and 1 INFO. It stated the G07 base method map remains closed except for this separately adjudicated one-method design exception; no gateway/permit implementation or exact-pair runtime behavior is proven.
- Current-turn read-only source inspection of the pinned SDK-Core file confirmed the RPC request construction at lines 784–808; this is static source evidence only.
- The Windows Firewall/WSL recheck ran only `Get-NetFirewallProfile -PolicyStore ActiveStore`, `wsl --status`, and `wsl --list --verbose`; no network, process, candidate, or policy-selector test was run.
- No code, project tests, build, CI, migration, candidate acquisition/install/execution, network probe, push, PR, or merge occurred. All S2 prohibited cases, S4 selectors, S4 `INCONCLUSIVE`, and S5 prerequisites remain unchanged.
- No per-sprint worktree/fork was created; all local work stayed in `D:\Repo\Virtual_scrum_team`.

## Verification and acceptance

- Regenerate `governance/DOCUMENT_REGISTRY.md` from the staged index and run its `--check`.
- Run the mandated HTML report-format check only.
- No GPT-PM architecture reopen is required for the terminal-outcome wording because it does not change the accepted semantics; reopen only if later changes alter the scope/authority contract.
- Do not interpret design acceptance as runtime qualification, candidate acquisition approval, legal disposition, S2/S4/S5 acceptance, or delivery approval.

## Ordered next steps and owners

1. Codex: complete this documentation-only follow-up, regenerate the staged-index registry, and run only the registry/report-format checks.
2. Codex: commit change 0406 locally, preserving the protected untracked S2 file.
3. Codex: continue only permitted S2 system evidence and read-only S3 source audit; preserve prohibited S2/S4 scenarios as `NOT_RUN`.
4. GPT-PM: retain design adjudication for change 0405; future exact final-head delivery approval remains a separate gate.
5. Operator: provide reserved legal/acquisition decisions only when those gates are reached; no action is required for this design-only clarification.
