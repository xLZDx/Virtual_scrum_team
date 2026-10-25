# Change 0168: Refresh S3 BMad Loop candidate metadata

## What changed

- Updated the current S3 BMad Loop candidate pin from v0.11.0 to official release v0.13.2, tag SHA `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`.
- Re-read the pinned `pyproject.toml`, LICENSE, SECURITY.md, and README; recorded MIT licensing, Python/dependency floors, maintainer-described execution and security scope, and continued uncertainty.
- Confirmed Temporal v1.32.1 remains the official latest pin and recorded its exact tag resolution.
- Updated the S3 plan, VST-028 backlog entry, decision log, and lesson log.

## Why

The previous BMad Loop pin v0.11.0 was no longer the latest official release. Candidate identity and current public metadata must be refreshed before any acquisition decision. New public documentation continues to describe a control-plane overlap with VST: coding-agent sessions, verification commands, worktree/branch handling, and local commits/merges. That overlap makes a source-level audit more important; it is not itself evidence that the code violates VST boundaries.

## Evidence and provenance

- Official release page: <https://github.com/bmad-code-org/bmad-loop/releases/tag/v0.13.2> (published 2026-10-10).
- Read-only command: `git ls-remote https://github.com/bmad-code-org/bmad-loop.git refs/tags/v0.13.2`; result `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`.
- Pinned official metadata: <https://github.com/bmad-code-org/bmad-loop/blob/v0.13.2/pyproject.toml>, <https://github.com/bmad-code-org/bmad-loop/blob/v0.13.2/LICENSE>, <https://github.com/bmad-code-org/bmad-loop/blob/v0.13.2/SECURITY.md>, and <https://github.com/bmad-code-org/bmad-loop/blob/v0.13.2/README.md>.
- Official Temporal release listing identifies v1.32.1 as latest; read-only tag query resolved `af08a5e5f2dd40f545f2afac7780daaa6987001e`.

## Verification limits and ownership

- Public metadata/docs reviewed only; no source clone, install, build, test, or candidate execution.
- BMad implementation details, dependency provenance/reproducibility, exact runtime permissions, prompt-injection boundary, network/offline behavior, and sandbox compatibility remain `NOT_VERIFIED`.
- Accountable task owner: operator. Executor: Codex for continued read-only audit. Operator retains explicit acquisition authorization and final worker choice.
- Next: continue read-only source/package audit; do not acquire until the audit and operator authorization are both recorded.
