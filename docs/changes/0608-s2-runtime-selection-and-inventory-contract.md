# Change 0608 — Select the staged S2 runtime and align config inventory input

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.11b, ordered prerequisite for configuration application

## Acceptance delta

The 80c2 runtime/helper were staged but the active selector remained on a600. The reviewed
inactive transition had to select the exact candidate without starting services or opening Store.
The new config applier then rejected the actual inventory shape before WSL because it looked for a
duplicate selected-runtime field; the canonical inventory uses `runtime_selector.link_target`.

## Runtime transition

- Source: the exact committed candidate at `docs/sdlc/runtime-config/runtime-transition-manifest.json`.
- Canonical manifest digest: `dc516f6b7053ec48bf96aaa3ddb3042d87d57f8f7199284e27e98f8203cc7935`.
- Command: `wsl.exe --distribution Ubuntu-24.04 --user root --exec /usr/bin/python3.12 -I -B -S -c <root-only manifest staging and bootstrap_runtime.apply wrapper> <base64 exact committed manifest>`.
- Result: `bootstrap_selection=complete`, `services_started_or_reloaded=false`,
  `store_opened_or_changed=false`, exit code 0.
- The wrapper wrote the manifest to a newly generated root-owned 0700 `/run/vst-deploy-80c2…`
  directory and invoked the existing versioned `tools.vst.bootstrap_runtime.apply` with the
  external digest above. It did not start units or touch Store/configuration.

## Inventory and code correction

- Independent post-selection capture:
  `docs/sdlc/evidence/s2-runtime-config-target-inventory-20261030T0328Z.json`, SHA-256
  `7d52ef6cfc839dbcb26f397e0a289334805171ab073547fe20718e9b5f9b0e78`, captured
  `2026-10-30T03:31:20.220992Z`.
- The selector points to exact source `80c2b81`; all nine relevant units report loaded/inactive,
  with no pending jobs. Store target is absent. Of 26 config destinations, 19 match and seven
  known JSON files differ. Private material was inspected only with `lstat`; bytes were not read,
  listed, or hashed.
- Updated the applier to require the actual `runtime_selector.link_target` field and reject an
  old-runtime selector. The previous invocation stopped during local inventory validation, before
  any WSL transfer or mutation.
- Focused functional-test-reviewer command:
  `python -m pytest -q tests/vst/test_s2_runtime_configuration_apply.py`.
- Result: 10 passed, exit code 0, one existing pytest-asyncio deprecation warning. The run used
  working-tree code and tests at base HEAD `158210ef30e22e2ee44fbfe6283a17f0eeefa56b`.

## Boundary and next action

This step selected the runtime but left all services inactive, made no Store changes, and did not
apply the seven differing config files. S2-4.11c owns a new fresh post-selection inventory and the
exact 26-file config installation. Current-run E5 and the permitted owner-to-Runner journey remain
unproven.
