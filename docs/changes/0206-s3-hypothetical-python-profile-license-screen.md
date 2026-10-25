# Change record 0206: Map licenses for hypothetical S3 Python base profiles

## What changed

- Added a bounded, read-only license screen for hypothetical Linux x86-64 / Python 3.12 / base-dependency profiles for BMad Loop and the Temporal Python SDK.
- Updated the S3 plan, VST-028 backlog, bilingual report, decision log, lesson log, and generated document registry.
- Kept the profiles explicitly hypothetical; no candidate was selected or approved.

## Why

VST-028 requires dependency and license assessment before acquisition. Public pinned lockfiles and exact-version package metadata can identify some Python dependency licenses without downloading or installing candidate packages, but their scope must not be overstated as complete runtime/build closure.

## Evidence and limits

- Reviewer: `security-reviewer`, GPT-6 Luna, medium effort. Read-only review of pinned lockfiles and authoritative project/package metadata; no clone, download, install, build, execution, or tests.
- Hypothetical BMad Loop 0.13.2 Linux base: root project MIT; PyYAML 6.0.3 MIT from the pinned [`uv.lock`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/uv.lock) and upstream project; `regex` 2026.7.19 is `Apache-2.0 AND CNRI-Python` per [exact-version PyPI metadata](https://pypi.org/project/regex/2026.7.19/). Windows-only `psutil` and optional `tui`, `opencode`, and non-Linux extras are excluded. Hatchling is a separate build dependency; the invoked coding-agent/provider executable is outside this lock and not identified.
- Hypothetical Temporal Python SDK 1.34.0 Python 3.12 base: root project MIT; `nexus-rpc` 1.4.0 MIT; `protobuf` 6.33.6 BSD-3-Clause; `types-protobuf` 7.34.1.20260518 Apache-2.0 (type stubs); `typing-extensions` 4.16.0 PSF-2.0. The pinned [`uv.lock`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/uv.lock) and exact-version [PyPI metadata](https://pypi.org/project/protobuf/6.33.6/) identify these resolutions/licenses. `python-dateutil` and `six` are conditional on Python `<3.11` and excluded from the hypothetical profile.
- The Temporal bridge compiles Rust code and includes a larger submodule/dependency graph not mapped to complete third-party notices. The Temporal server Go module graph and minimal build/deployment profile also remain unmapped. The inspected [PyPI SDK metadata](https://pypi.org/project/temporalio/1.34.0/) reports `provenance=false` for wheels; hashes alone do not bind them to the pinned source build.
- The selected candidate, OS/runtime profile, extras, build artifacts, compatibility and deployment configuration remain unknown. No runtime or security boundary claim is made.

## Ownership and next step

- Accountable task owner: operator for candidate selection and acquisition authorization.
- Executor: Codex for bounded source/dependency audit.
- Technical sandbox/service owner: not identified in inspected S3 records.
- Next: after a candidate/profile is selected, close its applicable Temporal Rust/Go/build and license-notice graph from authoritative sources. Do not acquire or execute until explicit authorization and a fresh run-bound S2 probe.

## Verification state

Documentation-only audit. No tests, checks, build, package download, candidate acquisition, installation, or runtime execution were performed.
