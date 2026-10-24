# S4 WSL source transfer and worker boundary at 452c8ea

## Scope and provenance

- Source repository: `D:\Repo\Virtual_scrum_team-s4`.
- Source branch: `s4-native-qa-runner`.
- Pre-transfer HEAD: `452c8ea8da5545bdce0f584a6b51662b93a33abf`; worktree was clean.
- WSL target: named `Ubuntu-24.04` distribution.
- Transfer was limited to a self-contained Git bundle into the already provisioned private snapshot root. No packages were installed; pytest, signer, report, or gate were not invoked during transfer.

## Command and correlated result

Command shape (private POSIX identity/group/root values omitted):

```text
C:\Python314\python.exe -m tools.qa.wsl_snapshot --cwd . --distribution Ubuntu-24.04 --wsl-user [private runner] --worker-gid [private group] --snapshot-root [private snapshot root]
```

The command returned `TRANSFERRED` with run ID `e8b68c59c17a449eb2e30803021a37ae`. The returned candidate HEAD exactly matched the requested HEAD. Bundle digest was `2d986eb65301d89e2530a13cce8a9924378dd7851c1fa986f78051edd0dd344c`, size `972190` bytes.

## Run-scoped verification

All probes were scoped to the returned run ID only. The runner-side probe independently verified bundle size and SHA-256, clone HEAD, ownership/group consistency, modes, and absence of symbolic links:

| Check | Result |
|---|---|
| Candidate HEAD | Exact match: `452c8ea8da5545bdce0f584a6b51662b93a33abf` |
| Bundle SHA-256 and bytes | Exact match: `2d986eb65301d89e2530a13cce8a9924378dd7851c1fa986f78051edd0dd344c`, `972190` |
| Run directory mode | `2710` |
| Repository root mode | `0750` |
| Repository entries | 40 directories and 271 files; zero mode errors, owner/group errors, or symlinks |
| Runner bundle file | Mode `0600` |
| Worker boundary | Worker read `README.md`; append-open and new-file creation were denied; no write was performed |

Private POSIX usernames, numeric IDs, and snapshot root are intentionally not recorded. This evidence applies only to this run and does not establish sandbox limits beyond the observed file boundary.

## Result

Transfer and run-scoped permission checks: **PASS**. The identified clone was then used for mapped native E2E; the separate test results are in `docs/sdlc/evidence/s4-native-e2e-452c8ea.md`. Signer socket, report-bound runner, receipt, and authoritative gate were not invoked.
