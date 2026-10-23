# Lessons log (append-only)

Entry fields: date and commit title; kind; facts with evidence pointer; root cause; layer that missed or caught it; rule for next time.

## 2026-10-23 -- Unified organization blueprint and review amendments

- Kind: FAILURE (author layer).
- Facts: the first drafts carried a personal name and location in the blueprint header, a private absolute path in `core/STATE.md`, a "DESIGN GO" verdict beside a "NOT ACCEPTED" status, a citation of the wrong file for the Luna model text, and "verified" claims that cannot be replayed from the repository. Evidence: security and consistency reviewer reports; re-checked by grep on 2026-10-23.
- Root cause: the draft was written from conversation context and a local bridge, then summarised as ready without a repository-wide scan for private data or a check of each cited file:line.
- Caught by: reviewers (security-reviewer, code-reviewer); missed by the author and by the author's own handoff summary.
- Rule: before handing over a documentation package, grep it for names, drive-letter paths and topology strings, cite model-policy text only with file:line, and never write a GO verdict into a document whose status is "not accepted".

## 2026-10-23 -- Unified organization blueprint and review amendments

- Kind: SUCCESS.
- Facts: a read-only devil's-advocate round by six role-separated reviewers found six BLOCKER root causes in the proposed contracts (unsigned receipts, no gate verdict function, no fenced state store, failures that can vanish, rule conflicts hidden in the test matrix, unenforced limits) that the author's own conflict list (C-01..C-12) did not contain; one reviewer claim (CRLF as a defect) was disproved by the coordinator against `README.md`.
- Why it worked: independent roles with an explicit "try to falsify" brief, and coordinator re-verification of contested claims against files.
- Rule: keep one adversarial round per design gate and re-verify any reviewer claim that contradicts repository facts before acting on it.

## 2026-10-23 -- Unified organization blueprint and review amendments

- Kind: SHORTCOMING (coordinator).
- Facts: the first status message cited `sdlc-orchestrator/SKILL.md:33` without the `team/skills/` directory; a stop hook flagged the unresolved path. One reviewer agent exhausted its turn limit without a report and had to be resumed.
- Root cause: shortened path in prose; no explicit "report first, then explore" turn budget in that reviewer brief.
- Rule: always give the full path from the repository root; tell reviewers to write the report before their last tool calls.

## 2026-10-23 -- Round 3 record corrections (FAILURE: records overstated operator intent and remote state)

- Kind: FAILURE (author layer: this session).
- Facts: change record 0004 said the operator asked for the fixes and the commit, but that answer was auto-accepted by the question policy; `core/STATE.md` still said nothing had been pushed while `origin/main` was at `d4aefb5`; the Round 1 amendment removed a private path from the tree without noting it was already public in history. Evidence: `docs/changes/0005-round3-records-correction.md`, `git ls-remote origin`.
- Root cause: the author wrote records from the visible question result without checking whether the answer was automatic, and trusted STATE.md without re-verifying the remote.
- Caught by: the Round 3 verification prompt's rules ("an operator decision that has not been made cannot be inferred", "establish source identity") applied by the same session; missed by Round 1 reviewers and the author.
- Rule: before writing that the operator decided something, check the question-policy log; before stating remote or push state, run `git ls-remote`; when removing sensitive text, check history with `git log --all -S`.
