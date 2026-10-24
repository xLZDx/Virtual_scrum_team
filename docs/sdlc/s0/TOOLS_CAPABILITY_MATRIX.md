# S0 tools capability matrix

**Observed on:** 2026-10-24
**Method:** read-only probes only: `git --version`, `gh --version`, the pinned Python at `<python314>` with `--version`, `-m pytest --version` and the stdlib `sqlite3` library version, `wsl.exe --status`, the Docker client `--version`; plus git status/HEAD of local checkouts. No install, no clone, no network, no tool was run beyond a version or status query.

Status meanings:

- **AVAILABLE**: the probe named in the evidence column ran and succeeded. It proves only what the probe covers.
- **NOT_INSTALLED**: a probe ran and found nothing.
- **NOT_VERIFIED**: no probe was run in S0 (not allowed by the S0 command list). This is not evidence of absence.

Licenses come only from existing documents in this repository; otherwise `unknown`. Values are volatile; re-verify before use.

| Tool | Blueprint role / decision | Status | Evidence actually run | Risk | License |
|---|---|---|---|---|---|
| BMad Loop | TOP execution pilot (provisional); early open beta; native Windows backend in progress (blueprint section 6) | NOT_VERIFIED | none; no local checkout looked for beyond the repo list | High: executes code via AI workers; breaking changes before 1.0; needs a sandbox and a pinned commit | unknown |
| OpenHands | PILOT alternative worker, container only | NOT_VERIFIED | none | High: host/manager security boundary needs a threat model; never unrestricted access to the Windows drive | unknown |
| Aider | PILOT worker; blueprint records no verified local checkout | NOT_VERIFIED | none | High: documented prompt-injection path from repository text to a committed change; disable auto-commit | unknown |
| AEVE | KEEP: bounded evidence engine, optional receipt in v1 | AVAILABLE (checkout only) | git: checkout present on branch `codex/real-repo-hardening-2`, HEAD `e26ca48`, 1 dirty file. The engine itself was not run | Medium: partial deterministic coverage (blueprint: 15 of 57 profiles have some executor mapping); `NO_FINDINGS` must not be presented as a full PASS | unknown |
| PM Bridge | KEEP: sprint closure only, after acceptance | AVAILABLE (checkout only) | git: `pm-bridge` on `master`, HEAD `14c7957`, 1 dirty file. Daemon and sessions not probed | Medium: browser/daemon shared state; must not become a second state writer | unknown |
| Personal DC | KEEP: bounded Windows access bridge (v2.2) | AVAILABLE (checkout only) | git: `Personal_DC` on `wip-snapshot-2026-10-20`, HEAD `fe08cbb`, clean. Service health not probed | Medium: transport exposing local paths; alias `AEVE` points at a frozen snapshot (see `PROFILE_RESOLUTION.md`) | unknown |
| pytest | Native runner for unit/functional (blueprint section 8) | AVAILABLE | `<python314> -m pytest --version` returned pytest 8.4.2. No `pytest` executable on the shell PATH; use the module form. No test was run | Low | unknown |
| git | Version control | AVAILABLE | `git --version` returned 2.53.0 (Windows build) | Low: destructive commands are operator-gated | unknown |
| gh | GitHub CLI for PRs | AVAILABLE | `gh --version` returned 2.100.0. Authentication state not checked | Medium: can publish; PR/push only after final approval on the exact head | unknown |
| Python 3.14 (pinned interpreter) | Interpreter for `tools/vst` (stdlib only) | AVAILABLE | `<python314> --version` returned 3.14.3 | Low | unknown |
| docker | Container sandbox candidate | AVAILABLE (client only) | the Docker client `--version` returned 29.5.2. Daemon reachability and running containers not checked | High if used as a worker sandbox: engine socket must never be exposed to a worker; existing containers of other projects must not be touched | unknown |
| WSL | Sandbox candidate for workers (WSL2 distro or VM) | AVAILABLE (WSL2 present; no worker distro verified) | `wsl.exe --status` reported default distribution `docker-desktop`, default version 2. No general-purpose distribution was listed or probed; automount and interop settings not checked | High: Windows drive automount and interop must be disabled for a worker sandbox (blueprint 13.4) | unknown |
| SQLite via Python stdlib | State store (baseline BD-1) | AVAILABLE | `<python314>` `sqlite3` library version 3.50.4. WAL mode and CAS behavior were not exercised in S0 | Low | unknown |

## Read-across

- Everything the S1 control plane needs (Python stdlib, SQLite, pytest, git) is present. The worker tools (BMad Loop, OpenHands, Aider) are NOT_VERIFIED and are not needed before S3 (baseline: real workers come after the sandbox specification).
- A sandbox for workers is not yet demonstrated: WSL2 is present but only the Docker-owned distribution was reported by `--status`, and the Docker daemon state is unknown.
- Local tool licenses are not recorded anywhere in the existing documents; the license audit remains a prerequisite for adopting any upstream (blueprint section 6).
- No CI runner is probed or authorized (ADR-0001).

## Not verified

- Any tool function beyond version/status output.
- Authentication of `gh`, Docker daemon, WSL distributions, network egress policy.
- Whether BMad Loop, OpenHands or Aider exist anywhere on this machine.
