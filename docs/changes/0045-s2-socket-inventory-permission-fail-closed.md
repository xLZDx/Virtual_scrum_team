# 0045 S2 socket inventory permission and symlink fail-closed handling

## What

- Removed `Path.exists()` and `os.path.exists()` from container-socket inventory because those APIs can collapse metadata/permission errors into a false absence.
- Check system socket candidates with `os.lstat`; a missing candidate is absent, while any other metadata error makes inventory incomplete. Present paths, including symlinks, are reported as exposed.
- Enumerate the canonical `/run/user` root without following symlinks. A root or numeric per-user entry that is a symlink or not a directory makes inventory incomplete. Permission failures while opening or enumerating the root, UID directories, or candidate parents also make it incomplete.
- Do not follow a per-user `podman` or `containerd` directory symlink. An absent directory is skipped; an inaccessible or symlinked directory fails closed.

## Why

Review of change 0044 found that `Path.exists()` and `os.path.exists()` can report false on `PermissionError`, allowing an unreadable socket path to look absent. Following an untrusted per-UID symlink could also make the scan claim coverage outside its inventory root. The supervisor relies on the inventory completeness bit, so these cases must make that bit false.

## Affected contracts and paths

- `tools/vst/preflight.py`: container-socket inventory error and symlink handling.
- Attestation format and verification are unchanged. An incomplete socket scan still makes the `no_container_socket` check fail and prevents worker start.

## Verification state

- Implemented on baseline `e50af122283e154b3bdb98446725b4d8674c060c`.
- No tests or checks were run, per task instruction. Test agents should add permission-denied, inaccessible per-UID directory, symlink-root, symlink-UID, and symlink-engine-directory cases.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation-engineer (`gpt-6-luna`).
- Test author/executor: authorized functional/E2E test agents. Technical owner for host runtime provisioning is not established in repository records.
- Next: test agents add the named incomplete-enumeration cases and execute them after code completion; host provisioning evidence remains separate.

Agent-Attribution: implementation-engineer (gpt-6-luna); Codex executor
