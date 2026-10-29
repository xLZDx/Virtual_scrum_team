# S2-3 exact runtime source plan and target inventory — 2026-10-29

## Scope and provenance

- Repository: `D:\Repo\Virtual_scrum_team`.
- Source revision: `c97836029a5d94ff84dee5cb15d1757efd5525c3` on
  `s2-canonical-continuation`.
- This turn's baseline tracked worktree was clean. Existing unrelated untracked
  `.pm-review/`, `gate-approval.md`, and `verify-evidence.json` were preserved.
- Codex generated the unsigned source-plan candidate and performed a read-only
  inventory of the explicitly selected `Ubuntu-24.04` WSL distribution. No source
  files, service identities, configuration, Store, runtime selector, keys or units
  were changed by these actions.

## Exact source plan

Command:

```powershell
python tools/qa/prepare_wsl_runtime_plan.py --expected-head c97836029a5d94ff84dee5cb15d1757efd5525c3
```

The committed utility verifies that the canonical checkout is at the requested full
HEAD and hashes the fixed runtime source/artifact set. Its output was saved as
[`s2-runtime-source-plan-c97836029a5d94ff84dee5cb15d1757efd5525c3.json`](s2-runtime-source-plan-c97836029a5d94ff84dee5cb15d1757efd5525c3.json).

| Field | Recorded value |
|---|---|
| Plan status | `UNSIGNED_REVIEW_CANDIDATE` |
| Source HEAD | `c97836029a5d94ff84dee5cb15d1757efd5525c3` |
| Runtime source archive SHA-256 | `a347bfdb549c389efbb5c319f4b50e1a8fc0c9f2201037db6c998bfcab635412` |
| Sandbox specification SHA-256 | `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997` |
| Versioned runtime destination | `/opt/vst-runtime-c97836029a5d94ff84dee5cb15d1757efd5525c3` |
| Source-plan file SHA-256 | `4368ee3685a3721e2afce3171ce65ee0f4cdb36c5e5665ada2fc8e18b3c57929` |

The source plan contains committed source and systemd-unit digests; it does not
contain secrets or approve staging, selection, activation, Store initialization or
key creation. The compiler provenance and target inventory fields in the source
plan are deliberately not treated as verified by the generator itself.

## Read-only WSL inventory

The bounded inventory was run as root in the named WSL distribution using Python
3.12.3. It checks only fixed paths, named accounts/groups, and candidate numeric
collisions. For present JSON configuration files it records only metadata and a
SHA-256 digest, never file contents. The inventory was saved as
[`s2-runtime-target-inventory-c97836029a5d94ff84dee5cb15d1757efd5525c3.json`](s2-runtime-target-inventory-c97836029a5d94ff84dee5cb15d1757efd5525c3.json),
SHA-256 `555652fe30a31b0d7d5f756f0b0fca9e99c940d4c4bdeab513e3ee05496fc90a`.

- Observed at `2026-10-29T22:09:59+02:00`; distribution `Ubuntu-24.04`.
- `/usr/bin/cc` resolves through `/etc/alternatives/cc` to
  `/usr/bin/x86_64-linux-gnu-gcc-13`; target is root-owned mode `0755`, SHA-256
  `1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26`, version
  `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.
- `vst-supervisor`, `vst-signer`, `vst-runner`, `vst-worker`, and `vst-reviewer`
  exist with UID/GID pairs `994:986`, `995:987`, `997:988`, `999:989`, and
  `993:985`. `vst-dispatcher`, `vst-dispatch-owner`, and
  `vst-supervisor-client` are absent.
- Candidate numeric IDs UID `980`, UID `981`, and GIDs `982`, `983`, `984` were
  unassigned at observation time. This is not a reservation; repeat collision
  checks immediately before any authorized identity creation.
- Existing `/opt/vst-runtime` is a root-owned symlink to the prior
  `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. The c978 versioned
  runtime and c978 versioned worker helper are absent.
- Existing Supervisor, Signer and Runner units are root-owned regular files mode
  `0644`. The Dispatcher unit, Dispatch-Owner unit and Dispatch-Owner socket are
  absent. The exact existing and proposed unit hashes are in the attached inventory
  and source-plan JSON respectively.
- `/etc/vst-runner` configuration files at the fixed Supervisor, Signer, Runner,
  Dispatcher, Dispatch-Owner, fence, delegation-policy and trust paths are absent.
  Store disposition remains `UNKNOWN`; no Store path or contents were inspected.

## Source-fidelity review evidence

An independent `security-reviewer` inspected the exact committed parser and
authorization/key paths without running tests. The previously redacted review packet's
verifier mapped all 41 of 41 masked diff lines to exact Git blob locations across 15
files with zero mismatches. The reported `parseAcknowledgements()` token at line 191
maps to committed expression `const token = \`${label}:\`;`; at the current source
HEAD the parser is blob `75c61d538d5e00f3ae926c8f2023d34f1e54c852` and contains the
same expression. A literal `[REDACTED]` occurs only in the intentional sanitizer
fixture at `tests/af/test_s2_review_source_fidelity.py:97` in the searched paths.
The reviewer found no confirmed BLOCKER or MAJOR in the named paths. This resolves
source fidelity for those paths; it does not certify every line of the 87,222-line
packet or prove runtime behavior.

## Acceptance and restrictions

- The generated candidate plus exact WSL inventory are prepared for GPT-PM's
  conditional exact-bundle review. Until that review is verified as fresh and
  correlated to this HEAD and these input hashes, no stage-only install is performed.
- No runtime selection, systemd activation, Store inspection/creation/migration,
  configuration installation, local key generation, production issuer key, E5
  attestation, or prohibited process/crash/recovery/mutation/E8/policy selector was
  performed. Restricted selectors remain `NOT_RUN`.
- Existing functional/E2E reports are inherited evidence only; no test was run by
  Codex in this preparation step.
- This preparation does not accept S2-3 or close S2. The next allowed action is to
  verify GPT-PM's fresh exact-plan verdict; if accepted, perform only the reviewed
  inactive stage-only preparation and create/review the post-stage manifest.
