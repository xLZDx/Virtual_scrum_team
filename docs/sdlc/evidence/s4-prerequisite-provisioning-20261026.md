# S4 prerequisite provisioning record — 2026-10-26

## Scope and result

This records two bounded prerequisites for the S4 report-bound WSL runs: a trusted offline wheelhouse for the committed QA lock and an Ubuntu 24.04 C compiler toolchain for building the fixed worker identity helper. Provisioning does not constitute a helper installation, test run, or acceptance result.

## Locked QA wheelhouse

- Location: `D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse`.
- Prepared with `C:\Python314\python.exe -m pip download --no-deps --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r tools/qa/requirements.lock`.
- Six wheel files are present. Their SHA-256 values are:

| Wheel | SHA-256 |
|---|---|
| `colorama-0.4.6-py2.py3-none-any.whl` | `4f1d9991f5acc0ca119f9d443620b77f9d6b33703e51011c16baf57afb285fc6` |
| `iniconfig-2.3.0-py3-none-any.whl` | `f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12` |
| `packaging-26.2-py3-none-any.whl` | `5fc45236b9446107ff2415ce77c807cee2862cb6fac22b8a73826d0693b0980e` |
| `pluggy-1.6.0-py3-none-any.whl` | `e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746` |
| `pygments-2.20.0-py3-none-any.whl` | `81a9e26dd42fd28a23a2d169d86d7ac03b46e2f8b59ed4698fb4785f946d0176` |
| `pytest-9.0.3-py3-none-any.whl` | `2c5efc453d45394fdd706ade797c0a81091eccd1d6e4bccfcd476e2b8e0ab5d9` |

The download used pip hash enforcement and binary-only selection. The pre-existing `D:\Temp\virtual_scrum_team_qa_f4ef8e7` remains a separate installed dependency target and was not used as a wheelhouse.

## Ubuntu 24.04 compiler toolchain

- Thirty Ubuntu `amd64` `.deb` package entries, including `gcc`, GCC 13, `libc6-dev`, and their declared dependencies, are recorded in [`s4-ubuntu2404-offline-toolchain-manifest-20261026.json`](s4-ubuntu2404-offline-toolchain-manifest-20261026.json).
- The manifest SHA-256 is `26cf4073d1cb83dbd60e0a91e4d91be0ab23bc2eb9f685d0e21dcb1ec342272`.
- Package digests were checked against Ubuntu apt metadata; the selected Ubuntu 24.04 WSL environment had no egress, so package archives were transferred over stdin without a Windows-drive mount and installed from local package files.
- Post-provisioning `cc`/`gcc` identified Ubuntu GCC 13.3.0. WSL automount and interop remained disabled.
- This provisioning step changed the WSL toolchain package state. No project binary/helper was installed.

## Acceptance boundary

- At the time this prerequisite record was created, S4 AC-16 helper compilation, installation, and report-bound identity execution were `NOT_RUN`; the earlier compile failure exposed the source declaration issue fixed in change 0344.
- At the time this prerequisite record was created, AC-17 report-bound dependency-content execution and the three seeded-failure selectors were `NOT_RUN`.
- The 52 policy-excluded selectors remain `NOT_RUN`; no timeout, process-kill, process-death, mutation, or prohibited crash scenario was invoked.
- This record proves the prerequisite artifacts were provisioned and locally inventoried, not that tests passed or that S4 is approved.

## Subsequent report-bound results

At candidate HEAD `4fe150326a36faf401b045cfa1b9a2e64d89436b`, the designated `e2e-runner` passed the singleton AC-16 WSL identity selector 1/1 and all three permitted AC-12 seeded-failure selectors 3/3. The locked dependency-target inventory matched the wheel lock both immediately before and after each run. The runner leaves in-run dependency mutation/change-and-restore protection `NOT_VERIFIED`; no stronger guarantee is claimed. Exact run IDs, row hashes, source/manifest identity, and limitations are recorded in [`s4-report-bound-allowed-runs-20261026.md`](s4-report-bound-allowed-runs-20261026.md). The 52 policy selectors remain `NOT_RUN`, and S4 has not received an exact-head GPT-PM gate.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Provisioning and evidence recording: Codex.
- Runtime test execution remains assigned to `functional-test-reviewer` / `e2e-runner` after coding and registry commit.

## Read-only prerequisite recheck — 2026-10-26

The current continuation verified the exact recorded wheelhouse path
`D:\Temp\virtual_scrum_team_qa_f4ef8e7_wheelhouse` by enumerating the six `.whl`
files and computing SHA-256. All six digests match the lock/provisioning table above.
No download, installation, or project test was performed during this recheck.

The following read-only commands were run in the named `Ubuntu-24.04` WSL distro:

```text
wsl.exe -d Ubuntu-24.04 -- /usr/bin/gcc --version
wsl.exe -d Ubuntu-24.04 -- /usr/bin/cc --version
wsl.exe -d Ubuntu-24.04 -- /usr/bin/id
```

Observed compiler: GCC/CC `13.3.0`. The default distro command identity was
`uid=0(root) gid=0(root) groups=0(root)`. This confirms toolchain availability only;
it does not prove the report-bound helper's unprivileged worker identity or S2
containment. The earlier report-bound worker-identity evidence remains separately
scoped to its recorded run.
