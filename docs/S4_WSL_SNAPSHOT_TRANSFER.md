# S4 Windows-to-WSL source snapshot transfer

## Purpose and trust boundary

`tools/qa/wsl_snapshot.py` transfers one clean, committed Windows branch to the already provisioned, explicitly named `Ubuntu-24.04` WSL distribution. It streams a self-contained Git bundle through `wsl.exe` stdin, so Windows drive automount and Windows/Linux path mounts are not needed. The receiver clones only the named branch into a new run-scoped directory and verifies that the cloned Git HEAD equals the Windows candidate SHA.

This tool transfers source only. It does not provision or reconfigure WSL, install packages, start the QA runner, access a signer socket, run tests, or claim sandbox acceptance. The bundle SHA and byte count are computed independently on the Windows sender and WSL receiver and must match in the returned JSON. A transfer result is not a signed VST receipt.

## Destination layout and permissions

The destination root must already exist inside WSL and be owned by the unprivileged runner account. Its group must be the dedicated QA worker group, and its mode must be `2710`: the runner owner has full directory access, while the worker group can traverse only when given the opaque run ID. The root and source tree must not contain symbolic-link components. The operator or responsible provisioning process must create and inspect this root before transfer; the canonical technical service owner is `UNKNOWN` in current project records.

For each transfer the tool creates:

```text
<snapshot-root>/<random-run-id>/source.bundle
<snapshot-root>/<random-run-id>/repo/
```

The run directory is mode `0710` and inherits the worker group. The bundle is runner-only. The cloned repository and Git metadata are runner-owned, worker-group-readable, and worker-group-nonwritable; the repository root is mode `0750`, directories are mode `0750`, and files are `0640` or `0750` according to executable bits. Symbolic links or unexpected owner/group identity fail the transfer. The QA runner independently rechecks the read-only boundary before launching tests.

## Invocation

Run only after S4 source coding is complete and committed, from a clean named branch. Substitute the actual unprivileged WSL runner account, worker group ID, and a pre-provisioned POSIX destination root; do not put host paths or identities in committed run evidence.

```powershell
C:\Python314\python.exe -m tools.qa.wsl_snapshot `
  --cwd . `
  --distribution Ubuntu-24.04 `
  --wsl-user <runner-account> `
  --worker-gid <worker-group-id> `
  --snapshot-root <private-posix-destination>
```

The tool refuses dirty or detached source state, another distribution name, invalid identity values, an unavailable `wsl.exe`, a bundle larger than 512 MiB, or a transfer exceeding five minutes. It returns JSON containing a random run ID, exact candidate HEAD, bundle SHA-256, and byte count. The WSL checkout path is the destination root plus the returned run ID plus `/repo`.

## Remaining runtime gates

- The source-transfer code has not been executed. Exact-head, size, timeout, hash, permission, symlink, and WSL interop behavior remain `NOT_RUN`.
- The exact WSL runner account, worker group ID, and provisioned destination root must come from the private sandbox provisioning evidence; this document does not invent them.
- A trusted signer socket must be independently available to the runner identity and inaccessible to the worker. The transfer tool does not create or authorize that socket.
- Native pytest execution, report signing, artifact resolution, and exact-head gate acceptance remain `NOT_RUN` until the designated functional/E2E phase and signer environment are available.
