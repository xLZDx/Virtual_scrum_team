# Change 0169: Record bounded BMad Loop v0.13.2 source review

## What changed

- Added a read-only source-level review for official BMad Loop v0.13.2 at immutable commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`.
- Recorded control-plane, command/plugin, repository-mutation, process-cleanup, and platform-compatibility surfaces as suitability concerns or explicit unknowns, without calling them confirmed exploits.
- Updated the S3 plan, VST-028 backlog, bilingual report, decision log, and lesson log.

## Review evidence

- Reviewer: security-reviewer, GPT-6 Luna, medium effort.
- Reviewed official pinned source files: `src/bmad_loop/engine.py`, `workspace.py`, `verify.py`, `plugins/bus.py`, `plugins/registry.py`, `adapters/profile.py`, `childrun.py`, and `process_host.py`.
- Source observations: orchestration includes verification and orchestrator commit; default workspace isolation is `none`, while worktree mode creates unit branches/worktrees and merges back; verify commands and declarative hooks run as child processes; enabled Python plugins are imported in-process after a trust gate and containment check; project-local CLI profile overlays and entry-point adapters are supported; the child runner documents a process-reparenting race; the upstream source says native Windows process-host behavior is not yet exercised.
- The review did not establish an OS-enforced network-egress or credential boundary. Plugin trust helper and loader paths could not be resolved at the requested immutable tag (HTTP 404), so hash/trust persistence and full load flow remain `NOT_VERIFIED`.

## Why and limits

S3 requires candidate identity, source, compatibility, and security review before acquisition. The source observations demonstrate independent orchestration and mutation capabilities relevant to VST's sole-authority contract. They are not by themselves an exploit finding, proof that every configuration violates the boundary, or an approval to use the candidate.

`report_conform.py --check` exited 0 (`all reports carry the mandated block`); `tools/build_document_registry.py --check` exited 0 (`DOCUMENT_REGISTRY.md is current`). No candidate source was cloned, installed, built, executed, or tested. Temporal remains a separate partially audited candidate. The worker boundary, plugin/configuration policy, provider credentials, network behavior, dependency provenance, and WSL runtime containment remain open.

## Ownership and next step

- Accountable task owner: operator for candidate authorization and final selection.
- Executor: Codex for continued read-only audit.
- Technical upstream/service owner: not identified in project records.
- Next: resolve accessible plugin trust/configuration sources and define the VST-owned worker boundary; acquire/run candidates only after the remaining audit and operator authorization.
