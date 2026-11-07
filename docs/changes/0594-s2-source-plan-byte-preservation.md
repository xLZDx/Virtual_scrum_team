# Change 0594 — Preserve exact source-plan bytes for every runtime revision

Date: 2026-10-30
Owner: Codex

The strict installer compares reviewed source-plan bytes with the committed Git blob. The old
.gitattributes exception covered only ef465cd, so the new a600 plan's trailing CRLF was normalized
in commit4a0fc76: worktree reviewed SHA620e4614 differed from committed SHAbe19be59. No installer
was run with that mismatch. Extend the existing exact-byte exception to source-plan filenames for
all revisions and re-add the unchanged reviewed bytes. The inventory bytes already match Git.
This corrects the recurring cause instead of adding another revision-specific exception.

Files: .gitattributes; the a600 source-plan artifact; core/DECISION_LOG.md; this change record.
The reviewed plan SHA remains620e4614929109e2c7689781943bf50e5cf5ad29703d407cb7ebef019cbff29d.
No source/plan JSON value or runtime state changes. Verify worktree/Git bytes before invoking the
existing strict stage-only wrapper. No tests were required or run for this artifact-byte fix.
