# Change record 0204: Resolve BMad Loop plugin trust and load flow

## What changed

- Extended the pinned BMad Loop v0.13.2 source audit to the plugin trust, discovery, manifest, policy, bus, registry, and model paths.
- Updated the S3 plan, VST-028 backlog, bilingual S3 report, decision log, lesson log, and generated document registry.
- Superseded change 0169's earlier statement that the trust/loader paths could not be resolved at the pinned source.

## Why

The earlier bounded review could not reach source pages for the plugin trust and loader paths. Retaining that uncertainty after the official immutable tree made those paths discoverable would overstate what remained unknown. The audit must also distinguish a conditional execution surface from a demonstrated exploit or sandbox escape.

## Evidence and limits

- Reviewer: `security-reviewer`, GPT-6 Luna, medium effort. Read-only source audit of official BMad Loop commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`; no clone, install, build, execution, or tests.
- [`plugins/trust.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/trust.py), [`loader.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/loader.py), [`manifest.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/manifest.py), and [`bus.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/bus.py) show project-declared shell hooks invoked as child processes with the BMad process environment and project worktree.
- [`policy.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/policy.py), [`registry.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/registry.py), and [`model.py`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/src/bmad_loop/plugins/model.py) show project-local name-based Python plugin enablement, same-name project plugin precedence, and no plugin content digest/signature field before enabled modules are imported/instantiated.
- Assessment: a repository contributor able to control the project manifest/policy can conditionally run shell-hook or Python-plugin code with the BMad process identity. Impact depends on that identity's permissions, files, environment, credentials, and OS policy. This is project-controlled execution by design and a reason to require OS containment; it is not a proven exploit or sandbox escape.
- This bounded review did not establish runtime containment, egress/credential isolation, or the complete transitive license inventory and artifact provenance. No candidate was acquired or executed.

## Ownership and next step

- Accountable task owner: operator for candidate acquisition authorization and final selection.
- Executor: Codex for bounded source review and project records.
- Technical sandbox/service owner: not identified in inspected S3 records.
- Next: complete accessible dependency/license and artifact-provenance assessment for the actual selected profile; retain acquisition and execution gates until explicit operator authorization and a fresh run-bound S2 probe exist.

## Verification state

Documentation-only change. No tests, checks, build, candidate acquisition, installation, or runtime execution were performed.
