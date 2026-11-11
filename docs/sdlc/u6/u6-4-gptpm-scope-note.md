# U6-4 GPT-PM scope note

Base: 0ac012a (U6-3 approved). Task U6-4: cleanup proposals.

- docs/sdlc/u6/CLEANUP_PROPOSALS.md: read-only inventory of scratch worktrees, unregistered folders, local and remote branches of Virtual_scrum_team and AEVE, the WSL distro and the main checkout. Counts: 12 KEEP, 30 PROPOSE_REMOVE (local branches merged into origin/main, 0 unpushed, not checked out), 98 NEEDS_OPERATOR_DECISION. Documentation only; nothing was deleted, moved, pruned or fetched; no process was killed.
- The 19 VST PROPOSE_REMOVE branches were re-checked by the coordinator (merge-base --is-ancestor origin/main, rev-list --not --remotes: all ancestors, 0 unpushed). The 11 AEVE branches were not re-checked.
- The plan row cites a "CLAUDE.md section 9" that does not exist; the document quotes the real rules (C:/Users/koros/.claude/CLAUDE.md:55-58 and the git-worktree-ops skill) and says so.
- Limits: the process check shows command lines only, not working directories (UNKNOWN for most worktrees); remote-tracking refs are 1h20m (VST) and 6h50m (AEVE) old; merged means ancestry only, squash merges look unmerged; WSL contents UNVERIFIED.
- Every deletion needs explicit operator authorization; this task authorizes none.
- docs/qa/categories.json: registry bookkeeping only.
