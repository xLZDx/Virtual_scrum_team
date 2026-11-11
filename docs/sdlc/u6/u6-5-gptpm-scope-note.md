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

## Round 2 (delta only)

Round 1 (reply 1d2d4951-b0ac-50f3-ba0f-ec029d3b883d, verdict MAJOR) reported that the manifest line 315 reads `"token_fields": [REDACTED]` and is not valid JSON. The word `token` in the key is masked by the bridge's secret redaction while the diff is sent; it is not in the file. Evidence from the committed blob a0be863: `git show a0be863:docs/sdlc/evidence/u6-5-baseline-manifest.json` parsed by Python `json.load` gives 61 entries in sessions[0].files and token_fields = [input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens]; the file contains no `REDACTED` string (grep count 0). Nothing in the manifest changed in this round; only this note and the logs.
