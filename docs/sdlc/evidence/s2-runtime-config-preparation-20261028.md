# S2 runtime configuration preparation inventory — 2026-10-28

## Scope

Read-only metadata review of the already selected dedicated `Ubuntu-24.04` WSL2 environment while
preparing a current S2 configuration plan. No configuration, account, key, permission, service,
network policy, migration, or runtime state was changed. No key bytes or private E5 contents were
read. No E5 probe or test was run.

## Commands and observed outputs

The distribution and effective shell identity were confirmed with:

```text
wsl.exe -l -q
wsl.exe -d Ubuntu-24.04 -- id
```

The distribution exists and the command shell reported `uid=0(root) gid=0(root)`.

The WSL configuration was read with `wsl.exe -d Ubuntu-24.04 -- cat /etc/wsl.conf`:

```ini
[boot]
systemd=true
[automount]
enabled=false
[interop]
enabled=false
appendWindowsPath=false
```

Read-only `getent passwd` lookups reported these service accounts:

| Account | UID:GID | Result |
|---|---:|---|
| `vst-runner` | `997:988` | Present |
| `vst-signer` | `995:987` | Present |
| `vst-supervisor` | `994:986` | Present |
| `vst-worker` | `999:989` | Present |
| `vst-reviewer` | `993:985` | Present |
| `vst-dispatcher` | — | Absent |

`systemctl is-active vst-supervisor.service vst-signer.service vst-runner.service
vst-dispatcher.service` reported all four as `inactive`.

Read-only `stat` showed `/etc/vst-runner` and `/run/vst-runner` absent, `/var/lib/vst` and
`/var/lib/vst/keys` as `root:root` mode `0700`, and `/opt/vst-runtime` as a symlink to
`/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`. The target is a directory owned by
`root:root` mode `0755`. The symlink itself reports mode `0777`; Linux access checks use the target
permissions, so no permission change was indicated by this observation. The target revision is
older than the current Pub/Sub source and is not a current runtime installation claim.

## Configuration consequences

- A current Supervisor/Runner/dispatcher configuration is not installed at `/etc/vst-runner`.
- No `vst-dispatcher` account exists. The Supervisor contract needs a separately pinned
  `dispatch_owner` principal, UID/GID, and service cgroup; none may be guessed from the dispatcher
  identity.
- The runner requires an exact installed helper/source manifest and a generation record. The
  symlink target is the older `d5001797...` runtime; it is not the Pub/Sub source revision.
- Earlier in-scope inventory reported six role-separated key files and a private historical E5
  inventory. Their contents were not read, and neither current authorization nor current-head
  provenance was established. A fresh run-bound preflight and operator-root-signed network-policy
  attestation remain absent from the current evidence.
- The full S2 flow therefore remains unprovisioned. This inventory does not authorize key
  generation, schema-v6 application, service activation, real dispatch, or an E5 acceptance claim.

## Next action

GPT-PM owns the pending adjudication of the minimum production owner-caller boundary and exact root
configuration preparation scope (`72e04f7e-aa30-4ee2-b079-1e6ee2e01107`). After that result, Codex
continues only within the accepted configuration/source boundary. No S3 work is started.
