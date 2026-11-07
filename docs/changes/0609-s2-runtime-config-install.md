# Change 0609 — Install the exact S2 runtime configuration

Date: 2026-10-30
Owner: Codex
Backlog task: S2-4.11c, ordered runtime configuration application

## Acceptance delta

After the exact 80c2 runtime was selected, seven of the 26 fixed configuration destinations
differed from the pinned candidate. The configuration must be updated without touching any
unknown path, private key bytes, Store data, or service activation.

## Execution

- Pre-install inventory:
  `docs/sdlc/evidence/s2-runtime-config-target-inventory-20261030T0335Z.json`, SHA-256
  `d68d5679936927172b2b143fb3c80c28278f7034940bbbf93ffdd72aeda8fba3`, captured
  `2026-10-30T03:36:07.658389Z` on WSL boot ID
  `270cd88b-183f-426c-8add-872d9e98bcec`.
- Exact command:
  `python tools/qa/apply_s2_runtime_configuration.py --inventory docs/sdlc/evidence/s2-runtime-config-target-inventory-20261030T0335Z.json --inventory-sha256 d68d5679936927172b2b143fb3c80c28278f7034940bbbf93ffdd72aeda8fba3 --source-commit aa32afd6298233666897b8753efafa84909715ef`.
- Result: exit code 0. Seven existing exact-path files were replaced from the committed candidate;
  19 were already exact. The tool verified every destination hash and ownership/mode, completed
  `systemctl daemon-reload`, and reported all nine relevant units `loaded/inactive`. It did not
  start services or open/change the Store.
- Post-install read-only e2e-runner evidence:
  `docs/sdlc/evidence/s2-runtime-config-post-install-20261030T033734Z.json`, SHA-256
  `734c1f4a2eff63dff82a42512ba336d0ce3ce7a8eeff8f9386303615777d237e`, captured
  `2026-10-30T03:37:34.162703Z`. It confirms 26/26 candidate matches, exact runtime selector
  `80c2b81`, nine loaded/inactive units, no pending jobs, and absent Store target. Private paths
  were inspected by metadata only.
- The earlier `...013734Z.json` derived inventory has incorrect comparison flags from an octal
  mode type mismatch; it is excluded from acceptance and this commit.

## Verification and limits

- Code review found no remaining concrete issue in the config applier.
- Designated functional-test-reviewer command:
  `python -m pytest -q tests/vst/test_s2_runtime_configuration_apply.py`.
- Result at source-code preparation: 10 passed, exit code 0, one existing pytest-asyncio
  deprecation warning. These are local payload-contract tests, not the real service journey.
- The runtime config is installed, but no service was started; current-run E5 and one allowed
  owner-to-Runner request remain open. Restricted process-kill, crash/recovery, mutation, E8, and
  policy selectors remain `NOT_RUN`.

## Next action

S2-4.12 owns the one permitted current-run E5 and authenticated owner-to-Runner qualification on
this exact installed candidate. Preserve the run/request identity and record actual measured
systemd, Supervisor, Store, Runner and receipt outcomes. S2-5 remains pending until that evidence
and the exact final review are complete.
