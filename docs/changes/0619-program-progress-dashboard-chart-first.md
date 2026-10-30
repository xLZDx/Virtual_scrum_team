# Change 0619 — chart-first program progress dashboard

Date: 2026-10-30
Owner: Codex
Project: `D:\Repo\Virtual_scrum_team`
Source revision for the reported runtime state: `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`

## Acceptance delta

The operator could not see the requested overall and per-sprint progress chart in the same hierarchy as the supplied reference. Inspection found that the existing segmented `.progress` bar used block children in a clipped fixed-height container, so the status segments could stack vertically and be clipped instead of appearing as a horizontal overall bar.

## Change

- Made the overall status bar a horizontal flex container and kept each segment at its declared width.
- Kept the dashboard chart-first: overall program status, S0–S5 sprint bars, the 40 canonical task-ID bars, and the separate S2-1–S2-5 delivery queue; explanatory tables and evidence remain below.
- Did not fabricate 40 extra task IDs to reach 80. The canonical register currently provides 40 task IDs; the six sprint bars and five S2 queue bars are displayed as separate levels and do not inflate the program task denominator.
- Reconciled both language reports with the latest S2-4 runtime outcome: authorization `8ee40d1a` was consumed; 17 checks passed; the root-captured preflight probe refused an unapproved Windows/host mount; VST services, Owner→Runner claim/probe and TestRun remain `NOT_RUN`.
- Added links to the latest attempt outcome while preserving source revision and report provenance.

## Verification

- `python C:/Users/koros/.claude/tools/report_conform.py D:/Repo/Virtual_scrum_team/reports/S2_PROGRAM_PROGRESS_2026-10-30.ru.html D:/Repo/Virtual_scrum_team/reports/S2_PROGRAM_PROGRESS_2026-10-30.html` — both reports refreshed.
- `python C:/Users/koros/.claude/tools/report_conform.py D:/Repo/Virtual_scrum_team/reports --check` — `all reports carry the mandated block`.
- Static structure inspection — RU and EN each contain 40 task bars and 11 sprint/S2 queue bars; the portfolio chart panel precedes explanatory sections; CSS declares horizontal flex layout for the segmented overall bar.

No product tests or runtime actions were run for this report-only change.

## Delivery

Commit and normal push are recorded by Git history and the command output for this change. No unrelated files are part of this change record.
