# Change 0468: Record S2 Windows ACL boundary design disposition

## What changed

- Added a design record for the Windows ACL gap in S2.3 and its relationship to the signed v2
  runner and signer.
- Recorded independent read-only architecture and security review findings.
- Kept VST-011 Windows ACL/signer isolation and VST-015 Windows read-only credentials
  `NOT_VERIFIED`; no code or acceptance criteria were silently changed.

## Why

The S2 plan requests Windows ACL protection, but the current signed v2 runner and signer are
POSIX-only. A standalone ACL helper would not be connected to Windows worker identity, process
creation, or signer authentication. The design records the concrete boundary and the decision
needed before a safe implementation can be selected.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-windows-acl-boundary-design-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`
- `core/BACKLOG.md`, `core/STATE.md`
- `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Documentation-only change; no tests, checks, build, CI, or migration were run.
- Two read-only reviewers (architect and security-reviewer, default GPT-6 Luna / medium) found
  that a helper-only Windows ACL patch would not close the actual signed-worker trust boundary.
- PM Bridge request `d9e174a1-fbdf-4ba7-bcd0-ec1902ed38c4` / job
  `11cffada-67dd-442f-9649-6ac6b706086d` remains uncertain with no correlated reply; a separate
  peek exposed uncorrelated text and is not counted as GPT-PM gate approval.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not
  modified or staged.
- S2 remains `NOT APPROVED`; no S3 source work, push, PR, or merge was performed.

## Decision and ownership

- Decision: preserve fail-closed POSIX-only v2 behavior; GPT-PM owns adjudicating whether Windows
  signed-worker support is part of S2 acceptance.
- Codex owns the follow-up request and implementation if the Windows profile is selected.
- The test roles own tests/runtime evidence after any source implementation.

Executor: Codex
