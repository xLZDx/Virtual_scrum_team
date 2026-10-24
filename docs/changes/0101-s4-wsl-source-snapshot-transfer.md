# 0101 S4 WSL source snapshot transfer

## What changed

- Added `tools/qa/wsl_snapshot.py` to require a clean, committed named Windows branch, create a bounded self-contained Git bundle, and stream it over `wsl.exe` stdin into the explicitly named `Ubuntu-24.04` distribution.
- The WSL receiver requires a pre-provisioned private root owned by the runner, grouped to the dedicated QA worker, and mode `2710`. It creates a mode `0710` run directory, clones the exact branch, checks the expected candidate HEAD and owner/group, rejects symbolic links, and prepares a worker-readable/nonwritable source tree.
- The Windows sender and WSL receiver independently compute the bundle SHA-256 and byte count; mismatched metadata, dirty/detached source, other distro names, oversize bundle, timeout, wrong identity/mode, or changed cloned HEAD refuses transfer.
- Added `docs/S4_WSL_SNAPSHOT_TRANSFER.md` and updated S4 design, backlog, plan, decision and lessons records. Regenerated the document registry.

## Why

The native v2 signer runner requires POSIX identity separation, while the source checkout is on Windows and the dedicated WSL has automount and interop disabled. A bounded byte-stream transfer preserves the exact commit and source history without making a host drive or checkout path visible inside WSL.

## Affected contracts and paths

- `tools/qa/wsl_snapshot.py`: Windows host transfer and WSL receiver.
- `docs/S4_WSL_SNAPSHOT_TRANSFER.md`: invocation, destination permissions and runtime gates.
- S4 plan/design, backlog, decision/lessons logs, and generated document registry.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- Distribution is fixed to `Ubuntu-24.04`; no distribution enumeration or provisioning is performed.
- The runner account, worker group ID, and private destination root must come from private provisioning evidence and remain outside public repository records. Canonical technical owner is `UNKNOWN`.
- The tool does not create the destination root, install packages, provision the signer, execute QA, or produce a signed VST receipt.
- Git bundle stream and stdin behavior follow the official [`git bundle` documentation](https://git-scm.com/docs/git-bundle).

## Verification state

- Manual source inspection only. No tests, checks, builds, CI, package installations, migrations, or WSL transfer were run.
- Exact-head transfer, bundle hash agreement, permission modes, symlink rejection, timeout, and source read-only behavior remain `NOT_RUN`.

## Follow-up

1. Complete remaining S4 source work before test phase.
2. After source freeze, have the designated E2E owner execute transfer with the exact private runner account, worker group ID and destination root.
3. Use the returned run ID and candidate HEAD for pinned native QA only after the trusted signer socket is available to the runner identity and denied to the worker.
