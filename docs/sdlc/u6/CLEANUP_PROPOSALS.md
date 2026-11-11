# U6-4 Cleanup proposals

Task U6-4 (sprint U6, branch `u6-hardening`). This document is a read-only inventory. Nothing was deleted,
removed, pruned, moved, reset, cleaned, merged or modified while writing it. Every command in the
"Operator commands" section is text only; the operator decides whether to run it.

## 1. Snapshot and its limits

- Snapshot time: 2026-11-11, about 09:04Z to 09:11Z (UTC). Processes and files can change at any time, and other
  Claude or Codex sessions share these folders. Re-run the checks in section 3 immediately before any removal.
- Remote refs were NOT refreshed (`git fetch` is not allowed in this task). "Merged" below means
  `git merge-base --is-ancestor <sha> origin/main` against the existing remote-tracking ref.
  - Virtual_scrum_team (VST): `origin/main` = 7855ef4 (PR 16 merge, 2026-11-11T07:43Z). `.git/FETCH_HEAD` mtime
    2026-11-11 09:46 local (+02:00), which is 07:46Z, about 1h20m before the snapshot. The ref matches `gh pr list` (PR 16 merged 07:43Z).
  - AEVE: `origin/main` = 8a9f6c1 (2026-11-10T22:21Z, PR 16 merge). `.git/FETCH_HEAD` mtime 2026-11-11 04:18 local, which is
    02:18Z, about 6h50m before the snapshot. A newer push to AEVE `main` would not be visible here.
- Process check: only command lines were readable (`Get-CimInstance Win32_Process`). The working directory of a
  process is not exposed by that API, so a session whose shell sits in a folder without naming it on its command line is
  invisible. The process column therefore means "no command line names this folder", not "no process uses it".
- "Ignored" counts are `git status --ignored --short` lines starting with `!!`. "Dirty" counts are `git status --short` lines.

## 2. The "section 9" rule source

PROJECT_PLAN.md line 172 (U6-4) cites "the CLAUDE.md section 9 checks". No file named in the task contains a section 9
for worktree removal:

- `D:/Repo/CLAUDE.md`, `D:/Repo/AGENTS.md`, `D:/Repo/Virtual_scrum_team/CLAUDE.md` and `AGENTS.md`, `D:/Repo/AEVE/CLAUDE.md` and
  `AGENTS.md`: grep for "scratch", "worktree", "section 9" and numbered headings found no removal rule
  (only `AEVE/AGENTS.md:12`, which says to check worktree topology before mutating).
- The VST CLAUDE.md headings are numbered 1 to 3 plus an unnumbered "SDLC workflow" section; there is no section 9.
- The rule text lives elsewhere. The conditions used here are quoted verbatim:
  - `C:/Users/koros/.claude/CLAUDE.md:57-58`: "A scratch worktree lives under `D:\tmp\scratch_worktrees` and is removed after
    its branch is merged, once no process uses it and `git status --ignored` is clean. No permanent worktrees."
  - `C:/Users/koros/.claude/CLAUDE.md:55-56`: "Operator-only: unrecoverable deletion, real money and live trading, force-push,
    `git reset --hard`, `git clean -f`, deleting remote branches, production data."
  - `C:/Users/koros/.claude/skills/git-worktree-ops/SKILL.md:24`: "Remove a worktree only after its branch is merged, after
    checking that no running process uses its folder, that `git status --ignored` is clean, and that it has no junctions pointing outside it."

This is a documentation gap: the plan row points at a section that does not exist under that number. Follow-up for the
operator: either fix the plan wording or add the section.

Conditions used (numbered for the tables):

| Id | Condition | How it was checked |
|---|---|---|
| C1 | Branch is merged | HEAD (or branch tip) is an ancestor of the repository's `origin/main` |
| C2 | No running process uses the folder | No process command line names the folder (cwd unknowable, see section 1) |
| C3 | `git status --ignored` is clean | Zero `??`/` M` entries and zero `!!` entries |
| C4 | No junctions pointing outside | PowerShell reparse-point scan, depth up to 3 below the worktree root, `.git` excluded |
| C5 | Scratch location (global rule "No permanent worktrees") | Folder is under `D:\tmp\scratch_worktrees` |

Rule applied for proposed actions: PROPOSE_REMOVE only if every applicable condition is PASS; deleting a remote branch is
operator-only by `CLAUDE.md:55-56`, so remote branches are never PROPOSE_REMOVE. For local branches (not worktrees) C1
is merged-into-`origin/main`, C2/C3/C4 become "not checked out in any worktree" and "no commit exists only on this branch"
(`git rev-list --count <b> --not --remotes` = 0).

## 3. Worktrees of Virtual_scrum_team and AEVE

C4 = PASS (0 reparse points to depth 3) for every row of this table except the three `D:/Temp` AEVE worktrees, which were not scanned (UNKNOWN).
"Ahead" = `git rev-list --count origin/main..HEAD`.

| # | Path | Repo | Branch @ head | Merged (C1) | Ahead | Dirty / ignored | Command-line users (C2) | C1 / C2 / C3 / C4 / C5 | Proposal |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `D:/tmp/scratch_worktrees/vst-u6` | VST | u6-hardening @ 0ac012a | NO (origin/u6-hardening = same sha, PR not opened or merged) | 18 | 0 / 0 | bash tool shells of this session (pids 51508, 52912, 53056 at snapshot time) | FAIL / FAIL / PASS / PASS / PASS | KEEP until the U6 PR merges |
| 2 | `D:/tmp/scratch_worktrees/Virtual_scrum_team-s5` | VST | s5-bounded-aeve-evidence @ b954c6f | NO (origin has same sha; 29 commits not in main; no PR found) | 29 | 0 / 2 (`tests/vst/__pycache__`, `tools/vst/__pycache__`) | none found | FAIL / PASS / FAIL / PASS / PASS | NEEDS_OPERATOR_DECISION (unmerged work, 2 ignored cache dirs) |
| 3 | `D:/Repo/Virtual_scrum_team` (main checkout) | VST | u3-7-real-run @ c1059bd | NO | 1 (unpushed) | 2 / 23 | none found | FAIL / UNKNOWN / FAIL / PASS / FAIL (not scratch; main checkout) | NEEDS_OPERATOR_DECISION (see section 6) |
| 4 | `D:/Repo/Virtual_scrum_team-s2` | VST | s2-isolated-worker-sandbox @ 43f772d | YES (ancestor of origin/main; PR 1/2 line merged) | 0 | 0 / 3 (`.pytest_cache`, 2x `__pycache__`) | none found | PASS / UNKNOWN / FAIL / PASS / FAIL (permanent, outside scratch dir) | NEEDS_OPERATOR_DECISION (only ignored caches block it) |
| 5 | `D:/Repo/Virtual_scrum_team-s3-current` | VST | s3-current-head-integration @ ba45363 | NO (PR 3 CLOSED, never merged) | 2 | 0 / 3 (caches) | none found | FAIL / UNKNOWN / FAIL / PASS / FAIL | NEEDS_OPERATOR_DECISION |
| 6 | `D:/Repo/Virtual_scrum_team-s4` | VST | s4-native-qa-runner @ 8f95efc | NO | 123 | 6 / 5 (3 modified logs + `tools/qa/registry.py`, 2 untracked docs; real content, 29 insertions / 5 deletions ignoring CR) | none found | FAIL / UNKNOWN / FAIL / PASS / FAIL | NEEDS_OPERATOR_DECISION (uncommitted work present) |
| 7 | `D:/Repo/AEVE` (main checkout) | AEVE | codex/real-repo-hardening-2 @ 25a8fea | YES (ancestor of origin/main) | 0 | 1 / 23 (untracked `reports/behavior-eval/clean-head-6787c8d/`) | none found | PASS / UNKNOWN / FAIL / PASS / FAIL | KEEP (primary AEVE checkout) |
| 8 | `D:/Temp/AEVE-clean-runtime-6787c8db` | AEVE | detached @ 6787c8d | YES | 0 | 1057 / 0 | none found | PASS / UNKNOWN / FAIL / UNKNOWN / FAIL | NEEDS_OPERATOR_DECISION (1057 dirty entries, not scanned for junctions) |
| 9 | `D:/Temp/AEVE-E12-claude-a7f06ee` | AEVE | detached @ a7f06ee | YES | 0 | 957 / 0 | none found | PASS / UNKNOWN / FAIL / UNKNOWN / FAIL | NEEDS_OPERATOR_DECISION (957 dirty entries) |
| 10 | `D:/Temp/aeve-readonly-benchmark-77f6f01` | AEVE | detached @ 77f6f01 | YES | 0 | 905 / 0 | none found | PASS / UNKNOWN / FAIL / UNKNOWN / FAIL | NEEDS_OPERATOR_DECISION (905 dirty entries; name says read-only benchmark) |

Counts for table 3: KEEP 2, NEEDS_OPERATOR_DECISION 8, PROPOSE_REMOVE 0. No worktree of these two repositories meets every condition.
C2 is "FAIL" for row 1 because this session itself is using it. For rows 2 to 10 no command line names the folder, but cwd is invisible, so C2 is
"UNKNOWN" (row 2 shows PASS only in the sense of "no command-line hit"; its proposal does not depend on it because C1 and C3 already fail).

## 4. Other directories under `D:/tmp/scratch_worktrees` (informational)

The directory also holds worktrees of other repositories and loose files. They are not VST or AEVE assets; they are listed because the
task says "every directory". "Base" is each repository's own `origin/HEAD`, with freshness NOT checked (ERP and Fitness_App were not inspected for fetch time).

| Folder | Kind | Repo, branch @ head | Merged into base | Dirty / ignored | Command-line users | Proposal |
|---|---|---|---|---|---|---|
| `w2` | worktree | Fitness_App, detached @ c42b987f | NO | 0 / 0 | `node.exe` pid 51972 (pm-bridge review `--cwd .../w2`), several bash shells (pids 33880, 46196, 53892) | KEEP (in active use) |
| `tf1` | worktree | Fitness_App, fix/stale-voice-tests @ 90fab951 | NO | 0 / 6 | bash shells (pids 35328, 44264, 51556) | KEEP (in active use) |
| `d3d5` | worktree | Fitness_App, feat/d3d05-crossfade @ 1364fa96 | YES | 14 / 6 | none found | NEEDS_OPERATOR_DECISION (dirty, ignored; modified 10:55 local today) |
| `s5wear` | worktree | Fitness_App, feat/s5wear @ 54bac5b2 | NO | 1 / 0 | none found | NEEDS_OPERATOR_DECISION |
| `s00` | worktree | ERP, codex/erp-s00-completion-20261031 @ 533b167c | NO | 10 / 6 | none found | NEEDS_OPERATOR_DECISION |
| `s01-db-20261110` | worktree | ERP, codex/s01-db0101-20261110 @ 2b737d1f | NO | 0 / 1 | none found | NEEDS_OPERATOR_DECISION |
| `s01-db-merge-20261110` | worktree | ERP, codex/s01-db-merge-20261110 @ 26edd828 | NO | 1 / 1 | none found | NEEDS_OPERATOR_DECISION |
| `s01-final-review-20261111` | worktree | ERP, detached @ c678ea2e | NO | 0 / 0 | none found | NEEDS_OPERATOR_DECISION |
| `s01-scope-review-20261111` | worktree | ERP, detached @ 520bd285 | YES | 0 / 0 | none found | NEEDS_OPERATOR_DECISION (C1, C3 pass; modified 09:50 local today, ERP refs freshness and junctions not checked, outside U6-4 scope) |
| `s01-ship-20261111` | worktree | ERP, codex/erp-s01-ship @ d2501f7d | YES | 0 / 0 | none found | NEEDS_OPERATOR_DECISION (same as above) |
| `av3`, `av5` (about 150 MB each) | NOT a registered worktree, no `.git` | looks like a Fitness_App source copy (`mobile`, `functions`, `wear`, `storage.rules`) | unknown | not a repo | none found | NEEDS_OPERATOR_DECISION (cannot be assessed with git; origin unknown) |
| `dep4` (about 700 MB) | NOT a registered worktree, no `.git` | same layout plus `functions-equipment-identity`, `marketing` | unknown | not a repo | none found | NEEDS_OPERATOR_DECISION |
| 17 loose files: `*.log`, `fn.txt`, `s01-perf-candidate-20261107.patch` | files, not folders | n/a | n/a | n/a | none found | NEEDS_OPERATOR_DECISION (logs of past deploys; `.patch` may be the only copy of a candidate) |

Counts for table 4: KEEP 2 (w2, tf1), NEEDS_OPERATOR_DECISION 8 registered worktrees + 3 unregistered folders + 1 row for the 17 loose files, PROPOSE_REMOVE 0.

Note: `vst-u6` and `Virtual_scrum_team-s5` are in table 3. Unregistered-folder rule: git does not know `av3`, `av5`, `dep4`, so no git removal command applies to them; deletion would be plain file deletion, which `CLAUDE.md:55` lists as operator-only when unrecoverable.

## 5. Branches

### 5.1 Virtual_scrum_team local branches (35), base `origin/main` 7855ef4

"Unpushed" = commits reachable from the branch but from no remote-tracking ref. Merged branches have 0 ahead.

PROPOSE_REMOVE (19 local branches): merged (ancestor of `origin/main`), unpushed 0, not checked out in any worktree.
`plan-sync-s5` 344d17c, `plan-u2-merged` fdd6e4b, `plan-u2-merged-fix` d660f93, `s1-control-plane-core` abc0d50,
`s2-canonical-continuation` f9d5039, `s3-worker-pilot` 9f766aa, `s4-a-registry` a3128f9, `s5-a-provenance` 6a9bdb6,
`sprint-a-check-catalog` e67f4b0, `u1-4-for-review` 9587052, `u2-evidence-gate-2` 40a72d2, `u3-7-results` 2e4e9ab,
`u3-testing-core` 621d23c, `u4-coverage-growth` 65e45f1, `u4-plan-end` 8289b80, `u4-role-table-pin` b343395,
`u5-7-real-change` 1cba665, `u5-coding-control` 5166f06, `unified-core-plan` ffcc939.
Caveat: `u4-role-table-pin`, `u5-7-real-change`, `u5-coding-control`, `plan-u2-merged-fix` are from today; a concurrent session could still be about to use them.
`git branch -d` (lowercase d) refuses to delete a branch that is not merged into its upstream or HEAD, so it is the safe form.

KEEP (2): `main` 9587052 (stale: 0 ahead, behind origin/main; should be fast-forwarded, not deleted), `u6-hardening` 0ac012a (current sprint).

NEEDS_OPERATOR_DECISION (14), with unique commits (ahead = commits not in `origin/main`):

| Branch @ sha | Ahead | Unpushed | Checked out | Unique commits (newest first, subjects) / reason |
|---|---|---|---|---|
| `s2-isolated-worker-sandbox` 43f772d | 0 | 0 | `Virtual_scrum_team-s2` | merged; blocked only by the worktree in row 4 |
| `s3-current-head-integration` ba45363 | 2 | 0 | `Virtual_scrum_team-s3-current` | "docs: record VST-027 integration delivery", "feat: integrate S3 worker adapter pilot"; PR 3 CLOSED unmerged |
| `s3-vendor-neutral-worker-pilot` fccf797 | 33 | 0 | no | "docs(s3): reconcile Git hook-path override", "docs(s3): reconcile attribution footer omission", ...; PR 3 CLOSED unmerged (origin copy is ba45363) |
| `s3d-docs` e7e7713 | 3 | 0 | no | "Mark S3-D superseded: single-user machine...", "Record the S3-D GPT-PM code approval as PARTIAL...", "S3-D: Windows-local sandbox proof with checkers..."; S3-D is superseded by operator decision, no PR |
| `s3d-windows-sandbox-proof` 9ddfa0b | 4 | 2 | no | "S3-D: deny only explicit write rights...", "S3-D: add the limited-job worker launcher..." (these two exist only locally; origin has e7e7713) |
| `s4-canonical-continuation` 3b14f20 | 349 | 0 | no | "feat(s2): integrate root issuer journal and delegated grant authority", "docs(s2): map final permitted bootstrap and issuer coverage"; old S2/S4 lineage on remote |
| `s4-e2e-snapshot-20261025-180e330` 9fd992f | 122 | 0 | no | "docs(s4): record source ACL runtime evidence", "test(s4): align signer ACL error assertions"; snapshot branch |
| `s4-native-qa-runner` 8f95efc | 123 | 0 | `Virtual_scrum_team-s4` | "docs: define S4 outer category report-bound contract", ...; worktree has uncommitted work |
| `s4-reproducible-qa-automation` 3b8d80f | 105 | 0 | no | "docs(s4): record exact-head platform matrix evidence", "chore(s4): refresh selector registry..." |
| `s5-bounded-aeve-evidence` b954c6f | 29 | 0 | `Virtual_scrum_team-s5` | "docs(s5): reconcile Git hook-path overrides", "docs(s5): reconcile contract-test commit metadata", ... |
| `u2-evidence-gate` 8e203d7 | 14 | 3 | no | "Record that U2 work stops; S3-D is the current task", "U2-1: add GPT-PM scope note", "U2-1: StaticAnalysis receipt v3...". 3 are local only; origin copy is 6d59767 (11 ahead) |
| `u3-7-a` b1d200e | 5 | 5 | no | "U3-7: regenerate the QA registry for the seeded probe", "U3-7: add the seeded failing probe and register it for executor A", ... all local only; scratch probe branch (U3-7 comparison probe) |
| `u3-7-real-run` c1059bd | 1 | 1 | `Virtual_scrum_team` | "U3: sync plan, reports and logs after the PR 11 merge" (local only) |
| `u3-7-run` 73b224a | 2 | 2 | no | "U3-7: add the seeded failing probe (scratch branch only)", "U3-7: add the comparison probe test and the AEVE profile"; local only |

Several S3/S4/S5 old-lineage branches have large "ahead" counts because main was reached through different histories; ahead does not mean the content
is absent from main. Whether their content is superseded is a judgment for the operator and was not verified here.

### 5.2 Virtual_scrum_team remote-tracking branches (25 besides `main`), base `origin/main`

Deleting a remote branch is operator-only (`CLAUDE.md:55-56`), so no remote branch is PROPOSE_REMOVE. Seen via `gh pr list`: PR 1,2,4,5,6,7,8,9,10,11,12,13,14,15,16 MERGED; PR 3 CLOSED (not merged); no PR was found for `s3d-*`, `s4-canonical-continuation`, `s4-e2e-snapshot-*`, `s4-native-qa-runner`, `s4-reproducible-qa-automation`, `s5-bounded-aeve-evidence`, `u2-evidence-gate`.

- NEEDS_OPERATOR_DECISION, merged into `origin/main` (16): `plan-sync-s5`, `plan-u2-merged`, `s1-control-plane-core`, `s2-canonical-continuation`, `s3-worker-pilot`, `s4-a-registry`, `s5-a-provenance`, `u2-evidence-gate-2`, `u3-7-results`, `u3-testing-core`, `u4-coverage-growth`, `u4-plan-end`, `u4-role-table-pin`, `u5-7-real-change`, `u5-coding-control`, `unified-core-plan`. Each is the head of a MERGED PR (or its ancestor).
- NEEDS_OPERATOR_DECISION, not merged (8): `s3-vendor-neutral-worker-pilot` (ba45363, 2 ahead, PR 3 CLOSED), `s3d-windows-sandbox-proof` (e7e7713, 3 ahead), `s4-canonical-continuation` (349), `s4-e2e-snapshot-20261025-180e330` (122), `s4-native-qa-runner` (123), `s4-reproducible-qa-automation` (105), `s5-bounded-aeve-evidence` (29), `u2-evidence-gate` (6d59767, 11 ahead).
- KEEP (2): `origin/main`, `origin/u6-hardening` (0ac012a, current sprint).

### 5.3 AEVE local branches (45), base `origin/main` 8a9f6c1 (freshness: 6h50m, see section 1)

PROPOSE_REMOVE (11): merged, unpushed 0, not checked out: `backlog/2026-10-21` a3a55d1, `backlog/2026-10-21-final` a3a55d1,
`codex/e04-e09-gate-reconciliation` f1f1047, `codex/post-pr3-merge-status` a7f06ee, `codex/pr1-language-audit` 349979e,
`codex/pr1-main-integration-candidate` 420200e, `codex/real-repo-hardening` 4d62173, `codex/s15-e04-project-test-bundle` 322861b,
`integrate/2026-10-20` a5bfc34, `merged-all-branches-2026-10-20` 097e248, `u4-aeve-executors` 4ae79d0.
Caution: `codex/post-pr3-merge-status` a7f06ee is also the commit of the detached worktree `D:/Temp/AEVE-E12-claude-a7f06ee`; removing the branch does not remove that worktree, and the commit stays reachable from `origin/main`.

KEEP (2): `main` a3a55d1 (behind origin/main, fast-forward candidate), `codex/real-repo-hardening-2` 25a8fea (checked out in `D:/Repo/AEVE`).

NEEDS_OPERATOR_DECISION (32). These are not in `origin/main`. "Unpushed" > 0 means commits that exist nowhere else; deleting loses them.

| Group | Branches (ahead / unpushed) | Reason |
|---|---|---|
| Feature branches, old lineage, all on a remote-reachable commit | `codex/pr2-completion` (453/0), `codex/pr2-s13-report-snapshot-followup` (405/0), `codex/s12-e01-e04-docs` (373/0), `feat/g0-foundation` (1/0, "feat(g0): add verified golden scaffold and governance baseline"), `feat/g2-s02-evaluation` (323/0), `feat/g3-s03-sqlite` (326/0), `feat/g4-s04-behavior` (331/0), `feat/g5-s05-architecture-security` (356/0), `feat/s09-local-readiness` (361/0), `feat/s10-e10-local-inventory` (364/0), `feat/s11-e11-local-explorer` (372/0), `feat/s12-e01-javascript-graph` (388/0), `rescue/rebaseline-proofrecord-v2` (34/0) | Unmerged by ancestry; content may have been merged under other hashes (PRs 2, 3, 13 to 15 exist) but this was not verified |
| Feature branches with local-only commits | `feat/g1-repository-intelligence` (403/2), `feat/g3-s03` (302/1), `feat/s13-e04-docker-sandbox` (402/2) | Unpushed commits would be lost |
| Rescue and consolidation snapshots with local-only commits | `consolidation-2026-10-20` (462/9), `rescue/dangling-001-2026-10-20` (461/8), `rescue/dangling-002-2026-10-20` (115/1, "fix(security): redact multiline mapping secrets"), `rescue/trash-AEVE-runtime-snapshot-head-2026-10-20` (1/1, "test: evaluate AEVE profile behavior"), `snapshot/AEVE-primary-2026-10-20` (403/2), `snapshot/trash-AEVE-2026-10-21`, `-b`, `-v2` (463/10 each) | Backup snapshots of removed folders; their names say "trash" but they are the only copy |
| One-commit snapshots of uncommitted work | `snapshot/AEVE-pr1-integration-2026-10-20` (1/1), `snapshot/AEVE-runtime-snapshot-2026-10-20` (2/2), `snapshot/AEVE-s15-e04-2026-10-20` (1/1), `snapshot/trash-AEVE-pr1-integration-live-2026-10-21` (1/1), `snapshot/trash-AEVE_old-2026-10-21`, `-b`, `-v2` (1/1 each), `wip/e14-review-unfinished-2026-10-20` (1/1, same commit 9373913 as `snapshot/AEVE-pr1-integration-2026-10-20`) | "snapshot: uncommitted work saved on ..." commits; only copies |

Group sizes: 13 + 3 + 8 + 8 = 32.

### 5.4 AEVE remote-tracking branches (8 besides `main`)

All NEEDS_OPERATOR_DECISION (remote deletion is operator-only) except the KEEP rows. `origin/main` 8a9f6c1: KEEP. `origin/codex/real-repo-hardening-2` 25a8fea: KEEP (upstream of the checked-out branch).
Merged: `codex/e04-e09-gate-reconciliation`, `codex/post-pr3-merge-status`, `codex/pr1-main-integration-candidate`, `codex/real-repo-hardening`, `docs/english-only-translation-20261010`, `u4-aeve-executors` (all heads of MERGED AEVE PRs 1 to 16).
Not merged: `origin/feat/g1-repository-intelligence` e468b0a (453 ahead, but AEVE PR 2 with this head is MERGED, so likely a history-rewrite merge; not verified).

## 6. The main checkout `D:/Repo/Virtual_scrum_team` (status only)

- Branch `u3-7-real-run` @ c1059bd, 1 commit ahead of `origin/main` and NOT pushed ("U3: sync plan, reports and logs after the PR 11 merge"). PR 11 and later PRs already merged, so this commit may be redundant, but that is unverified.
- Dirty file: `docs/sdlc/evidence/s2-ro-hardening-audit-20261101-pm08-09.json` (` M`). `git diff --stat` reports 2327 insertions and 2327 deletions, but `git diff --ignore-space-at-eol --stat` and `git diff --ignore-cr-at-eol --numstat` print nothing, so the change is CRLF versus LF only (git warns "CRLF will be replaced by LF").
- Untracked file: `Virtual_scrum_team — project plan.html` (32,260 bytes, 2026-11-10 01:29 local), a generated report; not tracked.
- Ignored: 23 entries (examples: `.pytest_cache/`, `.s2-runtime-a600-only.bundle.tmp`, `.s2-runtime-a600.bundle.tmp`, `PROJECT_PLAN.md.tmp`, `core/DECISION_LOG.md.bak`).
- Proposal: NEEDS_OPERATOR_DECISION. Options for the operator: (a) leave as is; (b) after confirming the commit is redundant, move the checkout to `main` or `u6-hardening` base; (c) restore the EOL-only file and delete the html if it is regenerable. None is done here. This is the primary checkout, not a scratch worktree, so removal does not apply.

## 7. The WSL copy

- `wsl -l -v` (listing only) at the snapshot: `Ubuntu-24.04` State **Stopped**, Version 2, marked default; `docker-desktop` Running, Version 2.
  `docker-desktop` belongs to Docker Desktop and must not be touched.
- `Ubuntu-24.04` backing disk (read-only `ls` of the Windows side): `C:\Users\koros\AppData\Local\wsl\{366d1ca4-c5b5-4eb5-8583-15220fa8a286}\ext4.vhdx`, 5,817,499,648 bytes (about 5.4 GiB), last written 2026-11-09 20:18; the folder was created 2026-10-24 21:27.
- What the project docs say (identification is by documents, not by entering the distro): the VST work used this distro as a POSIX test target, copying
  exact-HEAD archives into transient or private directories, for example `/tmp/vst-s2-e2e-dc959-posix`
  (`docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md:40`), "a WSL copy at 156ead1" (`core/DECISION_LOG.md:1765`),
  `/mnt/d/Repo/Virtual_scrum_team` mounts (`docs/sdlc/evidence/s2-dispatch-outcome-ack-focused-test-run-20261029.md:9`), and a
  "bounded WSL stage-only" runtime bundle (PROJECT_PLAN.md S2-3). PROJECT_PLAN.md S3-D and S4 rows record the operator decision of 2026-11-08 to proceed without WSL; the plan calls the WSL QA harness "retired".
- No note in the memory directory `C:/Users/koros/.claude/projects/D--Repo/memory/*.md` mentions WSL.
- **UNVERIFIED**: the actual contents of the distro (which copies, whether any `~` checkouts or unpushed work or secrets live there, whether any is the only copy of evidence). The distro was not started, entered or listed, as required.
- Section-9 conditions: C1 UNKNOWN (no git state read), C2 PASS for command lines (the distro is Stopped; `wsl.exe` x2, `wslhost.exe` x4, `wslrelay`, `wslservice` processes exist, belonging to Docker Desktop's running distro), C3 UNKNOWN, C4 UNKNOWN.
- Proposal: NEEDS_OPERATOR_DECISION. Unregistering a distro destroys its disk irrecoverably. If the operator decides it is no longer needed, a safe order is: start it in a session they control, list home and `/tmp`, export a backup with `wsl --export` to a drive with room, then unregister.

## 8. Counts per proposed action (this document's rows)

| Class | KEEP | PROPOSE_REMOVE | NEEDS_OPERATOR_DECISION |
|---|---|---|---|
| Worktrees of VST and AEVE (section 3, 10 rows) | 2 (vst-u6, AEVE main checkout) | 0 | 8 |
| Other `scratch_worktrees` worktrees (ERP, Fitness_App; 10 rows) | 2 (w2, tf1) | 0 | 8 |
| Unregistered folders in `scratch_worktrees` (av3, av5, dep4) | 0 | 0 | 3 |
| Loose files in `scratch_worktrees` (17 files, one row) | 0 | 0 | 1 row (17 files) |
| VST local branches (35) | 2 | 19 | 14 |
| VST remote-tracking branches (26 incl. main) | 2 | 0 | 24 |
| AEVE local branches (45) | 2 | 11 | 32 |
| AEVE remote-tracking branches (9 incl. main) | 2 | 0 | 7 |
| WSL distro `Ubuntu-24.04` | 0 | 0 | 1 |
| Main VST checkout (counted in the 10 rows above) | n/a | n/a | n/a |

PROPOSE_REMOVE total: 30 local branches (19 + 11). No worktree, folder, remote branch or WSL distro is PROPOSE_REMOVE.
KEEP total: 12 items. NEEDS_OPERATOR_DECISION: 8 + 8 + 3 + 1 + 14 + 24 + 32 + 7 + 1 = 98 items.

## 9. Operator commands (text only, not executed)

Run only after re-checking section 1 limits. For worktree removal re-run, immediately before:
`git -C <worktree> status --ignored --short`, `git -C <repo> branch --contains <sha>`, and a process listing that names the folder.

Safe removal of merged local VST branches (19), from `D:/Repo/Virtual_scrum_team`; `-d` refuses unmerged branches:

    git branch -d plan-sync-s5 plan-u2-merged plan-u2-merged-fix s1-control-plane-core s2-canonical-continuation s3-worker-pilot s4-a-registry s5-a-provenance sprint-a-check-catalog u1-4-for-review u2-evidence-gate-2 u3-7-results u3-testing-core u4-coverage-growth u4-plan-end u4-role-table-pin u5-7-real-change u5-coding-control unified-core-plan

Note: `git branch -d` checks against the branch upstream or the current HEAD (`u3-7-real-run` in the main checkout, which is not `origin/main`), so it may refuse some branches even though they are merged into `origin/main`. In that case run it from the `vst-u6` worktree or use `git branch --merged origin/main` to confirm first; do not fall back to `-D` without checking.

Safe removal of merged local AEVE branches (11), from `D:/Repo/AEVE`:

    git branch -d backlog/2026-10-21 backlog/2026-10-21-final codex/e04-e09-gate-reconciliation codex/post-pr3-merge-status codex/pr1-language-audit codex/pr1-main-integration-candidate codex/real-repo-hardening codex/s15-e04-project-test-bundle integrate/2026-10-20 merged-all-branches-2026-10-20 u4-aeve-executors

Example commands for NEEDS_OPERATOR_DECISION items, only after the operator decides (each is destructive):

- Worktree (registered, clean, merged), example row 4: `git -C D:/Repo/Virtual_scrum_team worktree remove D:/Repo/Virtual_scrum_team-s2`, preceded by deleting the three ignored cache folders it lists. Do not use `--force`. `git worktree remove` can follow junctions (memory note `windows-junctions`); C4 was PASS for this one.
- Remote branch deletion (operator-only): `git push origin --delete <branch>` for the 16 merged VST branches in 5.2 or the 6 merged AEVE branches in 5.4.
- Local branches that carry unpushed commits: push first (`git push origin <branch>`) or create a bundle (`git bundle create <file> <branch>`), then delete.
- WSL distro (irrecoverable): `wsl --export Ubuntu-24.04 <backup.tar>` first, and only then `wsl --unregister Ubuntu-24.04`.
- Unregistered folders and loose files: no git command applies; plain file deletion by the operator after inspection.

## 10. Doubts and unknowns

- The cited "CLAUDE.md section 9" does not exist; the quoted rules are from the global CLAUDE.md and the git-worktree-ops skill.
- C2 is based on command lines only; working directories of 17 `claude`, 5 `codex` and 50 `node` processes could not be read, so any folder may be in use by a session.
- `origin/*` refs are 1h20m (VST) and 6h50m (AEVE) old; a merge or push since then is not visible.
- Ancestry-based "merged" is conservative: a squash merge would show NOT merged. For VST the PR list shows ordinary merges, so ancestry matches the PR state; for AEVE `origin/feat/g1-repository-intelligence` (PR 2 MERGED, 453 ahead) shows the mismatch exists, so "unmerged" AEVE rows need a content check before any decision.
- Junction scans cover depth 3 only and skip the three `D:/Temp` AEVE worktrees.
- ERP and Fitness_App base refs and fetch freshness were not checked.
- WSL distro contents are UNVERIFIED.
