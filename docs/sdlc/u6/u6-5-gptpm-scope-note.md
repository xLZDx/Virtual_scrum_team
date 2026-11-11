PROJECT: virtual_scrum_team
SPRINT: U6
TASK: U6-5 (one task)

# U6-5 GPT-PM scope note

Base: origin/main (PR 18 merged). Head: the commit under review (explicit sha given by the review command).

- Change: manifest + report only, no code change. docs/sdlc/evidence/u6-5-baseline-manifest.json pins the now-closed U1-1 session 557da842 (1 session, 61 files, built by tools/uc/token_baseline.py build-manifest; hashes verified against the original directory and against the copy). docs/sdlc/u6/SAVINGS_REPORT.md gets a "Baseline rebuilt" section and an updated operator-input list.
- The report stays NOT_RUN: no after-side session, no paired-task file, no price table exist; no figure is estimated. The role token numbers quoted come from the tool output, not from computation by hand.
- The transcript copy is kept outside the repository (D:/tmp/u6-5-baseline-transcripts) because the repository is public; only paths, sizes and hashes are committed.
- Logs: core/DECISION_LOG.md and core/LESSONS_LOG.md entries; the merge of origin/main kept both sides of both logs (diff against main shows additions only).
- Prior review: one internal code-reviewer pass over the documentation claims (1 MAJOR wording defect, 2 MINOR, all fixed). Not verified by that reviewer: session ages and the count of sessions without tools/uc calls (author scans).
- Not run: pytest (forbidden by the operator), any test of the tools.
